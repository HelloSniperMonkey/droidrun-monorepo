"""
MobileRun Cloud API Client.

Updated to support latest Mobilerun API (2026).
"""

import asyncio
import logging
from typing import Optional, AsyncIterator, Literal
from datetime import datetime
from enum import Enum

import httpx

from .models import Device, Task, TaskStatus, TaskStatusEnum

logger = logging.getLogger("ironclaw.mobilerun.client")

MOBILERUN_API_URL = "https://api.mobilerun.ai"


class LLMModel(str, Enum):
    """Available LLM models for Mobilerun tasks."""

    GPT_51 = "openai/gpt-5.1"
    GPT_52 = "openai/gpt-5.2"
    GEMINI_25_FLASH = "google/gemini-2.5-flash"
    GEMINI_25_PRO = "google/gemini-2.5-pro"
    GEMINI_3_FLASH = "google/gemini-3-flash"
    GEMINI_3_PRO_PREVIEW = "google/gemini-3-pro-preview"
    CLAUDE_SONNET_45 = "anthropic/claude-sonnet-4.5"
    MINIMAX_M2 = "minimax/minimax-m2"
    KIMI_K2_THINKING = "moonshotai/kimi-k2-thinking"
    QWEN3_8B = "qwen/qwen3-8b"


class MobileRunClient:
    """
    Client for MobileRun Cloud API.

    Provides methods to:
    - Manage cloud devices
    - Execute natural language commands
    - Stream task execution
    - Retrieve screenshots and trajectories
    """

    def __init__(self, api_key: str, base_url: str = MOBILERUN_API_URL):
        """
        Initialize MobileRun client.

        Args:
            api_key: MobileRun API key
            base_url: API base URL (default: https://api.mobilerun.ai)
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[dict] = None,
        params: Optional[dict] = None,
        timeout: float = 60.0,
    ) -> dict:
        """Make an API request."""
        url = f"{self.base_url}{endpoint}"

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                url,
                headers=self._get_headers(),
                json=json,
                params=params,
            )
            response.raise_for_status()
            return response.json() if response.content else {}

    # ============ Device Management ============

    async def list_devices(self) -> list[Device]:
        """List all available devices."""
        data = await self._request("GET", "/devices")
        return [Device(**d) for d in data.get("devices", data)]

    async def get_device(self, device_id: str) -> Device:
        """Get device information."""
        data = await self._request("GET", f"/devices/{device_id}")
        return Device(**data)

    async def provision_device(self, platform: str = "android") -> Device:
        """Provision a new cloud device."""
        data = await self._request("POST", "/devices", json={"platform": platform})
        return Device(**data)

    async def terminate_device(self, device_id: str) -> bool:
        """Terminate a cloud device."""
        await self._request("DELETE", f"/devices/{device_id}")
        return True

    async def wait_for_device(self, device_id: str, timeout: float = 120.0) -> Device:
        """Wait for device to be ready."""
        data = await self._request("GET", f"/devices/{device_id}/wait", timeout=timeout)
        return Device(**data)

    # ============ Task Execution ============

    async def run_task(
        self,
        device_id: str,
        command: str,
        max_steps: int = 15,
        vision: bool = True,
        reasoning: bool = False,
        llm_model: Optional[str] = None,
    ) -> Task:
        """
        Execute a natural language command on a device.

        Args:
            device_id: Target device ID
            command: Natural language command
            max_steps: Maximum execution steps
            vision: Enable vision mode (screenshots)
            reasoning: Enable reasoning mode (planning)
            llm_model: LLM model to use (optional)

        Returns:
            Task object with execution result
        """
        logger.info(f"Running task on {device_id}: {command[:50]}...")

        payload = {
            "deviceId": device_id,
            "task": command,
            "maxSteps": max_steps,
            "vision": vision,
            "reasoning": reasoning,
        }
        
        if llm_model:
            payload["llmModel"] = llm_model

        data = await self._request("POST", "/v1/tasks/", json=payload, timeout=300.0)
        
        # The v1 API returns {"id": "...", "streamUrl": "...", "token": "..."}
        # Convert this to a Task object for compatibility
        task = Task(
            taskId=data.get("id"),
            deviceId=device_id,
            command=command,
            status=TaskStatusEnum.PENDING,
        )
        
        # Store the stream URL for potential streaming
        task.stream_url = data.get("streamUrl")
        
        return task

    async def run_task_v2(
        self,
        task: str,
        llm_model: LLMModel = LLMModel.GEMINI_25_FLASH,
        device_id: Optional[str] = None,
        max_steps: int = 100,
        vision: bool = True,
        reasoning: bool = True,
        temperature: float = 0.5,
        execution_timeout: int = 1000,
        apps: Optional[list[str]] = None,
    ) -> dict:
        """
        Execute a natural language task using the latest Mobilerun API (2026).

        This is the recommended method for new integrations.

        Args:
            task: Natural language task description
            llm_model: LLM model to use (default: gemini-2.5-flash)
            device_id: Target device ID (optional - uses default if not provided)
            max_steps: Maximum execution steps (default: 100)
            vision: Enable vision mode (default: True)
            reasoning: Enable reasoning/thinking mode (default: True)
            temperature: LLM temperature (default: 0.5)
            execution_timeout: Timeout in seconds (default: 1000)
            apps: List of app package names to use

        Returns:
            dict with {id, streamUrl, token}
        """
        logger.info(f"Running task v2: {task[:50]}...")

        payload = {
            "llmModel": llm_model.value if isinstance(llm_model, LLMModel) else llm_model,
            "task": task,
            "maxSteps": max_steps,
            "vision": vision,
            "reasoning": reasoning,
            "temperature": temperature,
            "executionTimeout": execution_timeout,
        }

        if device_id:
            payload["deviceId"] = device_id

        if apps:
            payload["apps"] = apps

        data = await self._request("POST", "/tasks", json=payload, timeout=300.0)
        return data

    async def run_task_stream(
        self,
        device_id: str,
        command: str,
        max_steps: int = 15,
        vision: bool = True,
        reasoning: bool = False,
        llm_model: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """
        Execute a command with streaming updates.

        Yields status updates as the task progresses.
        """
        payload = {
            "deviceId": device_id,
            "task": command,
            "maxSteps": max_steps,
            "vision": vision,
            "reasoning": reasoning,
        }
        
        if llm_model:
            payload["llmModel"] = llm_model

        url = f"{self.base_url}/v1/tasks/stream"

        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._get_headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        import json

                        yield json.loads(line[5:].strip())

    async def get_task(self, task_id: str) -> Task:
        """Get task details."""
        data = await self._request("GET", f"/tasks/{task_id}")
        return Task(**data)

    async def get_task_status(self, task_id: str) -> TaskStatus:
        """Get task execution status."""
        data = await self._request("GET", f"/tasks/{task_id}/status")
        return TaskStatus(**data)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        await self._request("POST", f"/tasks/{task_id}/cancel")
        return True

    async def get_task_screenshots(self, task_id: str) -> list[str]:
        """Get screenshots from a task."""
        data = await self._request("GET", f"/tasks/{task_id}/screenshots")
        return data.get("screenshots", [])

    async def get_task_trajectory(self, task_id: str) -> list[dict]:
        """Get execution trajectory from a task."""
        data = await self._request("GET", f"/tasks/{task_id}/trajectory")
        return data.get("trajectory", [])

    # ============ Device Tools ============

    async def take_screenshot(self, device_id: str) -> str:
        """Capture a screenshot from the device."""
        data = await self._request("GET", f"/devices/{device_id}/screenshot")
        return data.get("url") or data.get("base64", "")

    async def tap(self, device_id: str, x: int, y: int) -> bool:
        """Tap at coordinates."""
        await self._request("POST", f"/devices/{device_id}/tap", json={"x": x, "y": y})
        return True

    async def swipe(
        self,
        device_id: str,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300,
    ) -> bool:
        """Perform a swipe gesture."""
        await self._request(
            "POST",
            f"/devices/{device_id}/swipe",
            json={
                "startX": start_x,
                "startY": start_y,
                "endX": end_x,
                "endY": end_y,
                "durationMs": duration_ms,
            },
        )
        return True

    async def type_text(self, device_id: str, text: str) -> bool:
        """Input text on the device."""
        await self._request("POST", f"/devices/{device_id}/keyboard", json={"text": text})
        return True

    async def get_ui_state(self, device_id: str) -> dict:
        """Get current UI state (accessibility tree)."""
        return await self._request("GET", f"/devices/{device_id}/ui-state")

    async def list_apps(self, device_id: str) -> list[dict]:
        """List installed apps on the device."""
        data = await self._request("GET", f"/devices/{device_id}/apps")
        return data.get("apps", [])

    async def install_app(self, device_id: str, apk_url: str) -> bool:
        """Install an APK on the device."""
        await self._request("POST", f"/devices/{device_id}/apps", json={"apkUrl": apk_url})
        return True

    async def start_app(self, device_id: str, package_name: str) -> bool:
        """
        Start an app on the device.

        Args:
            device_id: Target device ID
            package_name: Android package name (e.g., 'com.android.chrome')

        Returns:
            True if successful
        """
        await self._request("PUT", f"/devices/{device_id}/apps/{package_name}", timeout=30.0)
        return True

    async def perform_global_action(self, device_id: str, action: int) -> bool:
        """
        Perform a global accessibility action on the device.

        Args:
            device_id: Target device ID
            action: Action code (0=BACK, 1=HOME, 2=RECENTS, etc.)

        Returns:
            True if successful
        """
        await self._request("POST", f"/devices/{device_id}/global", json={"action": action})
        return True

    async def input_text(self, device_id: str, text: str) -> bool:
        """
        Input text on the device (replaces current field content).

        Args:
            device_id: Target device ID
            text: Text to input

        Returns:
            True if successful
        """
        await self._request("POST", f"/devices/{device_id}/text", json={"text": text})
        return True

    async def clear_input(self, device_id: str) -> bool:
        """Clear the current input field."""
        await self._request("DELETE", f"/devices/{device_id}/text")
        return True

    # ============ Health Check ============

    async def ping(self) -> bool:
        """Check if API is accessible."""
        try:
            await self._request("GET", "/devices", timeout=10.0)
            return True
        except Exception as e:
            logger.error(f"MobileRun ping failed: {e}")
            return False
