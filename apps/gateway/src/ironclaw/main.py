"""
FastAPI main application entry point for Iron Claw Gateway.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import alarms, health, hitl, jobs, tabs, wake, chat, chat_cloud, speech, mobilerun, mobilerun_ws
from .utils.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ironclaw")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🦾 Iron Claw Gateway starting up...")
    settings = get_settings()

    # Log configuration (no secrets!)
    logger.info(f"Device: {settings.device_serial or 'auto-detect'}")
    logger.info(f"TCP Mode: {settings.use_tcp}")
    logger.info(f"Vapi configured: {bool(settings.vapi_api_key)}")
    logger.info(f"Telegram configured: {bool(settings.telegram_bot_token)}")

    yield

    logger.info("🦾 Iron Claw Gateway shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Iron Claw Gateway",
        description="Mobile-First Autonomous Agent Architecture",
        version="0.1.0",
        lifespan=lifespan,
        debug=settings.debug,
    )

    # CORS middleware - allow common dev ports
    origins = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8000",
        "http://localhost:8080",
    ]
    if settings.debug:
        origins = ["*"]  # Allow all origins in debug mode

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True
        if origins != ["*"]
        else False,  # credentials can't be used with wildcard
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Job Hunter"])
    app.include_router(alarms.router, prefix="/api/v1/alarms", tags=["Temporal Guardian"])
    app.include_router(tabs.router, prefix="/api/v1/tabs", tags=["Tab Manager"])
    app.include_router(wake.router, prefix="/api/v1/wake", tags=["Active Interrupter"])
    app.include_router(hitl.router, prefix="/api/v1/hitl", tags=["Human-in-the-Loop"])
    app.include_router(chat.router, prefix="/api", tags=["Chat & Web"])
    app.include_router(chat_cloud.router, prefix="/api", tags=["Cloud Chat"])
    app.include_router(speech.router, prefix="/api/v1/speech", tags=["Speech-to-Text"])
    app.include_router(mobilerun.router, prefix="/api/v1/mobilerun", tags=["MobileRun Cloud"])
    app.include_router(mobilerun_ws.router, prefix="/api/v1/mobilerun", tags=["MobileRun WebSocket"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "ironclaw.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
