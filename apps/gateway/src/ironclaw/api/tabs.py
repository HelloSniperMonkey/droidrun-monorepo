"""
Tab Manager API endpoints.
Handles Chrome tab organization, cleanup, and session management.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from ..modules.tab_manager import TabManagerService

logger = logging.getLogger("ironclaw.api.tabs")
router = APIRouter()

# In-memory task storage for async execution
# Format: {task_id: {status, steps, message, error, started_at, completed_at}}
task_storage: Dict[str, Dict[str, Any]] = {}


# ============ Request Models ============


class TabOrganizationRequest(BaseModel):
    """Request model for tab organization."""

    pass  # No parameters needed - AI determines groups


class TabCleanupRequest(BaseModel):
    """Request model for tab cleanup."""

    days_old: int = Field(
        default=7, ge=1, le=30, description="Close tabs older than this many days"
    )


class MergeDuplicatesRequest(BaseModel):
    """Request model for merging duplicate tabs."""

    pass  # No parameters needed


class SaveSessionRequest(BaseModel):
    """Request model for saving a tab session."""

    name: Optional[str] = Field(default=None, max_length=100, description="Session name (optional)")


class RestoreSessionRequest(BaseModel):
    """Request model for restoring a tab session."""

    session_id: str = Field(
        ..., min_length=1, max_length=50, description="ID of the session to restore"
    )


class DeleteSessionRequest(BaseModel):
    """Request model for deleting a session."""

    session_id: str = Field(
        ..., min_length=1, max_length=50, description="ID of the session to delete"
    )


# ============ Response Models ============


class TabOperationResponse(BaseModel):
    """Response model for async tab operations."""

    task_id: str
    status: str
    message: str
    steps: Optional[list] = None  # Parsed step information from execution


class TabListResponse(BaseModel):
    """Response model for listing tabs."""

    success: bool
    tabs: Optional[list] = None
    count: int = 0
    task_id: Optional[str] = None
    error: Optional[str] = None
    steps: Optional[list] = None  # Parsed step information from execution


class SessionResponse(BaseModel):
    """Response model for session operations."""

    success: bool
    session_id: Optional[str] = None
    name: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response model for listing sessions."""

    success: bool
    sessions: list = []
    count: int = 0
    error: Optional[str] = None


# ============ Tab Organization Endpoints ============


@router.post("/organize", response_model=TabOperationResponse)
async def organize_tabs(
    background_tasks: BackgroundTasks,
    request: Optional[TabOrganizationRequest] = None,
):
    """
    Organize Chrome tabs into AI-determined groups.

    The AI analyzes tab content and creates logical groups like:
    - Work/Development
    - Social Media
    - Shopping
    - Research
    - Entertainment

    Executes synchronously and returns steps when complete.
    """
    try:
        service = TabManagerService()

        # Generate task ID
        import uuid

        task_id = str(uuid.uuid4())[:8]

        # Execute synchronously to capture steps
        logger.info(f"Starting synchronous tab organization: {task_id}")
        result = await service.organize_tabs(task_id=task_id)

        return TabOperationResponse(
            task_id=task_id,
            status="completed" if result.get("success") else "failed",
            message=result.get("message", "Tab organization completed"),
            steps=result.get("steps", []),
        )
    except Exception as e:
        logger.error(f"Tab organization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-old", response_model=TabOperationResponse)
async def close_old_tabs(
    request: TabCleanupRequest,
    background_tasks: BackgroundTasks,
):
    """
    Close old/stale Chrome tabs.

    Identifies and closes tabs that appear unused or stale.
    Conservative by default - won't close important-looking tabs.

    Executes synchronously and returns steps when complete.
    """
    try:
        service = TabManagerService()

        import uuid

        task_id = str(uuid.uuid4())[:8]

        # Execute synchronously to capture steps
        logger.info(f"Starting synchronous tab cleanup: {task_id}")
        result = await service.close_old_tabs(
            days_old=request.days_old,
            task_id=task_id,
        )

        return TabOperationResponse(
            task_id=task_id,
            status="completed" if result.get("success") else "failed",
            message=result.get("message", f"Tab cleanup completed"),
            steps=result.get("steps", []),
        )
    except Exception as e:
        logger.error(f"Tab cleanup failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/merge-duplicates", response_model=TabOperationResponse)
