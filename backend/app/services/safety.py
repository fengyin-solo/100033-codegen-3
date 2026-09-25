"""安全区域管控业务规则：电子围栏、角色授权、越界告警与安全看板。

数据落在内存仓库的三张表：
- zone：电子围栏定义，边界坐标为 [[x,y], ...] 的多边形；
- zone_grant：角色编码与安全区域的授权关系；
- boundary_alarm：定位点越界产生的告警，独立于普通告警中心。
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.security import ROLE_CATALOG, authorized_zone_ids, can, role_label
from app.store import store

ZONE_MODULE = "zone"
GRANT_MODULE = "zone_grant"
BOUNDARY_MODULE = "boundary_alarm"
ZONE_REQUIRED = ["区域编码", "区域名称", "作业地点", "边界坐标"]
BOUNDARY_STATUSES = ["待提醒", "已提醒", "已处置"]


def _zone_name(zone_id: Any) -> str:
    zone = store.find(ZONE_MODULE, int(zone_id)) if str(zone_id).isdigit() else None
    return str(zone["区域名称"]) if zone else f"区域{zone_id}"


def _enrich_zone(row: dict[str, Any]) -> dict[str, Any]:
    grants = store.rows(GRANT_MODULE)
    roles = sorted({str(g["角色编码"]) for g in grants if g.get("安全区域ID") == row["id"]})
    result = dict(row)
    result["授权角色"] = [
        {"角色编码": code, "角色名称": role_label(code)} for code in roles if code in ROLE_CATALOG
    ]
    result["生效许可数"] = sum(
        1
        for permit in store.rows("permit")
        if permit.get("安全区域ID") == row["id"] and permit.get("status") == "已许可"
    )
    result["待提醒越界数"] = sum(
        1
        for alarm in store.rows(BOUNDARY_MODULE)
        if alarm.get("安全区域ID") == row["id"] and alarm.get("状态") == "待提醒"
    )
    return result


def _parse_polygon(raw: Any) -> list[list[float]]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    points = [[float(x), float(y)] for x, y in raw]
    if len(points) < 3:
        raise ValueError("电子围栏至少需要 3 个坐标点才能围成封闭区域")
    return points


def _point_in_polygon(point: list[float], polygon: list[list[float]]) -> bool:
    """射线法判断点是否在多边形内（含边界按在内处理）。"""
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _enrich_boundary(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    result["安全区域名称"] = _zone_name(row.get("安全区域ID"))
    result["告警分类"] = "越界告警"
    return result


class SafetyService:
    # ---------------- 电子围栏 ----------------

    def list_zones(self, role_code: str) -> list[dict[str, Any]]:
        scope = authorized_zone_ids(role_code)
        rows = store.rows(ZONE_MODULE)
        if scope is not None:
            rows = [row for row in rows if int(row["id"]) in scope]
        return [_enrich_zone(row) for row in rows]

    def get_zone(self, zone_id: int) -> dict[str, Any] | None:
        row = store.find(ZONE_MODULE, zone_id)
        return _enrich_zone(row) if row else None

    def save_zone(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """新增或更新围栏。维护人员等只读角色在路由层就被拦下，这里只校验数据。"""
        missing = [field for field in ZONE_REQUIRED if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        try:
            polygon = _parse_polygon(values["边界坐标"])
        except (ValueError, json.JSONDecodeError, TypeError) as exc:
            return None, f"边界坐标无法围成电子围栏：{exc}"

        rows = store.rows(ZONE_MODULE)
        zone_id = values.get("id")
        if zone_id:
            row = store.find(ZONE_MODULE, int(zone_id))
            if row is None:
                return None, f"安全区域 {zone_id} 不存在"
            code = str(values["区域编码"]).strip()
            if any(r["id"] != row["id"] and r["区域编码"] == code for r in rows):
                return None, f"区域编码 {code} 已被其他围栏占用"
            row.update({
                "区域编码": code,
                "区域名称": str(values["区域名称"]).strip(),
                "作业地点": str(values["作业地点"]).strip(),
                "边界坐标": json.dumps(polygon, ensure_ascii=False),
                "围栏状态": str(values.get("围栏状态") or "启用"),
                "备注": str(values.get("备注") or ""),
            })
            return _enrich_zone(row), "电子围栏已更新"

        code = str(values["区域编码"]).strip()
        if any(row["区域编码"] == code for row in rows):
            return None, f"区域编码 {code} 已存在"
        entry = {"id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
                 "区域编码": code,
                 "区域名称": str(values["区域名称"]).strip(),
                 "作业地点": str(values["作业地点"]).strip(),
                 "边界坐标": json.dumps(polygon, ensure_ascii=False),
                 "围栏状态": str(values.get("围栏状态") or "启用"),
                 "备注": str(values.get("备注") or "")}
        rows.append(entry)
        return _enrich_zone(entry), "电子围栏已划定"

    # ---------------- 角色授权 ----------------

    def list_grants(self, role_code: str | None = None) -> list[dict[str, Any]]:
        rows = store.rows(GRANT_MODULE)
        if role_code:
            rows = [row for row in rows if row.get("角色编码") == role_code]
        result = []
        for row in rows:
            item = dict(row)
            item["角色名称"] = role_label(str(row.get("角色编码")))
            item["安全区域名称"] = _zone_name(row.get("安全区域ID"))
            result.append(item)
        return result

    def save_grant(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        code = str(values.get("角色编码") or "").strip()
        if code not in ROLE_CATALOG:
            return None, f"角色编码 {code} 不存在，无法授权"
        try:
            zone_id = int(values.get("安全区域ID"))
        except (TypeError, ValueError):
            return None, "安全区域ID缺失或不是整数"
        if store.find(ZONE_MODULE, zone_id) is None:
            return None, f"安全区域 {zone_id} 不存在"
        rows = store.rows(GRANT_MODULE)
        existing = next(
            (r for r in rows if r["角色编码"] == code and int(r["安全区域ID"]) == zone_id),
            None,
        )
        if existing:
            return None, f"{role_label(code)}已被授权访问{_zone_name(zone_id)}，不能重复授权"
        entry = {"id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
                 "角色编码": code, "安全区域ID": zone_id}
        rows.append(entry)
        item = dict(entry)
        item["角色名称"] = role_label(code)
        item["安全区域名称"] = _zone_name(zone_id)
        return item, f"已将{_zone_name(zone_id)}授权给{role_label(code)}"

    def revoke_grant(self, grant_id: int) -> tuple[bool, str]:
        rows = store.rows(GRANT_MODULE)
        target = next((r for r in rows if int(r["id"]) == grant_id), None)
        if target is None:
            return False, f"授权记录 {grant_id} 不存在"
        rows.remove(target)
        return True, f"已收回{role_label(str(target['角色编码']))}对{_zone_name(target['安全区域ID'])}的授权"

    # ---------------- 越界告警 ----------------

    def report_position(
        self, role_code: str, zone_id: int, person: str, point_raw: Any
    ) -> tuple[dict[str, Any] | None, str, bool]:
        """作业人员定位上报：点落在围栏外即生成越界告警，并提醒值班管理员。

        返回 (记录, 消息, 是否越界)。
        """
        zone = store.find(ZONE_MODULE, zone_id)
        if zone is None:
            return None, f"安全区域 {zone_id} 不存在", False
        try:
            point = [float(v) for v in point_raw]
            if len(point) != 2:
                raise ValueError
        except (TypeError, ValueError):
            return None, "定位坐标必须是包含 x、y 两个数字的数组", False
        try:
            polygon = _parse_polygon(zone["边界坐标"])
        except (ValueError, json.JSONDecodeError):
            return None, "该安全区域的围栏坐标异常，请联系值班管理员修正", False

        inside = _point_in_polygon(point, polygon)
        if inside:
            return {"越界": False, "安全区域名称": zone["区域名称"]}, "定位点在电子围栏内，未越界", False

        rows = store.rows(BOUNDARY_MODULE)
        entry = {
            "id": max((int(r.get("id", 0)) for r in rows), default=0) + 1,
            "安全区域ID": zone_id,
            "越界编号": f"BND-{max((int(r.get('id', 0)) for r in rows), default=0) + 1:04d}",
            "越界人员": person or "未登记人员",
            "定位坐标": json.dumps(point, ensure_ascii=False),
            "越界时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "状态": "待提醒",
            "提醒值班人": "值班管理员",
            "处置说明": "",
        }
        rows.append(entry)
        return _enrich_boundary(entry), f"检测到{entry['越界人员']}越出{zone['区域名称']}，已提醒值班管理员", True

    def list_boundary_alarms(
        self, role_code: str, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        scope = authorized_zone_ids(role_code)
        rows = store.rows(BOUNDARY_MODULE)
        if scope is not None:
            rows = [row for row in rows if int(row.get("安全区域ID", 0)) in scope]
        if status:
            rows = [row for row in rows if row.get("状态") == status]
        return [_enrich_boundary(row) for row in rows]

    def acknowledge_boundary(self, alarm_id: int, note: str) -> tuple[dict[str, Any] | None, str]:
        row = store.find(BOUNDARY_MODULE, alarm_id)
        if row is None:
            return None, f"越界告警 {alarm_id} 不存在"
        row["状态"] = "已处置" if note.strip() else "已提醒"
        if note.strip():
            row["处置说明"] = note.strip()
        return _enrich_boundary(row), "越界告警已处置并通知值班记录归档"

    # ---------------- 安全看板 ----------------

    def dashboard(self, role_code: str) -> dict[str, Any]:
        """安全看板：授权范围与角色保持一致，只汇总本角色可见区域的数据。"""
        zones = self.list_zones(role_code)
        scope = authorized_zone_ids(role_code)
        permits = store.rows("permit")
        alarms = store.rows("alarm")
        boundary = store.rows(BOUNDARY_MODULE)
        if scope is not None:
            permits = [r for r in permits if r.get("安全区域ID") in scope]
            alarms = [
                r for r in alarms
                if r.get("安全区域ID") in scope
                and r.get("告警类型") != "越界告警"
                and not r.get("越界标记")
            ]
            boundary = [r for r in boundary if r.get("安全区域ID") in scope]

        from app.services.permit import annotate_locks, dedupe_permits

        permit_rows = annotate_locks(dedupe_permits(permits))
        released = [r for r in permit_rows if r.get("放行状态") == "放行"]
        readonly = [r for r in permit_rows if r.get("只读")]
        return {
            "角色编码": role_code,
            "角色名称": role_label(role_code),
            "授权范围": "全站安全区域" if scope is None else f"已授权 {len(scope)} 个安全区域",
            "cards": [
                {"label": "授权安全区域", "value": len(zones)},
                {"label": "生效中许可", "value": sum(1 for r in permit_rows if r.get("status") == "已许可")},
                {"label": "放行许可", "value": len(released)},
                {"label": "只读（排队）许可", "value": len(readonly)},
                {"label": "待确认普通告警", "value": sum(1 for r in alarms if r.get("status") == "待确认")},
                {"label": "待提醒越界告警", "value": sum(1 for r in boundary if r.get("状态") == "待提醒")},
            ],
            "zones": zones,
            "released_permits": released,
            "readonly_permits": readonly,
            "boundary_alarms": [_enrich_boundary(r) for r in boundary],
        }
