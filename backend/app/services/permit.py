"""作业许可业务规则：状态流转、字段校验与筛选口径都收在这里。

安全区域管控叠加在老流程之上：按角色圈定可见范围、同区域许可去重、
许可标识错位清理、同区域多条生效许可按优先级只放行一条，其余只读。
"""
from __future__ import annotations

from typing import Any

from app.services.zone import ZoneService
from app.store import store

MODULE = "permit"
REQUIRED_FIELDS = ["许可编号", "作业类型", "作业地点"]
STATUS_ORDER = ["待申请", "已受理", "已许可", "已驳回", "已过期"]
ACTION_RULES = {"提交申请": "已受理", "签发许可": "已许可", "驳回申请": "已驳回"}
NEGATIVE_ACTIONS = ["驳回申请"]
ACTIVE_STATUS = "已许可"
PRIORITY_RANK = {"高": 3, "中": 2, "低": 1}

zone_service = ZoneService()


class PermitService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        role: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        self._sync_zone_markers()
        self._apply_release_control()
        rows = store.rows(MODULE)
        if role:
            locations = zone_service.authorized_locations(role)
            rows = [row for row in rows if str(row.get("作业地点") or "") in locations]
        rows = self._dedupe(rows)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("许可编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any], *, role: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values.get("许可编号") or "").strip()
        if any(str(row.get("许可编号") or "") == code for row in store.rows(MODULE)):
            return None, [f"许可编号 {code} 已存在，同一片区域的许可不能重复登记"]
        location = str(values.get("作业地点") or "").strip()
        if role and location not in zone_service.authorized_locations(role):
            return None, [f"作业地点「{location}」不在当前角色（{role}）的授权区域内，越权提交已拒绝"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS})
        priority = str(values.get("优先级") or "中").strip()
        entry["优先级"] = priority if priority in PRIORITY_RANK else "中"
        entry["工作负责人"] = str(values.get("工作负责人") or "").strip()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        self._sync_zone_markers()
        return entry, []

    def run_action(self, entry_id: int, action: str, *, role: str | None = None) -> tuple[dict[str, Any] | None, str]:
        self._sync_zone_markers()
        self._apply_release_control()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"作业许可单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于作业许可可执行范围"
        if role and str(entry.get("作业地点") or "") not in zone_service.authorized_locations(role):
            return None, f"作业地点「{entry.get('作业地点')}」不在当前角色（{role}）的授权区域内，越权操作已拒绝"
        if entry.get("只读"):
            return None, f"同区域已有更高优先级许可放行中，许可 {entry.get('许可编号')} 当前为只读状态，不能{action}"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        self._apply_release_control()
        return entry, f"作业许可单已{action}"

    def _dedupe(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """同一片区域的许可不能重复显示两遍：按许可编号去重，保留先登记的一条。"""
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for row in rows:
            key = str(row.get("许可编号") or f"#{row.get('id')}")
            if key in seen:
                continue
            seen.add(key)
            result.append(row)
        return result

    def _sync_zone_markers(self) -> None:
        """许可标识错位清理：区域编号必须落在作业地点对应的电子围栏上，错位的一律清掉重标。"""
        location_to_code = {
            str(zone.get("作业地点") or ""): str(zone.get("区域编号") or "")
            for zone in store.rows("zone")
        }
        for row in store.rows(MODULE):
            expect = location_to_code.get(str(row.get("作业地点") or ""), "")
            if str(row.get("区域编号") or "") != expect:
                row["区域编号"] = expect

    def _apply_release_control(self) -> None:
        """同一片安全区域内多条许可同时生效时，按优先级只放行一条，其余置为只读。"""
        rows = store.rows(MODULE)
        for row in rows:
            row["只读"] = False
            row["放行状态"] = ""
        active: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if row.get("status") == ACTIVE_STATUS:
                key = str(row.get("区域编号") or row.get("作业地点") or "")
                active.setdefault(key, []).append(row)
        for group in active.values():
            group.sort(key=lambda row: (-PRIORITY_RANK.get(str(row.get("优先级") or ""), 0), int(row.get("id", 0))))
            for index, row in enumerate(group):
                row["只读"] = index > 0
                row["放行状态"] = "放行中" if index == 0 else "等待放行"
