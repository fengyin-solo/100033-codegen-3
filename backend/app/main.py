"""光伏电站智能运维平台 后端服务入口。

启动：uvicorn app.main:app --host 127.0.0.1 --port 8000
健康检查：GET /api/health
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import ROUTERS
from app.security import authorized_zone_ids, current_role, role_label
from app.store import store

app = FastAPI(title="光伏电站智能运维平台", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in ROUTERS:
    app.include_router(module.router)


@app.get("/api/health")
def health() -> dict[str, object]:
    """健康检查：确认服务已经监听、示例数据已经就绪。"""
    return {"ok": True, "app": settings.app_name, "modules": len(store.module_names())}


@app.get("/api/overview")
def overview(role_code: str = Depends(current_role)) -> dict[str, object]:
    """运营概览：把各业务模块的待处理量汇总成看板卡片。

    接入安全区域后，许可、告警与越界告警按当前角色授权区域汇总，
    其余模块沿用全量口径；越界告警单独成卡，不并入普通告警。
    """
    data = store.overview()
    scope = authorized_zone_ids(role_code)
    if scope is not None:
        for module in data["modules"]:
            if module["name"] not in {"permit", "alarm"}:
                continue
            rows = [
                row for row in store.rows(module["name"])
                if int(row.get("安全区域ID", -1)) in scope
            ]
            module["created"] = len(rows)
            module["pending"] = sum(1 for row in rows if row.get("pending"))
            module["abnormal"] = sum(1 for row in rows if row.get("abnormal"))
        data["cards"] = [
            {"label": "业务模块", "value": len(data["modules"])},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in data["modules"])},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in data["modules"])},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in data["modules"])},
        ]

    boundary_rows = store.rows("boundary_alarm")
    if scope is not None:
        boundary_rows = [row for row in boundary_rows if int(row.get("安全区域ID", -1)) in scope]
    data["scope"] = {
        "角色": role_label(role_code),
        "授权范围": "全站安全区域" if scope is None else f"已授权 {len(scope)} 个安全区域",
    }
    data["boundary_pending"] = sum(1 for row in boundary_rows if row.get("状态") == "待提醒")
    return data
