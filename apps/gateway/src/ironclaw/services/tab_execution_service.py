"""
Tab Execution Service for Chrome tab management.

Provides specialized execution methods for tab operations using:
1. Primary: MobileRun Cloud API (v2)
2. Fallback: Local DroidRun agent

Keeps it simple - focuses on tab-specific tasks.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger("ironclaw.services.tab_execution")


@dataclass
class TabInfo:
    """Represents a Chrome tab."""

    title: str
    url: str
    domain: Optional[str] = None
    is_active: bool = False
    group: Optional[str] = None


@dataclass
class TabExecutionResult:
    """Result from a tab operation."""

    success: bool
    message: str
    tabs: List[TabInfo] = field(default_factory=list)
    groups_created: int = 0
    tabs_closed: int = 0
    duplicates_merged: int = 0
    screenshots: List[str] = field(default_factory=list)
    task_id: Optional[str] = None
    error: Optional[str] = None


class TabExecutionService:
    """
    Specialized service for Chrome tab automation.

    Uses MobileRun's natural language task API for robust execution.
    Falls back to Droidrun agent if MobileRun is unavailable.
    """

    CHROME_PACKAGE = "com.android.chrome"

    def __init__(
        self,
        mobilerun_api_key: Optional[str] = None,
        mobilerun_device_id: Optional[str] = None,
    ):
        self.api_key = mobilerun_api_key or os.getenv("MOBILERUN_API_KEY")
        self.device_id = mobilerun_device_id or os.getenv("MOBILERUN_DEVICE_ID")
        self._client = None

    def _get_client(self):
        """Lazy-load MobileRun client."""
        if self._client is None and self.api_key:
            try:
                from ironclaw_mobilerun import MobileRunClient

                self._client = MobileRunClient(api_key=self.api_key)
            except ImportError:
                logger.warning("MobileRun client not available")
        return self._client

    async def _execute_via_mobilerun(self, task: str, max_steps: int = 50) -> dict:
        """Execute task via MobileRun Cloud API."""
        client = self._get_client()
        if not client:
            raise RuntimeError("MobileRun client not configured")

        try:
            from ironclaw_mobilerun import LLMModel

            result = await client.run_task_v2(
                task=task,
                llm_model=LLMModel.GEMINI_25_FLASH,
                device_id=self.device_id,
                max_steps=max_steps,
                vision=True,
                reasoning=True,
                apps=[self.CHROME_PACKAGE],
            )
            return result
        except Exception as e:
            logger.error(f"MobileRun execution failed: {e}")
            raise

    async def _execute_via_droidrun(self, goal: str) -> dict:
        """Fallback: Execute via local Droidrun agent."""
        try:
            from ..agents.ironclaw_agent import create_ironclaw_agent

            agent = await create_ironclaw_agent(goal=goal)
            result = await agent.run()
            return {
                "success": result.get("success", False),
                "output": result.get("output"),
                "error": result.get("error"),
            }
        except Exception as e:
            logger.error(f"Droidrun execution failed: {e}")
            raise

    async def _execute_hybrid(
        self,
        task: str,
        max_steps: int = 50,
    ) -> dict:
        """
        Execute task with hybrid approach:
        1. Try MobileRun first
        2. Fall back to Droidrun if MobileRun fails
        """
        # Try MobileRun first
        if self.api_key and self.device_id:
            try:
                logger.info(f"Executing via MobileRun: {task[:50]}...")
                result = await self._execute_via_mobilerun(task, max_steps)
                return {"backend": "mobilerun", **result}
            except Exception as e:
                logger.warning(f"MobileRun failed, falling back to Droidrun: {e}")

        # Fallback to Droidrun
        try:
            logger.info(f"Executing via Droidrun: {task[:50]}...")
            result = await self._execute_via_droidrun(task)
            return {"backend": "droidrun", **result}
        except Exception as e:
            logger.error(f"Both backends failed: {e}")
            return {
                "backend": "none",
                "success": False,
                "error": f"Execution failed: {e}",
            }

    async def organize_tabs(self) -> TabExecutionResult:
        """
        Organize Chrome tabs into AI-determined groups.
        """
        task = """
        Open Chrome and organize all open tabs into logical groups.

        Follow these physical steps:
        1. Unlock the device if locked (swipe up from bottom).
        2. Open the Chrome app.
        3. Tap the tab switcher icon (box with number) to view open tabs.
        4. LOOK at the screen to identify visible tabs.
        5. Scroll down slowly to reveal more tabs. 
           - **CRITICAL**: If you cannot scroll down further (bottom reached), scroll UP to review tabs you might have missed.
           - Ensure you have seen ALL open tabs.
        6. Group tabs by content type - let the groups emerge naturally:
           - Group work-related tabs together (GitHub, docs, work tools)
           - Group social media tabs (Twitter, LinkedIn, Reddit)
           - Group shopping tabs (Amazon, eBay, product pages)
           - Group news/media/entertainment
           - Group research/learning
        7. To group tabs: Long press a tab and drag it over another similar tab, OR tap the menu on a tab and select "Group tabs".
        8. Name each group descriptively.
        9. Take a screenshot of the final organized view.
        
        Important:
        - USE VISION: Look at the screenshots to read tab titles accurately.
        - Stop scrolling if you see the same tabs repeatedly.
        - If the list is short, scroll up and down once to confirm.
        """

        try:
            result = await self._execute_hybrid(task, max_steps=60)

            if result.get("success", False) or result.get("id"):
                return TabExecutionResult(
                    success=True,
                    message="Tabs organized successfully",
                    task_id=result.get("id"),
                )
            else:
                return TabExecutionResult(
                    success=False,
                    message="Tab organization failed",
                    error=result.get("error", "Unknown error"),
                )
        except Exception as e:
            return TabExecutionResult(
                success=False,
                message="Tab organization failed",
                error=str(e),
            )

    async def merge_duplicates(self) -> TabExecutionResult:
        """
        Find and close duplicate Chrome tabs.
        """
        task = """
        Open Chrome and find duplicate tabs to close.

        Follow these physical steps:
        1. Unlock the device if locked.
        2. Open the Chrome app.
        3. Tap the tab switcher icon.
        4. LOOK at the screen to identify visible tabs.
        5. Scroll through the list (down AND up) to view all titles.
           - If you reach the bottom, scroll back up to double-check.
        6. Identify tabs with the same URL (duplicates) by visually comparing titles/URLs.
        7. For each set of duplicates, tap the "X" on the older tabs to close them. Keep the most recent one.
        8. Count how many duplicate tabs were closed.
        9. Take a screenshot before and after.

        Important:
        - USE VISION: Verify titles match exactly before closing.
        - Do not get stuck scrolling at the bottom - scroll up if needed.
        """

        try:
            result = await self._execute_hybrid(task, max_steps=40)

            if result.get("success", False) or result.get("id"):
                return TabExecutionResult(
                    success=True,
                    message="Duplicate tabs merged",
                    task_id=result.get("id"),
                )
            else:
                return TabExecutionResult(
                    success=False,
                    message="Duplicate merge failed",
                    error=result.get("error", "Unknown error"),
                )
        except Exception as e:
            return TabExecutionResult(
                success=False,
                message="Duplicate merge failed",
                error=str(e),
            )

    async def close_old_tabs(self, max_tabs: int = 10) -> TabExecutionResult:
        """
        Close stale/old Chrome tabs.

        Args:
            max_tabs: Maximum number of tabs to close in one session
        """
        task = f"""
        Open Chrome and close old/stale tabs.

        Follow these physical steps:
        1. Unlock the device if locked.
        2. Open Chrome.
        3. Tap the tab switcher icon.
        4. Scroll through the list (down then up) to find old or unused ones.
        5. Look for tabs that seem abandoned (e.g., "New Tab", outdated searches).
        6. Tap the "X" button on these tabs to close them.
        7. Close up to {max_tabs} old tabs.
        8. Do NOT close tabs with unsaved forms or important work.
        
        Important:
        - USE VISION: Look closely at tab thumbnails/titles.
        - Scroll up if you hit the bottom to ensure you checked everything.
        """

        try:
            result = await self._execute_hybrid(task, max_steps=40)

            if result.get("success", False) or result.get("id"):
                return TabExecutionResult(
                    success=True,
                    message=f"Closed up to {max_tabs} old tabs",
                    task_id=result.get("id"),
                )
            else:
                return TabExecutionResult(
                    success=False,
                    message="Tab cleanup failed",
                    error=result.get("error", "Unknown error"),
                )
        except Exception as e:
            return TabExecutionResult(
                success=False,
                message="Tab cleanup failed",
                error=str(e),
            )

    async def list_tabs(self) -> TabExecutionResult:
        """
        Get a list of all currently open Chrome tabs.
        """
        task = """
        Open Chrome and list all open tabs.

        Follow these physical steps:
        1. Unlock the device if locked.
        2. Open Chrome.
        3. Tap the tab switcher icon.
        4. Scroll through the entire list of tabs (down then up).
        5. USE VISION: Read the title and URL of every visible tab.
        6. Report the total count of tabs found.
        7. Take a screenshot of the tab overview.
        
        Important:
        - If you reach the bottom, scroll up to view the top tabs again.
        - Ensure you capture details from the WHOLE list.
        """

        try:
            result = await self._execute_hybrid(task, max_steps=20)

            if result.get("success", False) or result.get("id"):
                return TabExecutionResult(
                    success=True,
                    message="Tab list retrieved",
                    task_id=result.get("id"),
                )
            else:
                return TabExecutionResult(
                    success=False,
                    message="Failed to list tabs",
                    error=result.get("error", "Unknown error"),
                )
        except Exception as e:
            return TabExecutionResult(
                success=False,
                message="Failed to list tabs",
                error=str(e),
            )

    async def get_ui_state(self) -> Optional[dict]:
        """Get current Chrome UI state (for debugging)."""
        client = self._get_client()
        if client and self.device_id:
            try:
                return await client.get_ui_state(self.device_id)
            except Exception as e:
                logger.error(f"Failed to get UI state: {e}")
        return None


# Singleton instance
_tab_service: Optional[TabExecutionService] = None


def get_tab_execution_service() -> TabExecutionService:
    """Get the singleton tab execution service."""
    global _tab_service
    if _tab_service is None:
        _tab_service = TabExecutionService()
    return _tab_service
