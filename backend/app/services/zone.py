"""安全区域管控业务规则：电子围栏、角色授权、越界告警与值班人提醒都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "zone"
REQUIRED_FIELDS = ["区域编号", "区域名称", "作业地点"]
STATUS_ORDER = ["启用", "停用"]
ROLES = ["值班管理员", "值班人", "维护人员", "外委负责人"]
ADMIN_ROLE = "值班管理员"
VIEW_ONLY_ROLES = ["维护人员"]
BOUNDARY_ALARM_TYPE = "越界告警"


class ZoneService:
    """按角色圈定可见区域；围栏调整、越界告警看板的口径也统一从这里出。"""

    def list_entries(
        self,
        *,
        role: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self.visible_zones(role)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("区域编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any], *, role: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
        if role and role != ADMIN_ROLE:
            return None, [f"当前角色（{role}）无权圈定安全区域，需值班管理员操作"]
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, [f"缺少必填字段：{'、'.join(missing)}"]
        code = str(values.get("区域编号") or "").strip()
        if any(str(row.get("区域编号") or "") == code for row in store.rows(MODULE)):
            return None, [f"区域编号 {code} 已存在，同一片安全区域不能重复圈定"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS})
        entry["围栏范围"] = str(values.get("围栏范围") or "").strip()
        entry["授权角色"] = str(values.get("授权角色") or ADMIN_ROLE).strip() or ADMIN_ROLE
        entry["值班人"] = str(values.get("值班人") or "").strip()
        entry["区域状态"] = STATUS_ORDER[0]
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def adjust_boundary(self, entry_id: int, role: str, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """调整电子围栏边界；维护人员只能查看，越权改动一律说明原因后拒绝。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"安全区域 {entry_id} 不存在或已撤销"
        if role in VIEW_ONLY_ROLES:
            return None, "维护人员只能查看安全区域，不能改动电子围栏边界"
        if role != ADMIN_ROLE:
            return None, f"当前角色（{role or '未指定'}）无权调整电子围栏，需值班管理员操作"
        boundary = str(values.get("围栏范围") or "").strip()
        if not boundary:
            return None, "围栏范围不能为空，请先圈定电子围栏边界"
        entry["围栏范围"] = boundary
        return entry, "安全区域电子围栏已调整"

    def visible_zones(self, role: str | None) -> list[dict[str, Any]]:
        """被授权人只能看到自己区域内的内容；未识别角色不给任何区域。"""
        rows = store.rows(MODULE)
        if not role or role == ADMIN_ROLE:
            return list(rows)
        if role not in ROLES:
            return []
        return [row for row in rows if role in self._roles_of(row)]

    def authorized_locations(self, role: str | None) -> set[str]:
        """角色被授权的作业地点集合，许可列表与告警看板都按这个口径过滤。"""
        return {str(zone.get("作业地点") or "") for zone in self.visible_zones(role)}

    def boundary_alarms(self, role: str | None = None) -> list[dict[str, Any]]:
        """越界告警单独列出并带上要提醒的值班人，不混进普通告警列表。"""
        rows = [row for row in store.rows("alarm") if row.get("告警类型") == BOUNDARY_ALARM_TYPE]
        if role and role != ADMIN_ROLE:
            locations = self.authorized_locations(role)
            rows = [row for row in rows if str(row.get("作业地点") or "") in locations]
        return rows

    def dashboard(self, role: str | None = None) -> dict[str, Any]:
        """看板数据：授权区域、越界告警、生效许可都按角色圈定，授权范围与角色保持一致。"""
        zones = self.visible_zones(role)
        locations = {str(zone.get("作业地点") or "") for zone in zones}
        alarms = self.boundary_alarms(role)
        active_permits = [
            row for row in store.rows("permit")
            if row.get("status") == "已许可" and str(row.get("作业地点") or "") in locations
        ]
        return {
            "role": role or ADMIN_ROLE,
            "zones": zones,
            "boundary_alarms": alarms,
            "active_permits": active_permits,
        }

    def _roles_of(self, zone: dict[str, Any]) -> list[str]:
        return [item.strip() for item in str(zone.get("授权角色") or "").split(",") if item.strip()]
