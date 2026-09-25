"""安全区域管控接口：电子围栏、角色授权、越界告警与安全看板。

写操作只有值班管理员能做：
- 维护人员/外委/安全员改围栏或授权时返回 403 并说明原因；
- 越界告警的看板按各自授权区域返回，值班管理员额外收到待提醒通知。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload
from app.security import (
    ROLE_CATALOG,
    current_role,
    require_permission,
    require_zone_scope,
    role_label,
)
from app.services.safety import SafetyService

router = APIRouter(prefix="/api/safety", tags=["安全区域管控"])

service = SafetyService()


@router.get("/me")
def current_identity(role_code: str = Depends(current_role)) -> dict[str, object]:
    """返回当前角色、名称与权限清单，前端按它决定按钮显隐。"""
    return {
        "角色编码": role_code,
        "角色名称": role_label(role_code),
        "授权范围": ROLE_CATALOG[role_code]["scope"],
        "permissions": ROLE_CATALOG[role_code]["permissions"],
    }


@router.get("/roles")
def list_roles() -> dict[str, object]:
    """角色目录：前端角色切换与授权下拉共用。"""
    return {
        "roles": [
            {"角色编码": code, "角色名称": info["label"], "授权范围": info["scope"]}
            for code, info in ROLE_CATALOG.items()
        ]
    }


@router.get("/dashboard")
def safety_dashboard(role_code: str = Depends(current_role)) -> dict[str, object]:
    """安全看板：卡片与明细都按当前角色授权区域过滤。"""
    return service.dashboard(role_code)


# ---------------- 电子围栏 ----------------

@router.get("/zones")
def list_zones(role_code: str = Depends(current_role)) -> dict[str, object]:
    return {"items": service.list_zones(role_code), "total": len(service.list_zones(role_code))}


@router.post("/zones", response_model=ActionResult)
def save_zone(payload: EntryPayload, role_code: str = Depends(current_role)) -> ActionResult:
    """划定或调整电子围栏；维护人员等只读角色被拒，必须说明原因。"""
    require_permission(role_code, "zone_edit", "划定或修改电子围栏边界")
    entry, message = service.save_zone(payload.values)
    return ActionResult(ok=entry is not None, message=message, entry=entry)


# ---------------- 角色授权 ----------------

@router.get("/grants")
def list_grants(
    role: str | None = Query(default=None, description="按角色编码过滤"),
    role_code: str = Depends(current_role),
) -> dict[str, object]:
    return {"items": service.list_grants(role)}


@router.post("/grants", response_model=ActionResult)
def save_grant(payload: EntryPayload, role_code: str = Depends(current_role)) -> ActionResult:
    """给角色分配授权区域；只有值班管理员能分配。"""
    require_permission(role_code, "grant_edit", "给角色分配授权区域")
    entry, message = service.save_grant(payload.values)
    return ActionResult(ok=entry is not None, message=message, entry=entry)


@router.delete("/grants/{grant_id}", response_model=ActionResult)
def revoke_grant(grant_id: int, role_code: str = Depends(current_role)) -> ActionResult:
    """收回某角色对某区域的授权。"""
    require_permission(role_code, "grant_edit", "收回角色的授权区域")
    ok, message = service.revoke_grant(grant_id)
    return ActionResult(ok=ok, message=message)


# ---------------- 越界告警 ----------------

@router.get("/boundary-alarms")
def list_boundary_alarms(
    status: str | None = Query(default=None, description="待提醒、已提醒、已处置"),
    role_code: str = Depends(current_role),
) -> dict[str, object]:
    """越界告警独立查询，不进普通告警列表。"""
    items = service.list_boundary_alarms(role_code, status=status)
    return {"items": items, "total": len(items)}


@router.post("/boundary-alarms/report", response_model=ActionResult)
def report_position(payload: EntryPayload, role_code: str = Depends(current_role)) -> ActionResult:
    """作业人员定位上报，越界自动生成告警并提醒值班管理员。"""
    zone_id_raw = payload.values.get("安全区域ID")
    try:
        zone_id = int(zone_id_raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="安全区域ID缺失或不是整数")
    require_zone_scope(role_code, zone_id, "该作业区域的定位上报")
    entry, message, crossed = service.report_position(
        role_code,
        zone_id,
        str(payload.values.get("越界人员") or ""),
        payload.values.get("定位坐标"),
    )
    return ActionResult(ok=entry is not None, message=message, entry=entry)


@router.post("/boundary-alarms/{alarm_id}/ack", response_model=ActionResult)
def acknowledge_boundary(
    alarm_id: int, payload: EntryPayload, role_code: str = Depends(current_role)
) -> ActionResult:
    """值班人处置越界告警；处置说明写在 remark/values.note 里。"""
    require_permission(role_code, "alarm_action", "处置越界告警")
    note = str(payload.values.get("note") or payload.remark or "")
    entry, message = service.acknowledge_boundary(alarm_id, note)
    return ActionResult(ok=entry is not None, message=message, entry=entry)
