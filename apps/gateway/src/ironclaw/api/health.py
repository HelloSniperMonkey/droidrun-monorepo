"""
Health check endpoints for Iron Claw Gateway.
"""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "service": "ironclaw-gateway"}


@router.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Iron Claw Gateway",
        "version": "0.1.0",
        "description": "Mobile-First Autonomous Agent Architecture",
        "endpoints": {
            "health": "/health",
            "jobs": "/api/v1/jobs",
            "alarms": "/api/v1/alarms",
            "wake": "/api/v1/wake",
        },
    }
