"""
OpenClaw Webhook API Router for Iron Claw.

Provides the webhook endpoint for receiving tasks from OpenClaw:
- POST /openclaw/webhook - Main webhook receiver with token auth
- GET /openclaw/tasks - List all tasks (admin)
- GET /openclaw/tasks/{run_id} - Get task status by run_id
"""

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

from ..services.openclaw_service import (
    WebhookRequest,
    WebhookResponse,
    TaskInfo,
    TaskStatus,
    init_openclaw_service,
    get_openclaw_service,
)

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[6]  # Navigate up to monorepo root
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Fallback: try to find .env by walking up directories
    current = Path(__file__).resolve().parent
    while current != current.parent:
        potential_env = current / ".env"
        if potential_env.exists():
            load_dotenv(potential_env)
            break
        current = current.parent

logger = logging.getLogger("ironclaw.api.openclaw")
router = APIRouter()


# Initialize service on module load
def _get_hook_token() -> str:
    """Get the OpenClaw hook token from environment."""
    token = os.getenv("OPENCLAW_HOOK_TOKEN")
    if not token:
        # Fallback to a default dev token (should be set in production)
        token = os.getenv("IRONCLAW_WEBHOOK_TOKEN", "dev-token-change-me")
        logger.warning(
            "OPENCLAW_HOOK_TOKEN not set, using fallback. "
            "Set OPENCLAW_HOOK_TOKEN in .env for production!"
        )
    return token


# Initialize service
try:
    _service = init_openclaw_service(_get_hook_token())
except Exception as e:
    logger.error(f"Failed to initialize OpenClaw service: {e}")
    _service = None


class TaskListResponse(BaseModel):
    """Response for listing tasks."""
    ok: bool
    tasks: list[TaskInfo]
    total: int


class TaskStatusRequest(BaseModel):
    """Request to query task status."""
    runId: Optional[str] = None
    taskId: Optional[str] = None


@router.post("/webhook", response_model=WebhookResponse, status_code=202)
async def openclaw_webhook(
    payload: WebhookRequest,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Receive webhook from OpenClaw.

    This endpoint accepts tasks from OpenClaw for execution by Iron Claw.

    **Authentication:**
    - Requires `Authorization: Bearer <token>` header
    - Token must match `OPENCLAW_HOOK_TOKEN` environment variable

    **Request Types:**
    - `execute-step`: Queue a step for execution
    - `query-status`: Get status of a running task
    - `cancel-task`: Cancel a pending/running task

    **Response:**
    - 202: Task accepted and queued
    - 401: Missing authorization header
    - 403: Invalid token
    - 400: Invalid request payload
    """
    if _service is None:
        raise HTTPException(
            status_code=500,
            detail="OpenClaw service not initialized",
        )

    # Log incoming request (structured JSON logging)
    logger.info(
        "Received OpenClaw webhook",
        extra={
            "task_id": payload.taskId,
            "type": payload.type,
            "step_type": payload.payload.stepType,
            "source": payload.metadata.source if payload.metadata else "unknown",
        },
    )

    # Handle the webhook
    response = await _service.handle_webhook(payload, authorization)

    # Return appropriate HTTP status
    if not response.ok:
        if "authorization" in (response.error or "").lower():
            raise HTTPException(status_code=401, detail=response.error)
        elif "invalid" in (response.error or "").lower() and "token" in (response.error or "").lower():
            raise HTTPException(status_code=403, detail=response.error)
        else:
            raise HTTPException(status_code=400, detail=response.error)

    return response


@router.get("/tasks", response_model=TaskListResponse)
async def list_tasks(
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    List all OpenClaw tasks.

    **Query Parameters:**
    - `limit`: Maximum number of tasks to return (default: 100)
    - `status`: Filter by task status (pending, queued, running, completed, failed, cancelled)

    **Authentication:**
    - Requires `Authorization: Bearer <token>` header
    """
    if _service is None:
        raise HTTPException(
            status_code=500,
            detail="OpenClaw service not initialized",
        )

    if not _service.validate_token(authorization):
        raise HTTPException(status_code=403, detail="Invalid or missing authorization token")

    tasks = _service.get_all_tasks(limit=limit)

    # Filter by status if specified
    if status:
        try:
            status_enum = TaskStatus(status)
            tasks = [t for t in tasks if t.status == status_enum]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in TaskStatus]}",
            )

    return TaskListResponse(
        ok=True,
        tasks=tasks,
        total=len(tasks),
    )


@router.get("/tasks/{run_id}", response_model=WebhookResponse)
async def get_task_status(
    run_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Get status of a specific task by run_id.

    **Path Parameters:**
    - `run_id`: The unique run ID returned when the task was queued

    **Authentication:**
    - Requires `Authorization: Bearer <token>` header
    """
    if _service is None:
        raise HTTPException(
            status_code=500,
            detail="OpenClaw service not initialized",
        )

    if not _service.validate_token(authorization):
        raise HTTPException(status_code=403, detail="Invalid or missing authorization token")

    task = _service.get_task_status(run_id)

    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {run_id}")

    return WebhookResponse(
        ok=True,
        runId=task.run_id,
        status=task.status.value,
        message=task.error if task.status == TaskStatus.FAILED else None,
    )


@router.delete("/tasks/{run_id}", response_model=WebhookResponse)
async def cancel_task(
    run_id: str,
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Cancel a pending or running task.

    **Path Parameters:**
    - `run_id`: The unique run ID of the task to cancel

    **Authentication:**
    - Requires `Authorization: Bearer <token>` header
    """
    if _service is None:
        raise HTTPException(
            status_code=500,
            detail="OpenClaw service not initialized",
        )

    if not _service.validate_token(authorization):
        raise HTTPException(status_code=403, detail="Invalid or missing authorization token")

    # Create a cancel request
    from ..services.openclaw_service import WebhookPayload, StepParams

    cancel_request = WebhookRequest(
        taskId=run_id,
        type="cancel-task",
        payload=WebhookPayload(
            stepType="cancel",
            params=StepParams(extra={"runId": run_id}),
        ),
    )

    # Use internal handler (already validated token)
    response = await _service._handle_cancel_task(cancel_request)

    if not response.ok:
        raise HTTPException(status_code=400, detail=response.error)

    return response


# Health check for the OpenClaw integration
@router.get("/health")
async def openclaw_health():
    """
    Health check for OpenClaw webhook integration.

    Returns service status and configuration info.
    """
    return {
        "ok": True,
        "service": "openclaw-webhook",
        "status": "ready" if _service else "not_initialized",
        "version": "1.0.0",
    }
