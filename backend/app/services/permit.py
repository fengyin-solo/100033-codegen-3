"""作业许可业务规则：状态流转、字段校验与筛选口径都收在这里。

安全区域管控接入后，这里额外负责：
1. 按当前角色的授权区域过滤许可（越权许可根本不出现在列表里）；
2. 同一条许可只展示一次（以许可编号去重，保留 id 最小的主记录）；
3. 同一片安全区域内多条同时生效的许可，只放行优先级最高的一条，其余置为只读；
4. 动作提交前校验角色权限与区域授权，越权一律拒绝并说明原因。
老的登记/提交/签发/驳回流程保持不变。
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

MODULE = "permit"
REQUIRED_FIELDS = ["许可编号", "作业类型", "作业地点"]
STATUS_ORDER = ["待申请", "已受理", "已许可", "已驳回", "已过期"]
ACTION_RULES = {"提交申请": "已受理", "签发许可": "已许可", "驳回申请": "已驳回"}
NEGATIVE_ACTIONS = ["驳回申请"]
ACTIVE_STATUS = "已许可"


def _zone_id(row: dict[str, Any]) -> int | None:
    try:
        return int(row["安全区域ID"])
    except (KeyError, TypeError, ValueError):
        return None


def dedupe_permits(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按许可编号去重：同编号只保留 id 最小的一条，杜绝列表里显示两遍。"""
    best: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = str(row.get("许可编号") or "").strip()
        if not code:
            continue
        current = best.get(code)
        if current is None or int(row.get("id", 0)) < int(current.get("id", 0)):
            best[code] = row
    return sorted(best.values(), key=lambda row: int(row.get("id", 0)))


def annotate_locks(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """给生效许可打放行/只读标注，只读许可不能执行任何动作。

    同一片安全区域内同时生效（状态=已许可）的许可，优先级数值最大的一条放行，
    其余只读；优先级相同取许可编号最小的，保证结果稳定。
    """
    winner_by_zone: dict[int, int] = {}
    active = [row for row in rows if row.get("status") == ACTIVE_STATUS]
    for row in active:
        zone_id = _zone_id(row)
        if zone_id is None:
            row["放行状态"] = "放行"
            row["只读"] = False
            continue
        current_id = winner_by_zone.get(zone_id)
        if current_id is None:
            winner_by_zone[zone_id] = int(row["id"])
        else:
            current = next(item for item in active if int(item["id"]) == current_id)
            if (int(row.get("优先级", 0)), -int(row["id"])) > (
                int(current.get("优先级", 0)),
                -int(current["id"]),
            ):
                winner_by_zone[zone_id] = int(row["id"])

    for row in rows:
        zone_id = _zone_id(row)
        if row.get("status") != ACTIVE_STATUS or zone_id is None:
            row.setdefault("放行状态", "")
            row["只读"] = False
        elif winner_by_zone.get(zone_id) == int(row["id"]):
            row["放行状态"] = "放行"
            row["只读"] = False
        else:
            row["放行状态"] = "只读"
            row["只读"] = True
            row["只读原因"] = (
                f"同区域已有优先级更高的生效许可（{_winner_code(rows, winner_by_zone[zone_id])}），本许可暂停放行"
            )
    return rows


def _winner_code(rows: list[dict[str, Any]], winner_id: int) -> str:
    for row in rows:
        if int(row.get("id", 0)) == winner_id:
            return str(row.get("许可编号") or winner_id)
    return str(winner_id)


def _scoped_rows(role_code: str) -> list[dict[str, Any]]:
    scope = authorized_zone_ids(role_code)
    rows = store.rows(MODULE)
    if scope is not None:
        rows = [row for row in rows if _zone_id(row) in scope]
    return dedupe_permits(rows)


class PermitService:
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
            rows = [row for row in rows if keyword in str(row.get("许可编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        annotate_locks(rows)
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
        code = str(values["许可编号"]).strip()
        if any(str(row.get("许可编号") or "").strip() == code for row in rows):
            raise ValueError(f"许可编号 {code} 已存在，同一许可不能重复登记")
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["安全区域ID"] = values.get("安全区域ID")
        entry["优先级"] = int(values.get("优先级") or 50)
        entry["工作负责人"] = values.get("工作负责人", "")
        entry["安全措施"] = values.get("安全措施", "")
        entry["许可时间"] = values.get("许可时间", "")
        entry["有效期至"] = values.get("有效期至", "")
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
            return None, f"作业许可单 {entry_id} 不存在或已归档"

        # 功能级权限：维护人员等只读角色不能动许可流程
        if not can(role_code, "permit_action"):
            raise PermissionError(
                f"越权提交已拒绝：{role_label(role_code)}只有查看权限，不能执行「{action}」"
            )
        # 数据级权限：许可不在授权区域内
        if not zone_in_scope(role_code, _zone_id(entry)):
            raise PermissionError(
                f"越权提交已拒绝：许可 {entry.get('许可编号')} 不在{role_label(role_code)}的授权区域内"
            )
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于作业许可可执行范围"

        # 区域内优先级互斥：非放行许可只能只读，动作一律拦下
        scoped = annotate_locks(_scoped_rows(role_code))
        annotated = next((row for row in scoped if int(row["id"]) == entry_id), None)
        if annotated is not None and annotated.get("只读"):
            return None, f"提交已拒绝：{annotated.get('只读原因', '该许可当前为只读状态')}"

        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target not in {STATUS_ORDER[-1], ACTIVE_STATUS}
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"作业许可单已{action}"
