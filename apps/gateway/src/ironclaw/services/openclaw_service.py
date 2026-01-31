"""
OpenClaw Webhook Service for Iron Claw.

Handles incoming webhook messages from OpenClaw and converts them
to internal jobs/tasks for execution by Iron Claw agents.

The flow:
1. OpenClaw sends webhook with task data -> POST /openclaw/webhook
2. OpenClawService validates token and parses payload
3. Task is enqueued to the job queue for processing
4. Async response with runId returned immediately
5. Task is processed and results can be queried via status endpoint
6. Telegram notification sent for visibility
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("ironclaw.services.openclaw")


class TaskStatus(str, Enum):
    """Status of an OpenClaw task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(str, Enum):
    """Types of steps that can be executed."""
    HTTP_ACTION = "http_action"
    SCRIPT = "script"
    CLICK = "click"
    EXTRACT = "extract"
    LOG = "log"
    MOBILE_ACTION = "mobile_action"


class WebhookMetadata(BaseModel):
    """Metadata for incoming webhook."""
    source: str = "openclaw"
    timestamp: Optional[str] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None


class StepParams(BaseModel):
    """Parameters for a step execution."""
    url: Optional[str] = None
    method: Optional[str] = None
    body: Optional[dict] = None
    message: Optional[str] = None
    selector: Optional[str] = None
    action: Optional[str] = None
    extra: Optional[dict] = Field(default_factory=dict)

    class Config:
        extra = "allow"


class WebhookPayload(BaseModel):
    """Payload section of webhook request."""
    stepType: str
    params: StepParams = Field(default_factory=StepParams)

    class Config:
        extra = "allow"


class WebhookRequest(BaseModel):
    """Full webhook request from OpenClaw."""
    taskId: str
    type: str  # execute-step, query-status, cancel-task
    metadata: Optional[WebhookMetadata] = None
    payload: WebhookPayload

    class Config:
        extra = "allow"


class TaskInfo(BaseModel):
    """Information about an enqueued task."""
    run_id: str
    task_id: str
    status: TaskStatus
    created_at: str
    updated_at: str
    step_type: str
    result: Optional[dict] = None
    error: Optional[str] = None


class WebhookResponse(BaseModel):
    """Response for webhook request."""
    ok: bool
    runId: Optional[str] = None
    status: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


# In-memory storage (use Redis/PostgreSQL in production)
_task_queue: dict[str, TaskInfo] = {}
_task_processors: list[Callable[[TaskInfo, WebhookRequest], Awaitable[dict]]] = []


class TelegramNotifier:
    """Helper class to send Telegram notifications."""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send a message to Telegram."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing)")
            return False
        
        try:
            client = await self._get_client()
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            response = await client.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
            })
            
            if response.status_code == 200:
                logger.info("Telegram notification sent successfully")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.exception(f"Failed to send Telegram message: {e}")
            return False


# Global notifier instance
_telegram_notifier: Optional[TelegramNotifier] = None


def get_telegram_notifier() -> TelegramNotifier:
    """Get or create the Telegram notifier singleton."""
    global _telegram_notifier
    if _telegram_notifier is None:
        _telegram_notifier = TelegramNotifier()
    return _telegram_notifier


