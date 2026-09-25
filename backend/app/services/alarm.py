"""告警中心业务规则：状态流转、字段校验与筛选口径都收在这里。

越界告警不在普通告警列表里显示，统一由安全区域看板单独列出并提醒值班人。
"""
from __future__ import annotations

from typing import Any

from app.services.zone import BOUNDARY_ALARM_TYPE, ZoneService
from app.store import store

MODULE = "alarm"
REQUIRED_FIELDS = ["告警编号", "告警类型", "告警等级"]
STATUS_ORDER = ["待确认", "已确认", "已处置", "已忽略"]
ACTION_RULES = {"确认告警": "已确认", "处置告警": "已处置", "忽略告警": "已忽略"}
NEGATIVE_ACTIONS = ["忽略告警"]

zone_service = ZoneService()


class AlarmService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        role: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [row for row in store.rows(MODULE) if row.get("告警类型") != BOUNDARY_ALARM_TYPE]
        if role:
            locations = zone_service.authorized_locations(role)
            rows = [row for row in rows if str(row.get("作业地点") or "") in locations]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("告警编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"告警事件 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于告警中心可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"告警事件已{action}"
