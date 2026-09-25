"""安全区域管控接口：电子围栏圈定、角色授权、越界告警看板与围栏调整。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.zone import ZoneService

router = APIRouter(prefix="/api/zone", tags=["安全区域"])

service = ZoneService()

LIST_FIELDS = ["区域编号", "区域名称", "作业地点", "围栏范围", "授权角色", "值班人", "区域状态"]


@router.get("/dashboard")
def dashboard(role: str | None = Query(default=None, description="按角色返回授权范围")) -> dict[str, Any]:
    """看板：授权区域、越界告警与生效许可都按角色圈定，返回后授权范围与角色保持一致。"""
    return service.dashboard(role=role)


@router.get("/alarms")
def boundary_alarms(role: str | None = Query(default=None, description="按角色过滤授权区域")) -> dict[str, Any]:
    """越界告警单独列出并提醒值班人，不在普通告警列表里显示。"""
    items = service.boundary_alarms(role=role)
    return {"module": "zone", "total": len(items), "items": items}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出安全区域清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "zone", "total": total, "items": items}


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按区域编号检索"),
    status: str | None = Query(default=None, description="启用、停用"),
    role: str | None = Query(default=None, description="按角色过滤授权区域"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按区域编号与状态过滤安全区域列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(role=role, keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条安全区域明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"安全区域 {entry_id} 不存在或已撤销")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(
    payload: EntryPayload,
    role: str | None = Query(default=None, description="提交人角色"),
) -> ActionResult:
    """圈定一片安全区域，缺字段或越权时说明原因而不是静默丢弃。"""
    entry, errors = service.create_entry(payload.values, role=role)
    if errors:
        return ActionResult(ok=False, message="；".join(errors))
    return ActionResult(ok=True, message="安全区域已圈定", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    role: str | None = Query(default=None, description="操作人角色"),
) -> ActionResult:
    """调整电子围栏边界；维护人员等越权操作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    if action != "调整围栏":
        return ActionResult(ok=False, message=f"动作「{action}」不属于安全区域可执行范围")
    entry, message = service.adjust_boundary(entry_id, role or "", payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