class OpenClawService:
    """
    OpenClaw Webhook Service.

    Handles:
    - Token validation for incoming requests
    - Task queueing and status management
    - Mapping webhook payloads to internal job queue
    - Result aggregation and reporting

    Usage:
        service = OpenClawService(hook_token="secret")

        # Register a task processor
        service.register_processor(my_processor)

        # Handle incoming webhook
        response = await service.handle_webhook(request, auth_header)

        # Query task status
        task = service.get_task_status(run_id)
    """

    def __init__(self, hook_token: str):
        """
        Initialize OpenClaw service.

        Args:
            hook_token: Secret token for validating incoming webhooks
        """
        self.hook_token = hook_token
        self._lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

    def validate_token(self, authorization: Optional[str]) -> bool:
        """
        Validate the Authorization header.

        Args:
            authorization: The Authorization header value

        Returns:
            True if valid, False otherwise
        """
        if not authorization:
            return False

        if not authorization.startswith("Bearer "):
            return False

        token = authorization.split(" ", 1)[1]
        return token == self.hook_token

    def register_processor(
        self, processor: Callable[[TaskInfo, WebhookRequest], Awaitable[dict]]
    ) -> None:
        """
        Register a task processor callback.

        The processor receives the TaskInfo and original WebhookRequest,
        and should return a dict with the result.
        """
        _task_processors.append(processor)
        logger.info(f"Registered OpenClaw processor: {processor.__name__}")

    async def handle_webhook(
        self,
        request: WebhookRequest,
        authorization: Optional[str] = None,
    ) -> WebhookResponse:
        """
        Handle incoming webhook from OpenClaw.

        Args:
            request: The parsed webhook request
            authorization: The Authorization header

        Returns:
            WebhookResponse with status and runId
        """
        # Validate token
        if not self.validate_token(authorization):
            logger.warning(f"Invalid token for task {request.taskId}")
            return WebhookResponse(
                ok=False,
                error="Invalid or missing authorization token",
            )

        # Route by request type
        if request.type == "execute-step":
            return await self._handle_execute_step(request)
        elif request.type == "query-status":
            return await self._handle_query_status(request)
        elif request.type == "cancel-task":
            return await self._handle_cancel_task(request)
        else:
            logger.warning(f"Unknown request type: {request.type}")
            return WebhookResponse(
                ok=False,
                error=f"Unknown request type: {request.type}",
            )

    async def _handle_execute_step(self, request: WebhookRequest) -> WebhookResponse:
        """Handle execute-step request."""
        run_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Create task info
        task_info = TaskInfo(
            run_id=run_id,
            task_id=request.taskId,
            status=TaskStatus.QUEUED,
            created_at=now,
            updated_at=now,
            step_type=request.payload.stepType,
        )

        # Store in queue
        async with self._lock:
            _task_queue[run_id] = task_info

        logger.info(
            f"Enqueued task {request.taskId} as {run_id}",
            extra={
                "run_id": run_id,
                "task_id": request.taskId,
                "step_type": request.payload.stepType,
                "source": request.metadata.source if request.metadata else "unknown",
            },
        )

        # Start background processing
        task = asyncio.create_task(self._process_task(task_info, request))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

        return WebhookResponse(
            ok=True,
            runId=run_id,
            status=TaskStatus.QUEUED.value,
            message=f"Task queued for execution",
        )

    async def _handle_query_status(self, request: WebhookRequest) -> WebhookResponse:
        """Handle query-status request."""
        # Look up by taskId in the payload params or use taskId from request
        extra = request.payload.params.extra or {}
        task_id_to_find = extra.get("runId") or request.taskId

        # Search for task
        task_info = None
        for run_id, info in _task_queue.items():
            if info.run_id == task_id_to_find or info.task_id == task_id_to_find:
                task_info = info
                break

        if not task_info:
            return WebhookResponse(
                ok=False,
                error=f"Task not found: {task_id_to_find}",
            )

        return WebhookResponse(
            ok=True,
            runId=task_info.run_id,
            status=task_info.status.value,
            message=task_info.error if task_info.status == TaskStatus.FAILED else None,
        )

    async def _handle_cancel_task(self, request: WebhookRequest) -> WebhookResponse:
        """Handle cancel-task request."""
        extra = request.payload.params.extra or {}
        task_id_to_cancel = extra.get("runId") or request.taskId

        # Find and cancel
        async with self._lock:
            for run_id, info in _task_queue.items():
                if info.run_id == task_id_to_cancel or info.task_id == task_id_to_cancel:
                    if info.status in (TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING):
                        info.status = TaskStatus.CANCELLED
                        info.updated_at = datetime.now(timezone.utc).isoformat()
                        logger.info(f"Cancelled task {run_id}")
                        return WebhookResponse(
                            ok=True,
                            runId=run_id,
                            status=TaskStatus.CANCELLED.value,
                            message="Task cancelled",
                        )
                    else:
                        return WebhookResponse(
                            ok=False,
                            runId=run_id,
                            error=f"Cannot cancel task in status: {info.status.value}",
                        )

        return WebhookResponse(
            ok=False,
            error=f"Task not found: {task_id_to_cancel}",
        )

    async def _process_task(self, task_info: TaskInfo, request: WebhookRequest) -> None:
        """Process a task in the background."""
        try:
            async with self._lock:
                task_info.status = TaskStatus.RUNNING
                task_info.updated_at = datetime.now(timezone.utc).isoformat()

            logger.info(f"Processing task {task_info.run_id}")

            # Execute registered processors
            result = {}
            for processor in _task_processors:
                try:
                    result = await processor(task_info, request)
                except Exception as e:
                    logger.exception(f"Processor {processor.__name__} failed: {e}")
                    result = {"error": str(e)}

            # If no processors, use default handler
            if not _task_processors:
                result = await self._default_processor(task_info, request)

            async with self._lock:
                task_info.status = TaskStatus.COMPLETED
                task_info.result = result
                task_info.updated_at = datetime.now(timezone.utc).isoformat()

            logger.info(
                f"Completed task {task_info.run_id}",
                extra={"run_id": task_info.run_id, "result": result},
            )

        except Exception as e:
            logger.exception(f"Failed to process task {task_info.run_id}: {e}")
            async with self._lock:
                task_info.status = TaskStatus.FAILED
                task_info.error = str(e)
                task_info.updated_at = datetime.now(timezone.utc).isoformat()

    async def _default_processor(
        self, task_info: TaskInfo, request: WebhookRequest
    ) -> dict:
        """Default task processor for basic step types."""
        step_type = request.payload.stepType
        params = request.payload.params
        notifier = get_telegram_notifier()

        if step_type == "log":
            # Simple log step - also send to Telegram
            message = params.message or "No message provided"
            logger.info(f"[OpenClaw Log] {message}")
            
            # Send to Telegram
            telegram_msg = (
                f"🎣 *OpenClaw Webhook Received*\n\n"
                f"*Task ID:* `{request.taskId}`\n"
                f"*Type:* `{step_type}`\n\n"
                f"📝 *Message:*\n{message}"
            )
            await notifier.send_message(telegram_msg)
            
            return {"logged": True, "message": message, "telegram_sent": True}

        elif step_type == "http_action":
            # HTTP action - could integrate with httpx
            logger.info(f"HTTP action requested: {params.method} {params.url}")
            
            # Notify Telegram
            telegram_msg = (
                f"🌐 *HTTP Action Requested*\n\n"
                f"*Task ID:* `{request.taskId}`\n"
                f"*Method:* `{params.method}`\n"
                f"*URL:* {params.url}"
            )
            await notifier.send_message(telegram_msg)
            
            return {
                "action": "http_action",
                "url": params.url,
                "method": params.method,
                "status": "acknowledged",
                "telegram_sent": True,
            }

        elif step_type in ("click", "mobile_action"):
            # Mobile action - delegate to execution service
            logger.info(f"Mobile action requested: {params.action} on {params.selector}")
            
            # Notify Telegram
            telegram_msg = (
                f"📱 *Mobile Action Requested*\n\n"
                f"*Task ID:* `{request.taskId}`\n"
                f"*Action:* `{params.action}`\n"
                f"*Selector:* `{params.selector}`"
            )
            await notifier.send_message(telegram_msg)
            
            return {
                "action": step_type,
                "selector": params.selector,
                "status": "queued_for_execution",
                "telegram_sent": True,
            }

        elif step_type == "extract":
            # Extract data
            logger.info(f"Extract requested from {params.selector}")
            
            # Notify Telegram
            telegram_msg = (
                f"🔍 *Data Extraction Requested*\n\n"
                f"*Task ID:* `{request.taskId}`\n"
                f"*Selector:* `{params.selector}`"
            )
            await notifier.send_message(telegram_msg)
            
            return {
                "action": "extract",
                "selector": params.selector,
                "status": "acknowledged",
                "telegram_sent": True,
            }

        else:
            logger.warning(f"Unhandled step type: {step_type}")
            
            # Still notify Telegram for unhandled types
            telegram_msg = (
                f"⚠️ *Unhandled Webhook Step*\n\n"
                f"*Task ID:* `{request.taskId}`\n"
                f"*Step Type:* `{step_type}`\n"
                f"*Params:* `{json.dumps(params.model_dump(), default=str)[:200]}`"
            )
            await notifier.send_message(telegram_msg)
            
            return {"status": "unhandled", "step_type": step_type, "telegram_sent": True}

    def get_task_status(self, run_id: str) -> Optional[TaskInfo]:
        """Get the status of a task by run_id."""
        return _task_queue.get(run_id)

    def get_all_tasks(self, limit: int = 100) -> list[TaskInfo]:
        """Get all tasks, most recent first."""
        tasks = list(_task_queue.values())
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    def get_task_by_task_id(self, task_id: str) -> Optional[TaskInfo]:
        """Get task by original taskId from OpenClaw."""
        for task in _task_queue.values():
            if task.task_id == task_id:
                return task
        return None


# Singleton instance (initialized in router)
_openclaw_service: Optional[OpenClawService] = None


def get_openclaw_service() -> OpenClawService:
    """Get the OpenClaw service singleton."""
    global _openclaw_service
    if _openclaw_service is None:
        raise RuntimeError("OpenClaw service not initialized. Call init_openclaw_service first.")
    return _openclaw_service


def init_openclaw_service(hook_token: str) -> OpenClawService:
    """Initialize the OpenClaw service singleton."""
    global _openclaw_service
    _openclaw_service = OpenClawService(hook_token=hook_token)
    logger.info("OpenClaw service initialized")
    return _openclaw_service
