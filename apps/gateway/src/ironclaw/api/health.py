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
            "chat": "/api/chat",
            "chat_cloud": "/api/chat-cloud",
            "chat_cloud_tasks": "/api/chat-cloud/tasks/{task_id}",
            "chat_cloud_devices": "/api/chat-cloud/devices",
            "upload": "/api/upload",
            "transcribe": "/api/transcribe",
            "schedule_call": "/api/schedule-call",
            "jobs": "/api/v1/jobs",
            "alarms": "/api/v1/alarms",
            "tabs": "/api/v1/tabs",
            "wake": "/api/v1/wake",
            "hitl": "/api/v1/hitl",
            "speech": "/api/v1/speech",
            "mobilerun": "/api/v1/mobilerun",
            "openclaw_webhook": "/openclaw/webhook",
            "openclaw_tasks": "/openclaw/tasks",
        },
        "documentation": {
            "mcp_skill": "/.agents/skills/ironclaw-mcp/",
            "integration_guide": "/.agents/skills/ironclaw-mcp/INTEGRATION.md",
            "cloud_agent_guide": "/.agents/skills/ironclaw-mcp/CLOUD_AGENT.md",
            "openclaw_prompt": "/.agents/skills/ironclaw-mcp/OPENCLAW_PROMPT.md",
        },
    }
