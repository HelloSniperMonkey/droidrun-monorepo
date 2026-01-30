"""
Unified Execution Service for Iron Claw.

Handles command execution with:
1. Primary: MobileRun Cloud (if configured)
2. Fallback: Local DroidRun CLI (if device connected via ADB)
"""
import asyncio
import logging
import subprocess
import shutil
from typing import Optional, AsyncIterator
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("ironclaw.services.execution")


class ExecutionBackend(str, Enum):
    """Available execution backends."""
    MOBILERUN_CLOUD = "mobilerun_cloud"
    DROIDRUN_LOCAL = "droidrun_local"
    NONE = "none"


@dataclass
class ExecutionResult:
    """Result from command execution."""
    success: bool
    backend: ExecutionBackend
    output: Optional[str] = None
    error: Optional[str] = None
    task_id: Optional[str] = None
    screenshots: list[str] = None
    steps: int = 0

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []


class ExecutionService:
    """
    Unified execution service for mobile automation.

    Automatically selects the best available backend:
    1. MobileRun Cloud - if API key and device ID are configured
    2. DroidRun Local - if a phone is connected via ADB

    Usage:
        service = ExecutionService(
            mobilerun_api_key="...",
            mobilerun_device_id="...",
        )

        # Check available backends
        backend = await service.get_available_backend()

        # Execute command
        result = await service.execute("Open settings and increase font size")
    """

    def __init__(
        self,
        mobilerun_api_key: Optional[str] = None,
        mobilerun_device_id: Optional[str] = None,
        mobilerun_base_url: str = "https://api.mobilerun.ai",
        local_device_serial: Optional[str] = None,
        prefer_local: bool = False,
    ):
        """
        Initialize execution service.

        Args:
            mobilerun_api_key: MobileRun Cloud API key
            mobilerun_device_id: MobileRun device ID
            mobilerun_base_url: MobileRun API URL
            local_device_serial: Local ADB device serial (optional)
            prefer_local: If True, prefer local DroidRun over cloud
        """
        self.mobilerun_api_key = mobilerun_api_key
        self.mobilerun_device_id = mobilerun_device_id
        self.mobilerun_base_url = mobilerun_base_url
        self.local_device_serial = local_device_serial
        self.prefer_local = prefer_local

        self._mobilerun_client = None
        self._backend_cache: Optional[ExecutionBackend] = None

    def _get_mobilerun_client(self):
        """Get or create MobileRun client."""
        if self._mobilerun_client is None and self.mobilerun_api_key:
            from ironclaw_mobilerun import MobileRunClient
            self._mobilerun_client = MobileRunClient(
                api_key=self.mobilerun_api_key,
                base_url=self.mobilerun_base_url,
            )
        return self._mobilerun_client

    async def check_mobilerun_available(self) -> bool:
        """Check if MobileRun Cloud is available."""
        if not self.mobilerun_api_key or not self.mobilerun_device_id:
            return False

        try:
            client = self._get_mobilerun_client()
            if client:
                return await client.ping()
        except Exception as e:
            logger.warning(f"MobileRun not available: {e}")
        return False

    async def check_droidrun_available(self) -> bool:
        """Check if local DroidRun CLI is available with a connected device."""
        # Check if droidrun CLI is installed
        if not shutil.which("droidrun"):
            logger.info("DroidRun CLI not found in PATH")
            return False

        try:
            # Try a simple command to test connectivity
            result = await asyncio.to_thread(
                subprocess.run,
                ["droidrun", "run", "echo test", "--steps", "1"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            # If it fails with "no device", return False
            if "no device" in result.stderr.lower() or "not found" in result.stderr.lower():
                logger.info("No local device connected for DroidRun")
                return False
            return True
        except subprocess.TimeoutExpired:
            logger.warning("DroidRun check timed out")
            return False
        except Exception as e:
            logger.warning(f"DroidRun check failed: {e}")
            return False

    async def get_available_backend(self, force_refresh: bool = False) -> ExecutionBackend:
        """
        Determine the best available backend.

        Returns:
            ExecutionBackend enum indicating which backend to use
        """
        if self._backend_cache and not force_refresh:
            return self._backend_cache

        # Check backends based on preference
        if self.prefer_local:
            if await self.check_droidrun_available():
                self._backend_cache = ExecutionBackend.DROIDRUN_LOCAL
                return self._backend_cache
            if await self.check_mobilerun_available():
                self._backend_cache = ExecutionBackend.MOBILERUN_CLOUD
                return self._backend_cache
        else:
            if await self.check_mobilerun_available():
                self._backend_cache = ExecutionBackend.MOBILERUN_CLOUD
                return self._backend_cache
            if await self.check_droidrun_available():
                self._backend_cache = ExecutionBackend.DROIDRUN_LOCAL
                return self._backend_cache

        self._backend_cache = ExecutionBackend.NONE
        return self._backend_cache

    async def execute(
        self,
        command: str,
        max_steps: int = 15,
        vision: bool = True,
        reasoning: bool = False,
        llm_model: Optional[str] = None,
        force_backend: Optional[ExecutionBackend] = None,
    ) -> ExecutionResult:
        """
        Execute a natural language command.

        Args:
            command: Natural language command to execute
            max_steps: Maximum execution steps
            vision: Enable vision mode (screenshots)
            reasoning: Enable reasoning/planning mode
            llm_model: LLM model to use (for MobileRun Cloud)
            force_backend: Force a specific backend (optional)

        Returns:
            ExecutionResult with success status and output
        """
        backend = force_backend or await self.get_available_backend()

        logger.info(f"Executing on {backend.value}: {command[:50]}...")

        if backend == ExecutionBackend.MOBILERUN_CLOUD:
            return await self._execute_mobilerun(command, max_steps, vision, reasoning, llm_model)
        elif backend == ExecutionBackend.DROIDRUN_LOCAL:
            return await self._execute_droidrun(command, max_steps, vision, reasoning)
        else:
            return ExecutionResult(
                success=False,
                backend=ExecutionBackend.NONE,
                error="No execution backend available. Connect a device or configure MobileRun.",
            )

    async def _execute_mobilerun(
        self,
        command: str,
        max_steps: int,
        vision: bool,
        reasoning: bool,
        llm_model: Optional[str] = None,
    ) -> ExecutionResult:
        """Execute via MobileRun Cloud."""
        try:
            client = self._get_mobilerun_client()
            task = await client.run_task(
                device_id=self.mobilerun_device_id,
                command=command,
                max_steps=max_steps,
                vision=vision,
                reasoning=reasoning,
                llm_model=llm_model,
            )

            # The v1 API returns immediately with task creation confirmation
            # For now, return success with the task ID
            return ExecutionResult(
                success=True,
                backend=ExecutionBackend.MOBILERUN_CLOUD,
                output=f"Task created successfully. Task ID: {task.task_id}",
                task_id=task.task_id,
                screenshots=[],
                steps=0,
            )
        except Exception as e:
            logger.error(f"MobileRun execution failed: {e}", exc_info=True)
            return ExecutionResult(
                success=False,
                backend=ExecutionBackend.MOBILERUN_CLOUD,
                error=str(e),
            )

    async def _execute_droidrun(
        self,
        command: str,
        max_steps: int,
        vision: bool,
        reasoning: bool,
    ) -> ExecutionResult:
        """Execute via local DroidRun CLI."""
        try:
            cmd = ["droidrun", "run", command, "--steps", str(max_steps)]

            if vision:
                cmd.append("--vision")
            if reasoning:
                cmd.append("--reasoning")
            if self.local_device_serial:
                cmd.extend(["--device", self.local_device_serial])

            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            success = result.returncode == 0
            output = result.stdout if success else result.stderr

            return ExecutionResult(
                success=success,
                backend=ExecutionBackend.DROIDRUN_LOCAL,
                output=output,
                error=result.stderr if not success else None,
            )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                backend=ExecutionBackend.DROIDRUN_LOCAL,
                error="Command execution timed out (300s)",
            )
        except Exception as e:
            logger.error(f"DroidRun execution failed: {e}")
            return ExecutionResult(
                success=False,
                backend=ExecutionBackend.DROIDRUN_LOCAL,
                error=str(e),
            )

    async def execute_stream(
        self,
        command: str,
        max_steps: int = 15,
        vision: bool = True,
        reasoning: bool = False,
        llm_model: Optional[str] = None,
    ) -> AsyncIterator[dict]:
        """
        Execute with streaming updates (MobileRun only).

        Yields status updates as the task progresses.
        Falls back to non-streaming for DroidRun.
        """
        backend = await self.get_available_backend()

        if backend == ExecutionBackend.MOBILERUN_CLOUD:
            client = self._get_mobilerun_client()
            async for update in client.run_task_stream(
                device_id=self.mobilerun_device_id,
                command=command,
                max_steps=max_steps,
                vision=vision,
                reasoning=reasoning,
                llm_model=llm_model,
            ):
                yield update
        else:
            # For DroidRun, execute and yield single result
            result = await self.execute(command, max_steps, vision, reasoning, llm_model)
            yield {
                "status": "completed" if result.success else "failed",
                "output": result.output,
                "error": result.error,
            }

    async def take_screenshot(self) -> Optional[str]:
        """Take a screenshot from the current device."""
        backend = await self.get_available_backend()

        if backend == ExecutionBackend.MOBILERUN_CLOUD:
            client = self._get_mobilerun_client()
            return await client.take_screenshot(self.mobilerun_device_id)
        elif backend == ExecutionBackend.DROIDRUN_LOCAL:
            # Use ADB to take screenshot
            try:
                result = await asyncio.to_thread(
                    subprocess.run,
                    ["adb", "shell", "screencap", "-p"],
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    import base64
                    return base64.b64encode(result.stdout).decode()
            except Exception as e:
                logger.error(f"Screenshot failed: {e}")
        return None


# Singleton instance
_service_instance: Optional[ExecutionService] = None


def get_execution_service() -> ExecutionService:
    """Get the singleton execution service."""
    global _service_instance
    if _service_instance is None:
        # Load from environment
        import os
        _service_instance = ExecutionService(
            mobilerun_api_key=os.getenv("MOBILERUN_API_KEY"),
            mobilerun_device_id=os.getenv("MOBILERUN_DEVICE_ID"),
            local_device_serial=os.getenv("DEVICE_SERIAL"),
            prefer_local=os.getenv("PREFER_LOCAL_DEVICE", "false").lower() == "true",
        )
    return _service_instance


def configure_execution_service(
    mobilerun_api_key: Optional[str] = None,
    mobilerun_device_id: Optional[str] = None,
    local_device_serial: Optional[str] = None,
    prefer_local: bool = False,
) -> ExecutionService:
    """Configure and return the execution service."""
    global _service_instance
    _service_instance = ExecutionService(
        mobilerun_api_key=mobilerun_api_key,
        mobilerun_device_id=mobilerun_device_id,
        local_device_serial=local_device_serial,
        prefer_local=prefer_local,
    )
    return _service_instance
