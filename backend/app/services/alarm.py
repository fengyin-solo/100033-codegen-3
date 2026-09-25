"""告警中心业务规则：状态流转、字段校验与筛选口径都收在这里。

接入安全区域管控后：
1. 普通告警只按授权区域过滤；越界告警走 boundary_alarm 独立表与独立看板，
   绝不在普通告警列表里显示成普通告警（即使老数据混入标记也会被剔除）；
2. 同一条告警按告警编号去重，只展示一次；
3. 确认/处置等动作要过角色权限与区域授权，越权拒绝并说明原因。
"""
from __future__ import annotations

from typing import Any

from app.security import (
    authorized_zone_ids,
    can,
    role_label,
    zone_in_scope,
)
from app.store import store

MODULE = "alarm"
REQUIRED_FIELDS = ["告警编号", "告警类型", "告警等级"]
STATUS_ORDER = ["待确认", "已确认", "已处置", "已忽略"]
ACTION_RULES = {"确认告警": "已确认", "处置告警": "已处置", "忽略告警": "已忽略"}
NEGATIVE_ACTIONS = ["忽略告警"]


def _zone_id(row: dict[str, Any]) -> int | None:
    try:
        return int(row["安全区域ID"])
    except (KeyError, TypeError, ValueError):
        return None


def dedupe_alarms(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按告警编号去重：同编号只保留 id 最小的一条。"""
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("告警编号") or "").strip()
        if not code:
            continue
        current = best.get(code)
        if current is None or int(row.get("id", 0)) < int(current.get("id", 0)):
            best[code] = row
    return sorted(best.values(), key=lambda row: int(row.get("id", 0)))


def _scoped_rows(role_code: str) -> list[dict[str, Any]]:
    rows = store.rows(MODULE)
    # 越界告警不能混进普通告警列表：双保险，按独立标记再剔一次
    rows = [
        row for row in rows
        if row.get("告警类型") != "越界告警" and not row.get("越界标记")
    ]
    scope = authorized_zone_ids(role_code)
    if scope is not None:
        rows = [row for row in rows if _zone_id(row) in scope]
    return dedupe_alarms(rows)


class AlarmService:
    def list_entries(
        self,
        *,
        role_code: str,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = _scoped_rows(role_code)
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
        entry["安全区域ID"] = values.get("安全区域ID")
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(
        self, role_code: str, entry_id: int, action: str
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"告警事件 {entry_id} 不存在或已归档"

        if not can(role_code, "alarm_action"):
            raise PermissionError(
                f"越权提交已拒绝：{role_label(role_code)}只有查看权限，不能执行「{action}」"
            )
        if not zone_in_scope(role_code, _zone_id(entry)):
            raise PermissionError(
                f"越权提交已拒绝：告警 {entry.get('告警编号')} 不在{role_label(role_code)}的授权区域内"
            )
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于告警中心可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"告警事件已{action}"
