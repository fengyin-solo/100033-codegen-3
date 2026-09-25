"""告警中心接口：维护告警事件，覆盖确认告警、处置告警、忽略告警等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.security import current_role
from app.services.alarm import AlarmService

router = APIRouter(prefix="/api/alarm", tags=["告警中心"])

service = AlarmService()

LIST_FIELDS = ["告警编号", "告警类型", "告警等级", "触发设备", "触发时间", "确认人员", "处置说明", "告警状态"]
STATUSES = ["待确认", "已确认", "已处置", "已忽略"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按告警编号检索"),
    status: str | None = Query(default=None, description="待确认、已确认、已处置、已忽略"),
    page: int = 1,
    size: int = 20,
    role_code: str = Depends(current_role),
) -> PageResult[dict]:
    """按告警编号与状态过滤普通告警列表；越界告警不在此列表，且只返回授权区域内数据。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(role_code=role_code, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条告警事件明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"告警事件 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条告警事件，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="告警事件已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    role_code: str = Depends(current_role),
) -> ActionResult:
    """对单条普通告警执行确认、处置、忽略；越权提交会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(role_code, entry_id, action)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries(role_code: str = Depends(current_role)) -> dict[str, Any]:
    """导出普通告警清单：只导出授权区域内数据，不含越界告警。"""
    items, total = service.list_entries(role_code=role_code, page=1, size=10000)
    return {"module": "alarm", "total": total, "items": items}
