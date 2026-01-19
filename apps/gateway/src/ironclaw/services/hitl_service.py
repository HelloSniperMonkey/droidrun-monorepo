"""
Human-in-the-Loop (HITL) Service for Iron Claw.

This service handles situations where the agent needs human intervention:
- CAPTCHAs
- Login required
- Confirmation dialogs
- Ambiguous UI states

The flow:
1. Agent encounters obstacle -> calls request_hitl()
2. HITL service stores request and notifies user (via Telegram/webhook)
3. User resolves issue and responds
4. Agent receives response and continues
"""
import asyncio
import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("ironclaw.services.hitl")

# In-memory storage (use Redis in production)
_hitl_requests: dict[str, dict] = {}
_hitl_responses: dict[str, dict] = {}
_notification_callbacks: list[Callable[[dict], Awaitable[None]]] = []


class HITLTimeoutError(Exception):
    """Raised when HITL request times out waiting for response."""
    pass


class HITLService:
    """
    Human-in-the-Loop service for agent intervention.

    Usage:
        service = HITLService()

        # Register notification callback (e.g., Telegram bot)
        service.register_callback(send_telegram_notification)

        # Agent requests help
        response = await service.request_hitl(
            task_id="task-123",
            hitl_type="captcha",
            message="CAPTCHA detected. Please solve it.",
            screenshot=screenshot_bytes,
        )

        # User responds via API
        await service.respond_hitl(request_id, action="I solved it")
    """

    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self):
        self._lock = asyncio.Lock()

    def register_callback(
        self, callback: Callable[[dict], Awaitable[None]]
    ) -> None:
        """
        Register a callback for HITL notifications.
        The callback receives the HITL request dict.
        """
        _notification_callbacks.append(callback)
        logger.info(f"Registered HITL callback: {callback.__name__}")

    async def request_hitl(
        self,
        task_id: str,
        hitl_type: str,
        message: str,
        screenshot: Optional[bytes] = None,
        options: Optional[list[str]] = None,
        timeout_seconds: int = DEFAULT_TIMEOUT,
    ) -> dict:
        """
        Request human intervention.

        Args:
            task_id: The task that needs intervention
            hitl_type: Type of intervention (captcha, login, confirmation, etc.)
            message: Message to display to the user
            screenshot: Optional screenshot bytes
            options: List of action options (default: Retry, Abort, I solved it)
            timeout_seconds: How long to wait for response

        Returns:
            Dict with response action and optional custom_input

        Raises:
            HITLTimeoutError: If no response within timeout
        """
        request_id = f"hitl-{uuid.uuid4().hex[:8]}"

        # Encode screenshot if provided
        screenshot_b64 = None
        if screenshot:
            screenshot_b64 = base64.b64encode(screenshot).decode("utf-8")

        request = {
            "request_id": request_id,
            "task_id": task_id,
            "hitl_type": hitl_type,
            "message": message,
            "screenshot_base64": screenshot_b64,
            "options": options or ["Retry", "Abort", "I solved it"],
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(seconds=timeout_seconds)).isoformat(),
            "status": "pending",
        }

        async with self._lock:
            _hitl_requests[request_id] = request

        logger.info(f"HITL request created: {request_id} ({hitl_type})")

        # Notify all registered callbacks
        for callback in _notification_callbacks:
            try:
                await callback(request)
            except Exception as e:
                logger.error(f"HITL callback failed: {e}")

        # Wait for response
        response = await self._wait_for_response(request_id, timeout_seconds)
        return response

    async def _wait_for_response(
        self, request_id: str, timeout_seconds: int
    ) -> dict:
        """Wait for a response to a HITL request."""
        deadline = datetime.now() + timedelta(seconds=timeout_seconds)
        poll_interval = 1.0  # seconds

        while datetime.now() < deadline:
            # Check if response exists
            if request_id in _hitl_responses:
                response = _hitl_responses.pop(request_id)
                async with self._lock:
                    if request_id in _hitl_requests:
                        _hitl_requests[request_id]["status"] = "resolved"
                logger.info(f"HITL response received: {request_id} -> {response['action']}")
                return response

            await asyncio.sleep(poll_interval)

        # Timeout - mark as expired
        async with self._lock:
            if request_id in _hitl_requests:
                _hitl_requests[request_id]["status"] = "expired"

        raise HITLTimeoutError(f"HITL request {request_id} timed out after {timeout_seconds}s")

    async def respond_hitl(
        self,
        request_id: str,
        action: str,
        custom_input: Optional[str] = None,
    ) -> bool:
        """
        Respond to a HITL request.

        Args:
            request_id: The HITL request ID
            action: The action taken (one of the options or custom)
            custom_input: Optional custom input from user

        Returns:
            True if response was recorded, False if request not found
        """
        if request_id not in _hitl_requests:
            logger.warning(f"HITL response for unknown request: {request_id}")
            return False

        request = _hitl_requests[request_id]
        if request["status"] != "pending":
            logger.warning(f"HITL request already resolved: {request_id}")
            return False

        response = {
            "request_id": request_id,
            "action": action,
            "custom_input": custom_input,
            "resolved_at": datetime.now().isoformat(),
        }

        _hitl_responses[request_id] = response
        logger.info(f"HITL response recorded: {request_id} -> {action}")
        return True

    async def get_pending_requests(self, task_id: Optional[str] = None) -> list[dict]:
        """Get all pending HITL requests, optionally filtered by task_id."""
        pending = []
        for req in _hitl_requests.values():
            if req["status"] == "pending":
                if task_id is None or req["task_id"] == task_id:
                    pending.append(req)
        return pending

    async def get_request(self, request_id: str) -> Optional[dict]:
        """Get a specific HITL request."""
        return _hitl_requests.get(request_id)

    async def cancel_request(self, request_id: str) -> bool:
        """Cancel a pending HITL request."""
        if request_id not in _hitl_requests:
            return False

        async with self._lock:
            _hitl_requests[request_id]["status"] = "cancelled"

        # Trigger response with "Abort" action
        _hitl_responses[request_id] = {
            "request_id": request_id,
            "action": "Abort",
            "custom_input": "Cancelled by user",
            "resolved_at": datetime.now().isoformat(),
        }
        return True


# Singleton instance
_service_instance: Optional[HITLService] = None


def get_hitl_service() -> HITLService:
    """Get the singleton HITL service instance."""
    global _service_instance
    if _service_instance is None:
        _service_instance = HITLService()
    return _service_instance
