"""
Tab Manager API endpoints.
Handles Chrome tab organization, cleanup, and session management.
"""

import logging
import asyncio
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


# ============ Helper Functions ============


async def run_agent_task_background(task_id: str, goal: str):
    """
    Run an IronClaw agent task in the background and update task_storage.
    This allows real-time step tracking via the /status endpoint.
    """
    try:
        from ..agents.ironclaw_agent import create_ironclaw_agent

        logger.info(f"[{task_id}] Starting agent task: {goal[:50]}...")

        # Create and run agent
        agent = await create_ironclaw_agent(goal=goal)
        result = await agent.run()

        logger.info(f"[{task_id}] Agent result keys: {list(result.keys())}")
        logger.info(
            f"[{task_id}] Raw steps type: {type(result.get('steps'))}, value: {result.get('steps')}"
        )

        # Extract steps and convert to frontend format
        raw_steps = result.get("steps", [])
        formatted_steps = []

        if raw_steps:
            total_steps = len(raw_steps)
            for i, step in enumerate(raw_steps, 1):
                if isinstance(step, str):
                    formatted_steps.append(
                        {"step_number": i, "total_steps": total_steps, "description": step}
                    )
                elif isinstance(step, dict):
                    # Already formatted or has custom structure
                    formatted_steps.append(
                        {
                            "step_number": step.get("step_number", i),
                            "total_steps": step.get("total_steps", total_steps),
                            "description": step.get("description", str(step)),
                        }
                    )

        # Update task storage with final result
        task_storage[task_id].update(
            {
                "status": "completed" if result.get("success") else "failed",
                "success": result.get("success", False),
                "message": result.get("reason", "Task completed"),
                "steps": formatted_steps,
                "output": result.get("output"),
                "completed_at": datetime.now().isoformat(),
            }
        )

        logger.info(f"[{task_id}] Task completed with {len(formatted_steps)} formatted steps")

    except Exception as e:
        logger.error(f"[{task_id}] Task failed: {e}")
        task_storage[task_id].update(
            {
                "status": "failed",
                "success": False,
                "error": str(e),
                "completed_at": datetime.now().isoformat(),
            }
        )


async def run_agent_task_with_steps(task_id: str, goal: str):
    """
    Run an IronClaw agent task with live step streaming to task_storage.
    Steps are updated in real-time as the agent executes each action.
    Errors are gracefully handled and never exposed raw to the frontend.
    """
    step_counter = 0
    
    def add_step(description: str, action: str = None):
        """Add a step to the task storage for real-time frontend updates."""
        nonlocal step_counter
        step_counter += 1
        step_info = {
            "step_number": step_counter,
            "total_steps": step_counter,  # Updates as we progress
            "description": description,
            "action": action,
        }
        task_storage[task_id]["steps"].append(step_info)
        logger.info(f"[{task_id}] Step {step_counter}: {description}")
    
    try:
        from ..agents.ironclaw_agent import create_ironclaw_agent

        logger.info(f"[{task_id}] Starting agent task with step streaming: {goal[:50]}...")
        add_step("Initializing agent...", "init")

        # Create agent
        agent = await create_ironclaw_agent(goal=goal)
        add_step("Agent created, starting execution...", "create")

        # Run agent
        result = await agent.run()

        logger.info(f"[{task_id}] Agent result keys: {list(result.keys())}")

        # Extract any additional steps from the agent result
        raw_steps = result.get("steps", [])
        if raw_steps:
            for step in raw_steps:
                if isinstance(step, str):
                    add_step(step)
                elif isinstance(step, dict):
                    add_step(
                        step.get("description") or step.get("action") or str(step),
                        step.get("action")
                    )

        # Determine success message
        success = result.get("success", False)
        if success:
            message = result.get("reason") or result.get("output") or "Task completed successfully"
            add_step(f"Completed: {message}", "complete")
        else:
            # Don't expose raw errors - provide user-friendly message
            message = result.get("reason") or "Task encountered an issue, please try again"
            add_step(f"Finished: {message}", "finish")

        # Update final step counts
        total_steps = len(task_storage[task_id]["steps"])
        for step in task_storage[task_id]["steps"]:
            step["total_steps"] = total_steps

        # Update task storage with final result
        task_storage[task_id].update(
            {
                "status": "completed",
                "success": success,
                "message": message,
                "output": result.get("output"),
                "completed_at": datetime.now().isoformat(),
            }
        )

        logger.info(f"[{task_id}] Task completed with {total_steps} steps")

    except Exception as e:
        logger.error(f"[{task_id}] Task failed with exception: {e}")
        
        # Add a graceful step instead of exposing error
        add_step("Task completed with issues, please try again", "error")
        
        # Update final step counts
        total_steps = len(task_storage[task_id]["steps"])
        for step in task_storage[task_id]["steps"]:
            step["total_steps"] = total_steps
        
        # Never return raw errors to frontend - provide friendly message
        task_storage[task_id].update(
            {
                "status": "completed",  # Mark as completed, not failed, to show steps
                "success": False,
                "message": "Task completed. Check the steps for details.",
                "completed_at": datetime.now().isoformat(),
            }
        )


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


@router.post("/test/check-android-version")
async def check_android_version(background_tasks: BackgroundTasks):
    """
    Check Android version by navigating to Settings.

    This demonstrates:
    - Real agent execution with actual device interaction
    - Background task processing
    - Live step tracking via /status endpoint
    - End-to-end polling from frontend

    The agent will:
    1. Open Settings app
    2. Search for "Android version"
    3. Find and report the version number
    """
    import uuid

    task_id = str(uuid.uuid4())[:8]

    # Initialize task in storage with "running" status
    task_storage[task_id] = {
        "status": "running",
        "success": None,
        "message": "Checking Android version...",
        "steps": [],
        "started_at": datetime.now().isoformat(),
    }

    # Define the agent goal
    goal = """
    Go to Settings and find the Android version.
    
    Steps:
    1. Open the Settings app
    2. Scroll down to find "About phone" or "About device"
    3. Tap on it
    4. Look for "Android version" 
    5. Read and report the version number
    
    Important: Once you see the Android version on screen, STOP and report it.
    """

    # Run agent task in background with step streaming
    background_tasks.add_task(run_agent_task_with_steps, task_id, goal)

    logger.info(f"Started Android version check task: {task_id}")

    return TabOperationResponse(
        task_id=task_id,
        status="started",
        message="Checking Android version... Poll /status/{task_id} for updates",
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
