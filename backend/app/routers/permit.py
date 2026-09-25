"""作业许可接口：维护作业许可单，覆盖提交申请、签发许可、驳回申请等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.security import current_role
from app.services.permit import PermitService

router = APIRouter(prefix="/api/permit", tags=["作业许可"])

service = PermitService()

LIST_FIELDS = ["许可编号", "作业类型", "作业地点", "工作负责人", "安全措施", "许可时间", "有效期至", "许可状态"]
STATUSES = ["待申请", "已受理", "已许可", "已驳回", "已过期"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按许可编号检索"),
    status: str | None = Query(default=None, description="待申请、已受理、已许可、已驳回、已过期"),
    page: int = 1,
    size: int = 20,
    role_code: str = Depends(current_role),
) -> PageResult[dict]:
    """按许可编号与状态过滤作业许可列表；只返回当前角色授权区域内的许可。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(role_code=role_code, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条作业许可单明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"作业许可单 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条作业许可单，缺字段或编号重复时说明原因而不是静默丢弃。老流程不变。"""
    try:
        entry, missing = service.create_entry(payload.values)
    except ValueError as exc:
        return ActionResult(ok=False, message=str(exc))
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="作业许可单已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    role_code: str = Depends(current_role),
) -> ActionResult:
    """对单条作业许可单执行提交申请、签发许可、驳回申请。

    越权提交（只读角色、区域未授权、许可被优先级互斥置为只读）一律拒绝并说明原因。
    """
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(role_code, entry_id, action)
    except PermissionError as exc:
        # 越权提交：说明原因后以 403 拒绝
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)


@router.get("/export")
def export_entries(role_code: str = Depends(current_role)) -> dict[str, Any]:
    """导出作业许可清单：只导出当前角色授权区域内的全量数据。"""
    items, total = service.list_entries(role_code=role_code, page=1, size=10000)
    return {"module": "permit", "total": total, "items": items}