async def merge_duplicate_tabs(
    background_tasks: BackgroundTasks,
    request: Optional[MergeDuplicatesRequest] = None,
):
    """
    Find and close duplicate Chrome tabs.

    Identifies tabs with the same URL and closes duplicates,
    keeping one instance of each unique URL.

    Executes synchronously and returns steps when complete.
    """
    try:
        service = TabManagerService()

        import uuid

        task_id = str(uuid.uuid4())[:8]

        # Execute synchronously to capture steps
        logger.info(f"Starting synchronous duplicate merge: {task_id}")
        result = await service.merge_duplicate_tabs(
            task_id=task_id,
        )

        return TabOperationResponse(
            task_id=task_id,
            status="completed" if result.get("success") else "failed",
            message=result.get("message", "Duplicate tab merge completed"),
            steps=result.get("steps", []),
        )
    except Exception as e:
        logger.error(f"Duplicate merge failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=TabListResponse)
async def list_tabs():
    """
    Get a list of all currently open Chrome tabs.
    """
    try:
        service = TabManagerService()
        result = await service.list_tabs()
        return TabListResponse(**result)
    except Exception as e:
        logger.error(f"List tabs failed: {e}")
        return TabListResponse(success=False, error=str(e))


# ============ Testing Endpoint ============


@router.post("/test/mock-task")
async def create_mock_task():
    """
    Create a mock task for testing the frontend step display.
    Simulates a successful tab operation with sample steps.
    """
    import uuid

    task_id = str(uuid.uuid4())[:8]

    # Store mock task with sample steps
    task_storage[task_id] = {
        "status": "completed",
        "success": True,
        "message": "Mock tab operation completed successfully",
        "steps": [
            {"step": 1, "description": "Opening Chrome app"},
            {"step": 2, "description": "Tapping tab switcher icon"},
            {"step": 3, "description": "Scrolling through tab list"},
            {"step": 4, "description": "Identifying 6 open tabs"},
            {"step": 5, "description": "Grouping work-related tabs"},
            {"step": 6, "description": "Grouping social media tabs"},
            {"step": 7, "description": "Taking final screenshot"},
        ],
        "started_at": datetime.now().isoformat(),
        "completed_at": datetime.now().isoformat(),
    }

    return TabOperationResponse(
        task_id=task_id,
        status="started",
        message="Mock task created - poll /status/{task_id} to see results",
    )


# ============ Session Management Endpoints ============


@router.post("/save-session", response_model=SessionResponse)
async def save_session(request: SaveSessionRequest):
    """
    Save current Chrome tabs as a session.

    Sessions can be restored later to reopen the same set of tabs.
    """
    try:
        service = TabManagerService()
        result = await service.save_session(name=request.name)

        return SessionResponse(
            success=result.get("success", False),
            session_id=result.get("session_id"),
            name=result.get("name"),
            message=result.get("message"),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Save session failed: {e}")
        return SessionResponse(success=False, error=str(e))


@router.post("/restore-session", response_model=SessionResponse)
async def restore_session(request: RestoreSessionRequest):
    """
    Restore a previously saved tab session.

    Opens all tabs from the saved session in Chrome.
    """
    try:
        service = TabManagerService()
        result = await service.restore_session(session_id=request.session_id)

        return SessionResponse(
            success=result.get("success", False),
            session_id=result.get("session_id"),
            name=result.get("name"),
            message=result.get("message"),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"Restore session failed: {e}")
        return SessionResponse(success=False, error=str(e))


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    """
    List all saved tab sessions.

    Returns a list of sessions with their names, tab counts, and creation dates.
    """
    try:
        service = TabManagerService()
        result = service.list_sessions()

        return SessionListResponse(
            success=result.get("success", False),
            sessions=result.get("sessions", []),
            count=result.get("count", 0),
            error=result.get("error"),
        )
    except Exception as e:
        logger.error(f"List sessions failed: {e}")
        return SessionListResponse(success=False, error=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a saved session.
    """
    try:
        service = TabManagerService()
        result = service.delete_session(session_id=session_id)

        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Session not found"))

        return {"success": True, "message": result.get("message")}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete session failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Status Endpoint ============


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a tab management task.

    Returns the current status, steps, and result of a background task.
    Checks both in-memory task_storage and TabManagerService.
    """
    # First check in-memory storage (for new async tasks)
    if task_id in task_storage:
        return {"task_id": task_id, **task_storage[task_id]}

    # Fallback to TabManagerService (for old implementation)
    service = TabManagerService()
    status = await service.get_task_status(task_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return status
