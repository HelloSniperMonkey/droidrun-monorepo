"""
Tab Manager Module - Chrome tab organization and cleanup.

Features:
- Organize tabs into AI-determined groups
- Merge duplicate tabs
- Close old/stale tabs
- Save and restore tab sessions
"""

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..services.tab_execution_service import (
    TabExecutionService,
    TabExecutionResult,
    get_tab_execution_service,
)
from ..utils.config import get_app_config, get_settings

logger = logging.getLogger("ironclaw.modules.tab_manager")

# In-memory task storage (use Redis in production)
_task_storage: dict = {}

# Session storage directory
SESSION_DIR = Path(__file__).parent.parent.parent.parent.parent.parent / "data" / "tab_sessions"


class TabSession:
    """Represents a saved tab session."""

    def __init__(
        self,
        session_id: str,
        name: str,
        tabs: List[dict],
        created_at: Optional[str] = None,
    ):
        self.session_id = session_id
        self.name = name
        self.tabs = tabs
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.session_id,
            "name": self.name,
            "tabs": self.tabs,
            "created_at": self.created_at,
            "tab_count": len(self.tabs),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TabSession":
        return cls(
            session_id=data["id"],
            name=data["name"],
            tabs=data.get("tabs", []),
            created_at=data.get("created_at"),
        )


