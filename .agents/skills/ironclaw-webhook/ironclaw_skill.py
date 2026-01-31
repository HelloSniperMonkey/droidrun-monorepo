"""
Iron Claw Webhook Skill for OpenClaw

This module provides actions to interact with Iron Claw's webhook API:
- run-step: Execute a task on Iron Claw
- query-status: Check the status of a running task
- cancel-task: Cancel a pending/running task

Usage:
    from ironclaw_skill import IronClawSkill

    skill = IronClawSkill(
        base_url="https://your-tunnel.trycloudflare.com",
        token="your-token"
    )

    # Execute a step
    result = await skill.run_step(
        task_id="task-001",
        step_type="log",
        params={"message": "Hello from OpenClaw"}
    )

    # Query status
    status = await skill.query_status(run_id=result["runId"])

    # Cancel task
    await skill.cancel_task(run_id=result["runId"])
"""

import os
import logging
from typing import Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("openclaw.skills.ironclaw")


@dataclass
class SkillConfig:
    """Configuration for Iron Claw skill."""
    base_url: str
    token: str
    timeout: float = 30.0
    
    @classmethod
    def from_env(cls) -> "SkillConfig":
        """Create config from environment variables."""
        base_url = os.getenv(
            "IRONCLAW_WEBHOOK_URL",
            "https://pack-nickel-occasionally-tube.trycloudflare.com"
        )
        token = os.getenv("OPENCLAW_HOOK_TOKEN", "")
        
        if not token:
            raise ValueError("OPENCLAW_HOOK_TOKEN environment variable is required")
        
        return cls(base_url=base_url, token=token)


class IronClawError(Exception):
    """Base exception for Iron Claw skill errors."""
    pass


class AuthenticationError(IronClawError):
    """Raised when authentication fails."""
    pass


class TaskNotFoundError(IronClawError):
    """Raised when a task is not found."""
    pass


