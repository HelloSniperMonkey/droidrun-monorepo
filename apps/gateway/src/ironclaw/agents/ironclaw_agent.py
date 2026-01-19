"""
Iron Claw Agent - Extended DroidAgent with security and bio-memory.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from droidrun import DroidAgent
from droidrun.config_manager import AgentConfig, DroidrunConfig
from llama_index.llms.google_genai import GoogleGenAI

from ..utils.config import get_app_config, get_settings
from ..modules.schedule_extractor import ScheduleExtractor
from ..modules.temporal_guardian import TemporalGuardianService
from .adb_connection import ADBConnection

logger = logging.getLogger("ironclaw.agents.ironclaw_agent")


class SecurityException(Exception):
    """Raised when agent attempts to access a forbidden package."""

    pass


class IronClawAgent:
    """
    Iron Claw Agent - Mobile automation with security guardrails.

    Key Features:
    - Package whitelist enforcement
    - Bio-memory injection (user profile)
    - Screenshot capture for HITL
    """

    def __init__(
        self,
        goal: str,
        bio_memory: Optional[dict] = None,
        credentials: Optional[dict] = None,
        image_path: Optional[Path] = None,
    ):
        self.goal = goal
        self.bio_memory = bio_memory or {}
        self.credentials = credentials or {}
        self.image_path = image_path
        self.app_config = get_app_config()
        self.settings = get_settings()

        self._agent: Optional[DroidAgent] = None
        self._adb = ADBConnection()
        self._last_screenshot: Optional[bytes] = None
        self._schedule_extractor = ScheduleExtractor()
        self._temporal_guardian = TemporalGuardianService()

    async def scan_schedule_from_screen(self) -> dict:
        """
        Capture screen (or use provided image), extract schedule, and create calendar events.
        """
        logger.info("📸 Scanning for schedule...")

        image_data = None
        if self.image_path and self.image_path.exists():
            logger.info(f"Using provided image file: {self.image_path}")
            try:
                with open(self.image_path, "rb") as f:
                    image_data = f.read()
            except Exception as e:
                return {"success": False, "error": f"Failed to read image file: {e}"}
        else:
            logger.info("Capturing screenshot from device...")
            image_data = await self.get_screenshot()

        if not image_data:
            return {"success": False, "error": "No image data available (screen or file)"}

        # Extract events
        events = await self._schedule_extractor.extract_from_image(image_data)
        if not events:
            return {"success": False, "error": "No schedule events found in image"}

        # Create calendar entries
        count = await self._temporal_guardian.create_events_from_schedule(events)

        return {
            "success": True,
            "events_found": len(events),
            "events_created": count,
            "details": [e.dict() for e in events],
        }

    async def _check_package_safety(self) -> bool:
        """
        Verify current app is in the safe packages list.
        Returns True if safe, raises SecurityException if not.
        """
        current_package = await self._adb.get_current_package()
        safe_packages = self.app_config.safe_packages

        if current_package and current_package not in safe_packages:
            # Allow launcher as a "neutral" state
            if "launcher" in current_package.lower():
                return True

            logger.warning(f"⚠️ Agent in forbidden package: {current_package}")

            # Navigate home for safety
            await self._adb.press_key(3)  # KEYCODE_HOME
            raise SecurityException(f"Forbidden package: {current_package}")

        return True

    def _build_augmented_goal(self) -> str:
        """Build goal with bio-memory context injected."""
        context_parts = [self.goal]

        if "schedule" in self.goal.lower() or "timetable" in self.goal.lower():
            context_parts.append(
                "\nINSTRUCTION: If searching for a schedule/timetable, navigate until it is visible on screen. Once visible, STOP. The system will read it automatically."
            )

        if self.bio_memory:
            context_parts.append("\n\n--- User Context (Bio-Memory) ---")
            for key, value in self.bio_memory.items():
                if isinstance(value, list):
                    context_parts.append(f"{key}: {', '.join(str(v) for v in value)}")
                else:
                    context_parts.append(f"{key}: {value}")

        return "\n".join(context_parts)

    async def _create_agent(self) -> DroidAgent:
        """Create the underlying DroidAgent with configuration."""
        settings = get_settings()
        agent_config = self.app_config.agent_config

        # Initialize LLM
        llm = GoogleGenAI(
            api_key=settings.gemini_api_key,
            model="gemini-2.5-flash",
        )

        # Build configuration
        config = DroidrunConfig(
            agent=AgentConfig(
                max_steps=agent_config.get("max_steps", 30),
                reasoning=agent_config.get("reasoning", True),
                after_sleep_action=agent_config.get("after_sleep_action", 1.5),
            ),
        )

        # Create agent with augmented goal
        augmented_goal = self._build_augmented_goal()

        agent = DroidAgent(
            goal=augmented_goal,
            config=config,
            llms=llm,
            credentials=self.credentials,
        )

        return agent

    async def run(self) -> dict:
        """
        Execute the agent with security checks.
        Returns result dict with success status and output.
        """
        logger.info(f"🦾 Starting Iron Claw Agent: {self.goal[:50]}...")

        # OPTIMIZATION: If we have an image provided and the goal is schedule extraction,
        # skip ADB navigation and process immediately.
        if self.image_path and (
            "schedule" in self.goal.lower() or "timetable" in self.goal.lower()
        ):
            logger.info("Processing provided schedule image directly (bypassing navigation).")
            scan_result = await self.scan_schedule_from_screen()
            msg = f"Processed uploaded schedule: {scan_result.get('events_created', 0)} events created."
            return {
                "success": scan_result["success"],
                "reason": msg,
                "steps": ["Image uploaded", "Schedule extracted", "Calendar events created"],
                "output": str(scan_result),
            }

        # OPTIMIZATION: If we have an image and the goal is wallpaper/personalization,
        # delegate to PersonalizationService immediately.
        if self.image_path and (
            "wallpaper" in self.goal.lower()
            or "personalize" in self.goal.lower()
            or "set it" in self.goal.lower()
            or "apply it" in self.goal.lower()
        ):
            logger.info("Delegating to PersonalizationService from within Agent...")
            from ..modules.personalization import PersonalizationService

            service = PersonalizationService()
            result = await service.personalize_homescreen(self.image_path)
            return {
                "success": result["success"],
                "reason": result.get("message", "Personalization completed"),
                "steps": [result.get("method", "personalization_service")],
                "output": str(result),
            }

        try:
            # Verify connection

            ping_result = await self._adb.ping()
            if ping_result.get("status") != "connected":
                return {
                    "success": False,
                    "error": "Device not connected",
                    "details": ping_result,
                }

            # Create and run agent
            self._agent = await self._create_agent()

            # Pre-execution safety check
            await self._check_package_safety()

            # Run the agent
            result = await self._agent.run()

            # Post-execution safety check
            await self._check_package_safety()

            logger.info(f"✅ Agent completed: success={result.success}")

            # Extract steps from shared state if available
            steps = []
            if self._agent and hasattr(self._agent, "shared_state"):
                steps = self._agent.shared_state.summary_history

            # Check if this was a schedule extraction task and perform it if agent thinks it's done
            if result.success and (
                "schedule" in self.goal.lower() or "timetable" in self.goal.lower()
            ):
                logger.info("Attempting schedule extraction after agent navigation...")
                scan_result = await self.scan_schedule_from_screen()

                if scan_result["success"]:
                    msg = f"Schedule processed: {scan_result['events_created']} events created."
                    logger.info(msg)
                    return {
                        "success": True,
                        "reason": msg,
                        "steps": steps,
                        "output": str(scan_result),
                    }
                elif scan_result.get("error") == "No schedule events found in image":
                    # Not a failure, maybe just didn't find it.
                    pass
                else:
                    logger.warning(f"Schedule scan failed: {scan_result.get('error')}")

            return {
                "success": result.success,
                "reason": result.reason,
                "steps": steps,
                "output": getattr(result, "output", None),
            }

        except SecurityException as e:
            logger.error(f"🔒 Security violation: {e}")
            return {
                "success": False,
                "error": "security_violation",
                "details": str(e),
            }
        except Exception as e:
            logger.error(f"❌ Agent failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def get_screenshot(self) -> Optional[bytes]:
        """Capture and return the current screen."""
        try:
            _, screenshot = await self._adb.take_screenshot()
            self._last_screenshot = screenshot
            return screenshot
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return None

    async def go_home(self):
        """Navigate to home screen."""
        await self._adb.press_key(3)  # KEYCODE_HOME


async def create_ironclaw_agent(
    goal: str,
    bio_memory_path: Optional[Path] = None,
    credentials: Optional[dict] = None,
    image_path: Optional[Path] = None,
) -> IronClawAgent:
    """
    Factory function to create an IronClawAgent.

    Args:
        goal: The task to accomplish
        bio_memory_path: Path to user profile JSON file
        credentials: Dict of credentials for form filling
        image_path: Path to an initial image context (optional)

    Returns:
        Configured IronClawAgent instance
    """
    bio_memory = {}

    if bio_memory_path and bio_memory_path.exists():
        with open(bio_memory_path) as f:
            bio_memory = json.load(f)

    return IronClawAgent(
        goal=goal,
        bio_memory=bio_memory,
        credentials=credentials,
        image_path=image_path,
    )