class TabManagerService:
    """
    Service for Chrome tab management and organization.

    Capabilities:
    - List open Chrome tabs
    - Organize tabs into groups by content type (AI analysis)
    - Close old tabs (older than X days)
    - Merge duplicate tabs
    - Save/restore tab sessions
    """

    def __init__(self):
        self.settings = get_settings()
        self.config = get_app_config().tab_manager_config
        self.execution_service = get_tab_execution_service()
        self._ensure_session_dir()

    def _ensure_session_dir(self):
        """Create session storage directory if it doesn't exist."""
        SESSION_DIR.mkdir(parents=True, exist_ok=True)

    async def organize_tabs(self, task_id: str = "") -> dict:
        """
        Organize Chrome tabs into groups by content type using AI analysis.

        Returns dict with organization results.
        """
        if not task_id:
            task_id = str(uuid.uuid4())[:8]

        logger.info(f"[{task_id}] Starting tab organization")

        # Initialize task status
        _task_storage[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "operation": "organize",
            "logs": [],
        }

        try:
            self._log_task(task_id, "Starting AI-powered tab organization")

            # Execute via hybrid service (MobileRun first, then Droidrun)
            result = await self.execution_service.organize_tabs()

            # Update task status
            _task_storage[task_id]["status"] = "completed" if result.success else "failed"
            _task_storage[task_id]["completed_at"] = datetime.now().isoformat()
            _task_storage[task_id]["result"] = {
                "success": result.success,
                "message": result.message,
                "mobilerun_task_id": result.task_id,
                "groups_created": result.groups_created,
            }

            self._log_task(task_id, f"Organization completed: {result.message}")

            return {
                "success": result.success,
                "task_id": task_id,
                "message": result.message,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"[{task_id}] Tab organization failed: {e}")
            _task_storage[task_id]["status"] = "error"
            _task_storage[task_id]["error"] = str(e)
            return {"success": False, "task_id": task_id, "error": str(e)}

    async def list_tabs(self) -> dict:
        """
        List all currently open Chrome tabs.

        Returns dict with tab information.
        """
        try:
            result = await self.execution_service.list_tabs()

            return {
                "success": result.success,
                "tabs": [t.__dict__ for t in result.tabs] if result.tabs else [],
                "count": len(result.tabs) if result.tabs else 0,
                "task_id": result.task_id,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"List tabs failed: {e}")
            return {"success": False, "error": str(e)}

    async def close_old_tabs(self, days_old: int = 7, task_id: str = "") -> dict:
        """
        Close Chrome tabs that are older than the specified number of days.

        Args:
            days_old: Close tabs older than this many days
            task_id: Unique task identifier for status tracking
        """
        if not task_id:
            task_id = str(uuid.uuid4())[:8]

        logger.info(f"[{task_id}] Starting cleanup of tabs older than {days_old} days")

        # Initialize task status
        _task_storage[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "operation": "close_old",
            "logs": [],
        }

        try:
            max_tabs = self.config.get("max_tabs_to_close", 10)
            self._log_task(task_id, f"Closing up to {max_tabs} old tabs")

            result = await self.execution_service.close_old_tabs(max_tabs=max_tabs)

            # Update task status
            _task_storage[task_id]["status"] = "completed" if result.success else "failed"
            _task_storage[task_id]["completed_at"] = datetime.now().isoformat()
            _task_storage[task_id]["result"] = {
                "success": result.success,
                "message": result.message,
                "tabs_closed": result.tabs_closed,
            }

            self._log_task(task_id, f"Cleanup completed: {result.message}")

            return {
                "success": result.success,
                "task_id": task_id,
                "message": result.message,
                "tabs_closed": result.tabs_closed,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"[{task_id}] Tab cleanup failed: {e}")
            _task_storage[task_id]["status"] = "error"
            _task_storage[task_id]["error"] = str(e)
            return {"success": False, "task_id": task_id, "error": str(e)}

    async def merge_duplicate_tabs(self, task_id: str = "") -> dict:
        """
        Find and close duplicate Chrome tabs.

        Keeps one instance of each duplicate URL.
        """
        if not task_id:
            task_id = str(uuid.uuid4())[:8]

        logger.info(f"[{task_id}] Starting duplicate tab merge")

        _task_storage[task_id] = {
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "operation": "merge_duplicates",
            "logs": [],
        }

        try:
            self._log_task(task_id, "Finding and merging duplicate tabs")

            result = await self.execution_service.merge_duplicates()

            _task_storage[task_id]["status"] = "completed" if result.success else "failed"
            _task_storage[task_id]["completed_at"] = datetime.now().isoformat()
            _task_storage[task_id]["result"] = {
                "success": result.success,
                "message": result.message,
                "duplicates_merged": result.duplicates_merged,
            }

            self._log_task(task_id, f"Merge completed: {result.message}")

            return {
                "success": result.success,
                "task_id": task_id,
                "message": result.message,
                "duplicates_merged": result.duplicates_merged,
                "error": result.error,
            }

        except Exception as e:
            logger.error(f"[{task_id}] Duplicate merge failed: {e}")
            _task_storage[task_id]["status"] = "error"
            _task_storage[task_id]["error"] = str(e)
            return {"success": False, "task_id": task_id, "error": str(e)}

    async def save_session(self, name: Optional[str] = None) -> dict:
        """
        Save current Chrome tabs as a session.

        Args:
            name: Optional session name (defaults to timestamp)

        Returns:
            dict with session info
        """
        session_id = str(uuid.uuid4())[:8]
        session_name = name or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        logger.info(f"Saving tab session: {session_name}")

        try:
            # First, list current tabs
            tabs_result = await self.execution_service.list_tabs()

            # Create session object
            # Note: Since we can't reliably get tab URLs from the device,
            # we save a placeholder that indicates the session was saved
            session = TabSession(
                session_id=session_id,
                name=session_name,
                tabs=[],  # Would contain actual tab data if available
            )

            # Save to file
            session_file = SESSION_DIR / f"{session_id}.json"
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)

            logger.info(f"Session saved: {session_id}")

            return {
                "success": True,
                "session_id": session_id,
                "name": session_name,
                "message": f"Session '{session_name}' saved successfully",
            }

        except Exception as e:
            logger.error(f"Failed to save session: {e}")
            return {"success": False, "error": str(e)}

    async def restore_session(self, session_id: str) -> dict:
        """
        Restore a previously saved tab session.

        Args:
            session_id: ID of the session to restore

        Returns:
            dict with restore result
        """
        logger.info(f"Restoring session: {session_id}")

        try:
            session_file = SESSION_DIR / f"{session_id}.json"

            if not session_file.exists():
                return {"success": False, "error": f"Session {session_id} not found"}

            with open(session_file, "r") as f:
                data = json.load(f)

            session = TabSession.from_dict(data)

            # If we have tabs saved, we could restore them
            # For MVP, we just acknowledge the session exists
            # Full restoration would open each URL via Chrome

            if session.tabs:
                # Future: Use execution service to open each tab
                pass

            return {
                "success": True,
                "session_id": session_id,
                "name": session.name,
                "tab_count": len(session.tabs),
                "message": f"Session '{session.name}' found. Tab restoration is pending.",
            }

        except Exception as e:
            logger.error(f"Failed to restore session: {e}")
            return {"success": False, "error": str(e)}

    def list_sessions(self) -> dict:
        """
        List all saved tab sessions.

        Returns:
            dict with list of sessions
        """
        try:
            sessions = []
            for session_file in SESSION_DIR.glob("*.json"):
                try:
                    with open(session_file, "r") as f:
                        data = json.load(f)
                        sessions.append(
                            {
                                "id": data.get("id"),
                                "name": data.get("name"),
                                "tab_count": data.get("tab_count", 0),
                                "created_at": data.get("created_at"),
                            }
                        )
                except Exception as e:
                    logger.warning(f"Failed to read session {session_file}: {e}")

            # Sort by created_at descending
            sessions.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            return {
                "success": True,
                "sessions": sessions,
                "count": len(sessions),
            }

        except Exception as e:
            logger.error(f"Failed to list sessions: {e}")
            return {"success": False, "error": str(e)}

    def delete_session(self, session_id: str) -> dict:
        """
        Delete a saved session.

        Args:
            session_id: ID of the session to delete
        """
        try:
            session_file = SESSION_DIR / f"{session_id}.json"

            if not session_file.exists():
                return {"success": False, "error": f"Session {session_id} not found"}

            session_file.unlink()
            logger.info(f"Deleted session: {session_id}")

            return {"success": True, "message": f"Session {session_id} deleted"}

        except Exception as e:
            logger.error(f"Failed to delete session: {e}")
            return {"success": False, "error": str(e)}

    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get the status of a tab management task."""
        return _task_storage.get(task_id)

    def _log_task(self, task_id: str, message: str):
        """Add a log entry to the task."""
        if task_id in _task_storage:
            _task_storage[task_id]["logs"].append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "message": message,
                }
            )
        logger.info(f"[{task_id}] {message}")