class IronClawSkill:
    """
    OpenClaw skill for interacting with Iron Claw webhook API.
    
    Provides three main actions:
    - run_step: Execute a step on Iron Claw
    - query_status: Get status of a running task
    - cancel_task: Cancel a pending/running task
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        config: Optional[SkillConfig] = None,
    ):
        """
        Initialize the Iron Claw skill.
        
        Args:
            base_url: Iron Claw webhook base URL
            token: Bearer token for authentication
            config: SkillConfig object (alternative to base_url/token)
        """
        if config:
            self.config = config
        elif base_url and token:
            self.config = SkillConfig(base_url=base_url, token=token)
        else:
            self.config = SkillConfig.from_env()
        
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def webhook_url(self) -> str:
        """Full webhook URL."""
        return f"{self.config.base_url.rstrip('/')}/openclaw/webhook"
    
    @property
    def headers(self) -> dict[str, str]:
        """Request headers with authentication."""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.token}",
        }
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers=self.headers,
            )
        return self._client
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def __aenter__(self) -> "IronClawSkill":
        return self
    
    async def __aexit__(self, *args) -> None:
        await self.close()
    
    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle HTTP response and raise appropriate errors."""
        if response.status_code == 401:
            raise AuthenticationError("Missing or invalid authorization token")
        elif response.status_code == 403:
            raise AuthenticationError("Invalid token")
        elif response.status_code == 404:
            raise TaskNotFoundError("Task not found")
        elif response.status_code >= 400:
            raise IronClawError(f"Request failed: {response.text}")
        
        return response.json()
    
    # === Action: run-step ===
    
    async def run_step(
        self,
        task_id: str,
        step_type: str,
        params: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute a step on Iron Claw.
        
        Args:
            task_id: Unique identifier for the task
            step_type: Type of step (log, http_action, click, extract, mobile_action, script)
            params: Parameters for the step execution
            metadata: Optional metadata (source, correlation_id, etc.)
        
        Returns:
            dict with:
                - ok: bool - Whether the request was accepted
                - runId: str - Unique run ID for tracking
                - status: str - Current status (queued)
                - message: str - Status message
        
        Raises:
            AuthenticationError: If token is invalid
            IronClawError: If request fails
        """
        payload = {
            "taskId": task_id,
            "type": "execute-step",
            "metadata": metadata or {
                "source": "openclaw",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "payload": {
                "stepType": step_type,
                "params": params or {},
            },
        }
        
        logger.info(f"Executing step: task_id={task_id}, step_type={step_type}")
        
        client = await self._get_client()
        response = await client.post(self.webhook_url, json=payload)
        
        result = self._handle_response(response)
        
        logger.info(f"Step queued: run_id={result.get('runId')}")
        return result
    
    # === Action: query-status ===
    
    async def query_status(self, run_id: str) -> dict[str, Any]:
        """
        Query the status of a running task.
        
        Args:
            run_id: Run ID returned from run_step
        
        Returns:
            dict with:
                - ok: bool
                - runId: str
                - status: str (pending, queued, running, completed, failed, cancelled)
                - message: str (error message if failed)
        
        Raises:
            TaskNotFoundError: If task is not found
            AuthenticationError: If token is invalid
        """
        url = f"{self.config.base_url.rstrip('/')}/openclaw/tasks/{run_id}"
        
        logger.info(f"Querying status: run_id={run_id}")
        
        client = await self._get_client()
        response = await client.get(url)
        
        return self._handle_response(response)
    
    # === Action: cancel-task ===
    
    async def cancel_task(self, run_id: str) -> dict[str, Any]:
        """
        Cancel a pending or running task.
        
        Args:
            run_id: Run ID of the task to cancel
        
        Returns:
            dict with:
                - ok: bool
                - runId: str
                - status: str (cancelled)
                - message: str
        
        Raises:
            TaskNotFoundError: If task is not found
            AuthenticationError: If token is invalid
            IronClawError: If task cannot be cancelled
        """
        url = f"{self.config.base_url.rstrip('/')}/openclaw/tasks/{run_id}"
        
        logger.info(f"Cancelling task: run_id={run_id}")
        
        client = await self._get_client()
        response = await client.delete(url)
        
        return self._handle_response(response)
    
    # === Convenience methods ===
    
    async def list_tasks(
        self,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        List all tasks.
        
        Args:
            limit: Maximum number of tasks to return
            status: Filter by status (optional)
        
        Returns:
            dict with:
                - ok: bool
                - tasks: list of TaskInfo objects
                - total: int
        """
        url = f"{self.config.base_url.rstrip('/')}/openclaw/tasks"
        params = {"limit": limit}
        if status:
            params["status"] = status
        
        client = await self._get_client()
        response = await client.get(url, params=params)
        
        return self._handle_response(response)
    
    async def health_check(self) -> dict[str, Any]:
        """
        Check Iron Claw webhook health.
        
        Returns:
            dict with health status information
        """
        url = f"{self.config.base_url.rstrip('/')}/openclaw/health"
        
        client = await self._get_client()
        response = await client.get(url)
        
        return response.json()


# === OpenClaw Skill Entry Points ===

async def run_step(
    task_id: str,
    step_type: str,
    params: Optional[dict] = None,
    **kwargs,
) -> dict[str, Any]:
    """OpenClaw action entry point for run-step."""
    async with IronClawSkill() as skill:
        return await skill.run_step(task_id, step_type, params)


async def query_status(run_id: str, **kwargs) -> dict[str, Any]:
    """OpenClaw action entry point for query-status."""
    async with IronClawSkill() as skill:
        return await skill.query_status(run_id)


async def cancel_task(run_id: str, **kwargs) -> dict[str, Any]:
    """OpenClaw action entry point for cancel-task."""
    async with IronClawSkill() as skill:
        return await skill.cancel_task(run_id)
