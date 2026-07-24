"""API 主路由聚合。

所有路由按模块拆分，统一在 api_router 下注册。
"""

from fastapi import APIRouter

from .projects import router as projects_router
from .generate import router as generate_router
from .frames import router as frames_router
from .parameters import router as parameters_router
from .knowledge import router as knowledge_router
from .feedback import router as feedback_router
from .export import router as export_router
from .materials import router as materials_router
from .versions import router as versions_router
from .auth import router as auth_router

api_router = APIRouter()

# 注册子路由
api_router.include_router(projects_router)
api_router.include_router(generate_router)
api_router.include_router(frames_router)
api_router.include_router(parameters_router)
api_router.include_router(knowledge_router)
api_router.include_router(feedback_router)
api_router.include_router(export_router)
api_router.include_router(materials_router)
api_router.include_router(versions_router)
api_router.include_router(auth_router)


@api_router.get("/ping")
async def ping() -> dict[str, str]:
    """轻量 ping 检查。"""
    return {"ping": "pong"}
