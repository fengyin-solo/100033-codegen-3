"""安全区域管控的角色模型与授权口径。

前端通过请求头 ``X-Operator-Role`` 告知当前登录角色；没有带头时按值班管理员处理，
保证老页面、老脚本在不感知角色时仍能按全量口径工作。
"""
from __future__ import annotations

from typing import Any

from fastapi import Header, HTTPException

from app.store import store

# 角色编码 -> 展示信息与权限开关
ROLE_CATALOG: dict[str, dict[str, Any]] = {
    "duty_admin": {
        "label": "值班管理员",
        "scope": "全站安全区域",
        "permissions": {
            "zone_view_all": True,
            "zone_edit": True,
            "grant_edit": True,
            "permit_action": True,
            "alarm_action": True,
        },
    },
    "safety_officer": {
        "label": "安全员",
        "scope": "被授权安全区域",
        "permissions": {
            "zone_view_all": True,
            "zone_edit": False,
            "grant_edit": False,
            "permit_action": True,
            "alarm_action": True,
        },
    },
    "contractor_lead": {
        "label": "外委检修负责人",
        "scope": "被授权安全区域",
        "permissions": {
            "zone_view_all": False,
            "zone_edit": False,
            "grant_edit": False,
            "permit_action": True,
            "alarm_action": False,
        },
    },
    "maintainer": {
        "label": "维护人员",
        "scope": "被授权安全区域（只读）",
        "permissions": {
            "zone_view_all": False,
            "zone_edit": False,
            "grant_edit": False,
            "permit_action": False,
            "alarm_action": False,
        },
    },
}


def resolve_role(role_code: str | None) -> str:
    """把请求头里的角色归一化；传了不认识的角色直接 400，不悄悄降级。"""
    code = (role_code or "duty_admin").strip()
    if code not in ROLE_CATALOG:
        raise HTTPException(status_code=400, detail=f"未知角色：{code}，请重新选择登录身份")
    return code


def current_role(x_operator_role: str | None = Header(default=None)) -> str:
    """FastAPI 依赖：解析当前请求角色。"""
    return resolve_role(x_operator_role)


def role_label(role_code: str) -> str:
    return str(ROLE_CATALOG[role_code]["label"])


def can(role_code: str, permission: str) -> bool:
    return bool(ROLE_CATALOG[role_code]["permissions"].get(permission))


def authorized_zone_ids(role_code: str) -> set[int] | None:
    """角色可访问的区域集合；返回 None 表示全站可见，不受围栏限制。"""
    if can(role_code, "zone_view_all"):
        return None
    return {
        int(row["安全区域ID"])
        for row in store.rows("zone_grant")
        if row.get("角色编码") == role_code and row.get("安全区域ID") is not None
    }


def zone_in_scope(role_code: str, zone_id: Any) -> bool:
    """判断某个区域是否在角色授权范围内；记录未绑定区域时按越权处理。"""
    scope = authorized_zone_ids(role_code)
    if scope is None:
        return True
    try:
        return int(zone_id) in scope
    except (TypeError, ValueError):
        return False


def require_permission(role_code: str, permission: str, resource: str) -> None:
    """没有功能权限时统一抛 403，并说明被拒原因。"""
    if not can(role_code, permission):
        raise HTTPException(
            status_code=403,
            detail=f"越权操作已拒绝：{role_label(role_code)}无权{resource}，请联系值班管理员",
        )


def require_zone_scope(role_code: str, zone_id: Any, resource: str) -> None:
    """资源不在授权区域时抛 403，并说明缺的是哪个区域的授权。"""
    if zone_in_scope(role_code, zone_id):
        return
    raise HTTPException(
        status_code=403,
        detail=f"越权操作已拒绝：{resource}不在{role_label(role_code)}的授权区域内",
    )
