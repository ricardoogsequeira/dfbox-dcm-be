from fastapi import APIRouter

from app.api.routes.allocations import router as allocations_router
from app.api.routes.capacity import router as capacity_router
from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router
from app.api.routes.projects import router as projects_router
from app.api.routes.resources import router as resources_router
from app.api.routes.settings import router as settings_router
from app.api.routes.supporting import router as supporting_router

api_router = APIRouter()
api_router.include_router(allocations_router)
api_router.include_router(capacity_router)
api_router.include_router(chat_router)
api_router.include_router(health_router, tags=["health"])
api_router.include_router(projects_router)
api_router.include_router(resources_router)
api_router.include_router(settings_router)
api_router.include_router(supporting_router)
