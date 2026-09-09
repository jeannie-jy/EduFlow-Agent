"""API 主路由聚合。

所有路由按模块拆分，统一在 api_router 下注册。
"""

from fastapi import APIRouter, Depends

from .admin import router as admin_router
from .audit import router as audit_router
from .auth import require_project_owner
from .auth import router as auth_router
from .export import router as export_router
from .feedback import router as feedback_router
from .frames import router as frames_router
from .generate import router as generate_router
from .jobs import router as jobs_router
from .knowledge import router as knowledge_router
from .materials import router as materials_router
from .parameters import router as parameters_router
from .projects import router as projects_router
from .traces import router as traces_router
from .versions import router as versions_router

api_router = APIRouter()
protected_router = APIRouter(dependencies=[Depends(require_project_owner)])

# Auth 与 ping 公开；业务 API 在 AUTH_REQUIRED=true 时统一要求有效会话。
api_router.include_router(auth_router)
api_router.include_router(admin_router)
protected_router.include_router(projects_router)
protected_router.include_router(generate_router)
protected_router.include_router(frames_router)
protected_router.include_router(parameters_router)
protected_router.include_router(knowledge_router)
protected_router.include_router(feedback_router)
protected_router.include_router(export_router)
protected_router.include_router(materials_router)
protected_router.include_router(versions_router)
protected_router.include_router(jobs_router)
protected_router.include_router(traces_router)
protected_router.include_router(audit_router)
api_router.include_router(protected_router)


@api_router.get("/ping")
async def ping() -> dict[str, str]:
    """轻量 ping 检查。"""
    return {"ping": "pong"}
