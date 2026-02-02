"""API v1 router combining all endpoint routers."""

from fastapi import APIRouter

from app.api.v1 import auth, comments, health_check, issues, projects

router = APIRouter()

# Include all routers
router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(issues.router, tags=["Issues"])
router.include_router(comments.router, tags=["Comments"])
router.include_router(health_check.router, prefix="/health-check", tags=["Health Check"])
