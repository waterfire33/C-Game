from fastapi import APIRouter

from app.api.routes import auth, health, mcp, planner, workflows
from app.api.routes import tools

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workflows.router, prefix="/workflows", tags=["workflows"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(mcp.router, prefix="/mcp", tags=["mcp"])
api_router.include_router(planner.router, prefix="/agent", tags=["agent"])
