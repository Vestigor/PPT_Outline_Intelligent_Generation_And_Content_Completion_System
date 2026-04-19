from __future__ import annotations

from fastapi import APIRouter

from app.modules.user.controller.user_controller import router as user_router
from app.modules.knowledge_base.controller.knowledge_base_controller import router as knowledge_router
from app.modules.model.controller.model_controller import router as model_router
from app.modules.session.controller.session_controller import router as session_router
# from app.modules.task.controller.task_controller import router as task_router

api_router = APIRouter()

api_router.include_router(user_router)
api_router.include_router(knowledge_router)
api_router.include_router(model_router)
api_router.include_router(session_router)
# api_router.include_router(task_router)
