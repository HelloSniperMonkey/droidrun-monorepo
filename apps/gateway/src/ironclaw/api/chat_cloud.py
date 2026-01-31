"""
Cloud Chat API endpoint - Direct MobileRun API integration.

This endpoint makes direct HTTP requests to the MobileRun API,
bypassing the complex execution service to avoid compatibility issues.
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional, List

import httpx
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Load .env from project root
PROJECT_ROOT = Path(__file__).resolve().parents[6]  # Navigate up to monorepo root
ENV_PATH = PROJECT_ROOT / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    # Fallback: try to find .env by walking up directories
    current = Path(__file__).resolve().parent
    while current != current.parent:
        potential_env = current / ".env"
        if potential_env.exists():
            load_dotenv(potential_env)
            break
        current = current.parent

logger = logging.getLogger("ironclaw.api.chat_cloud")
logger.info(f"Loaded .env from: {ENV_PATH if ENV_PATH.exists() else 'fallback location'}")
router = APIRouter()

MOBILERUN_API_URL = "https://api.mobilerun.ai/v1"


class ChatCloudRequest(BaseModel):
    """Request model for cloud chat."""
    message: str
    device_id: Optional[str] = None  # Can be passed from frontend
    llm_model: Optional[str] = "google/gemini-2.5-flash"
    max_steps: Optional[int] = 100
    vision: Optional[bool] = True
    reasoning: Optional[bool] = True
    temperature: Optional[float] = 0.5
    execution_timeout: Optional[int] = 1000
    wait_for_completion: Optional[bool] = False  # Default to async mode for live updates


class StepInfo(BaseModel):
    """Information about a single step in the task execution."""
    step_number: int
    event: str
    description: Optional[str] = None
    action: Optional[str] = None
    thought: Optional[str] = None
    success: Optional[bool] = None
    timestamp: Optional[str] = None


class TaskStatusResponse(BaseModel):
    """Response model for task status with live steps."""
    task_id: str
    status: str  # created, running, completed, failed, cancelled
    steps: List[StepInfo] = []
    total_steps: int = 0
    final_answer: Optional[str] = None
    success: Optional[bool] = None
    error: Optional[str] = None


class ChatCloudResponse(BaseModel):
    """Response model for cloud chat."""
    success: bool
    task_id: Optional[str] = None
    stream_url: Optional[str] = None
    message: str
    status: Optional[str] = None  # Task status: created, running, completed, failed
    steps: Optional[List[StepInfo]] = None  # Steps taken during execution
    output: Optional[dict] = None  # Structured output if any
    error: Optional[str] = None


def get_mobilerun_api_key() -> str:
    """Get MobileRun API key from environment."""
    api_key = os.getenv("MOBILERUN_API_KEY")
    
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="MOBILERUN_API_KEY not configured. Please set it in .env file."
        )
    
    return api_key


async def get_task_status(api_key: str, task_id: str) -> str:
    """Get the current status of a task."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{MOBILERUN_API_URL}/tasks/{task_id}/status",
            headers=headers,
        )
        
        if response.status_code >= 400:
            logger.error(f"Failed to get task status: {response.status_code} - {response.text}")
            return "unknown"
        
        data = response.json()
        return data.get("status", "unknown")


async def get_task_trajectory(api_key: str, task_id: str) -> tuple[List[StepInfo], Optional[str]]:
    """
    Get the trajectory (steps) of a completed task.
    Returns (steps, final_answer) tuple.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(
            f"{MOBILERUN_API_URL}/tasks/{task_id}/trajectory",
            headers=headers,
        )
        
        if response.status_code >= 400:
            logger.error(f"Failed to get trajectory: {response.status_code} - {response.text}")
            return [], None
        
        data = response.json()
        trajectory = data.get("trajectory", [])
        
        # Parse trajectory events into steps
        steps = []
        step_number = 0
        final_answer = None
        
        for event in trajectory:
            event_type = event.get("event", "")
            event_data = event.get("data", {})
            
            # Extract meaningful steps from ExecutorActionEvent (actual actions taken)
            if event_type == "ExecutorActionEvent":
                step_number += 1
                description = event_data.get("description") or ""
                action_json = event_data.get("action_json", "")
                
                step = StepInfo(
                    step_number=step_number,
                    event=event_type,
                    description=description,
                    action=action_json,
                    thought=event_data.get("thought"),
                    success=None,  # Will be updated by result event
                )
                steps.append(step)
            
            # ManagerPlanDetailsEvent shows the plan and current subgoal
            elif event_type == "ManagerPlanDetailsEvent":
                subgoal = event_data.get("subgoal", "")
                thought = event_data.get("thought", "")
                answer = event_data.get("answer", "")
                
                # If there's an answer, this might be the final answer
                if answer:
                    final_answer = answer
                
                # Only add as a step if there's a meaningful subgoal and no action step follows
                if subgoal and thought:
                    step_number += 1
                    steps.append(StepInfo(
                        step_number=step_number,
                        event=event_type,
                        description=subgoal,
                        thought=thought,
                        success=event_data.get("success"),
                    ))
            
            # Update the last step with success info from action result
            elif event_type == "ExecutorActionResultEvent":
                if steps:
                    action_data = event_data.get("action", {})
                    steps[-1].success = event_data.get("success")
                    if not steps[-1].action and action_data:
                        steps[-1].action = str(action_data)
            
            # Capture final result - this contains the final answer/reason
            elif event_type == "ResultEvent":
                reason = event_data.get("reason", "")
                success = event_data.get("success", True)
                
                # The reason is often the final answer
                if reason:
                    final_answer = reason
                
                step_number += 1
                steps.append(StepInfo(
                    step_number=step_number,
                    event=event_type,
                    description=reason or "Task completed",
                    success=success,
                ))
            
            # FinalizeEvent also contains useful info
            elif event_type == "FinalizeEvent":
                reason = event_data.get("reason", "")
                if reason and not final_answer:
                    final_answer = reason
        
        # Remove duplicate/empty steps
        filtered_steps = []
        seen_descriptions = set()
        for step in steps:
            desc = step.description or ""
            if desc and desc not in seen_descriptions:
                seen_descriptions.add(desc)
                filtered_steps.append(step)
            elif not desc and step.event == "ResultEvent":
                # Keep result event even if empty description
                filtered_steps.append(step)
        
        # Re-number steps
        for i, step in enumerate(filtered_steps):
            step.step_number = i + 1
        
        return filtered_steps, final_answer


async def wait_for_task_completion(
    api_key: str, 
    task_id: str, 
    poll_interval: float = 2.0,
    max_wait_time: float = 300.0
) -> tuple[str, bool]:
    """
    Poll the task status until it's completed or failed.
    Returns (status, success) tuple.
    """
    elapsed = 0.0
    terminal_statuses = {"completed", "failed", "cancelled"}
    
    while elapsed < max_wait_time:
        status = await get_task_status(api_key, task_id)
        logger.info(f"Task {task_id} status: {status} (elapsed: {elapsed:.1f}s)")
        
        if status in terminal_statuses:
            success = status == "completed"
            return status, success
        
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    
    logger.warning(f"Task {task_id} timed out after {max_wait_time}s")
    return "timeout", False


async def fetch_ready_device(api_key: str) -> Optional[str]:
    """
    Fetch the list of devices and return the first ready device ID.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MOBILERUN_API_URL}/devices",
                headers=headers,
            )
            
            if response.status_code >= 400:
                logger.error(f"Failed to fetch devices: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            # Handle different response formats: {items: [...]} or {devices: [...]} or [...]
            devices = data.get("items") or data.get("devices") or (data if isinstance(data, list) else [])
            
            logger.info(f"Fetched {len(devices)} devices")
            
            # Find the first device that is ready (check both 'state' and 'status' fields)
            for device in devices:
                state = (device.get("state") or device.get("status") or "").lower()
                if state == "ready":
                    device_id = device.get("id") or device.get("deviceId")
                    logger.info(f"Found ready device: {device_id} (name: {device.get('name', 'unknown')})")
                    return device_id
            
            # If no ready device, check for assigned devices
            for device in devices:
                state = (device.get("state") or device.get("status") or "").lower()
                if state == "assigned":
                    device_id = device.get("id") or device.get("deviceId")
                    logger.info(f"Found assigned device: {device_id} (name: {device.get('name', 'unknown')})")
                    return device_id
            
            # If no ready/assigned device, return the first non-terminated device
            for device in devices:
                state = (device.get("state") or device.get("status") or "").lower()
                if state != "terminated":
                    device_id = device.get("id") or device.get("deviceId")
                    logger.warning(f"No ready device found, using device: {device_id} (state: {state})")
                    return device_id
                
            return None
            
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        return None


async def get_device_id(api_key: str, request_device_id: Optional[str] = None) -> str:
    """
    Get device ID from request, environment, or fetch from API.
    Priority: request > env > fetch from API
    """
    # 1. Use device ID from request if provided
    if request_device_id:
        logger.info(f"Using device ID from request: {request_device_id}")
        return request_device_id
    
    # 2. Check environment variable
    env_device_id = os.getenv("MOBILERUN_DEVICE_ID")
    if env_device_id:
        logger.info(f"Using device ID from environment: {env_device_id}")
        return env_device_id
    
    # 3. Fetch from API and get the first ready device
    fetched_device_id = await fetch_ready_device(api_key)
    if fetched_device_id:
        return fetched_device_id
    
    raise HTTPException(
        status_code=500,
        detail="No device ID provided and no ready devices found. Please select a device."
    )


@router.post("/chat-cloud", response_model=ChatCloudResponse)
async def chat_cloud_handler(request: ChatCloudRequest):
    """
    Handle chat messages using MobileRun Cloud API directly.
    
    This endpoint makes a simple HTTP request to the MobileRun API,
    avoiding any complex client dependencies that might cause issues.
    """
    logger.info(f"Cloud chat request: {request.message[:50]}...")
    
    try:
        api_key = get_mobilerun_api_key()
        device_id = await get_device_id(api_key, request.device_id)
        
        # Build the request payload matching MobileRun API spec
        payload = {
            "llmModel": request.llm_model,
            "task": request.message,
            "deviceId": device_id,
            "maxSteps": request.max_steps,
            "vision": request.vision,
            "reasoning": request.reasoning,
            "temperature": request.temperature,
            "executionTimeout": request.execution_timeout,
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        logger.info(f"Sending request to MobileRun API with model: {request.llm_model}")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{MOBILERUN_API_URL}/tasks/",
                json=payload,
                headers=headers,
            )
            
            if response.status_code >= 400:
                error_text = response.text
                logger.error(f"MobileRun API error: {response.status_code} - {error_text}")
                return ChatCloudResponse(
                    success=False,
                    message="MobileRun API request failed",
                    error=f"API returned {response.status_code}: {error_text}",
                )
            
            data = response.json()
            
            # MobileRun API returns: {"id": "...", "streamUrl": "...", "token": "..."}
            task_id = data.get("id")
            stream_url = data.get("streamUrl")
            
            logger.info(f"Task created successfully: {task_id}")
            
            # Return immediately - frontend will poll /tasks/{task_id} for live updates
            return ChatCloudResponse(
                success=True,
                task_id=task_id,
                stream_url=stream_url,
                message=f"Task started. Poll /api/chat-cloud/tasks/{task_id} for live updates.",
                status="created",
            )
            
    except httpx.TimeoutException:
        logger.error("MobileRun API request timed out")
        return ChatCloudResponse(
            success=False,
            message="Request timed out",
            error="The MobileRun API did not respond in time. Please try again.",
        )
    except httpx.HTTPError as e:
        logger.error(f"HTTP error communicating with MobileRun API: {e}")
        return ChatCloudResponse(
            success=False,
            message="Failed to communicate with MobileRun API",
            error=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in chat_cloud: {e}", exc_info=True)
        return ChatCloudResponse(
            success=False,
            message="An unexpected error occurred",
            error=str(e),
        )


@router.get("/chat-cloud/status/{task_id}")
async def get_task_status_endpoint(task_id: str):
    """
    Get the status of a cloud task (simple status only).
    """
    try:
        api_key = get_mobilerun_api_key()
        status = await get_task_status(api_key, task_id)
        return {"task_id": task_id, "status": status}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-cloud/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_with_steps(task_id: str):
    """
    Get task status with live steps - use this endpoint for polling.
    
    Returns current status and all steps completed so far.
    Frontend should poll this endpoint every 1-2 seconds while status is 'running'.
    """
    try:
        api_key = get_mobilerun_api_key()
        
        # Get current status
        status = await get_task_status(api_key, task_id)
        
        # Get trajectory (steps completed so far)
        steps, final_answer = await get_task_trajectory(api_key, task_id)
        
        # Determine success based on status
        success = None
        error = None
        if status == "completed":
            success = True
        elif status in ("failed", "cancelled"):
            success = False
            error = f"Task {status}"
        
        return TaskStatusResponse(
            task_id=task_id,
            status=status,
            steps=steps,
            total_steps=len(steps),
            final_answer=final_answer,
            success=success,
            error=error,
        )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task with steps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-cloud/devices")
async def list_devices():
    """
    List all available MobileRun devices.
    """
    try:
        api_key = get_mobilerun_api_key()
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{MOBILERUN_API_URL}/devices",
                headers=headers,
            )
            
            if response.status_code >= 400:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"MobileRun API error: {response.text}",
                )
            
            return response.json()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat-cloud/trajectory/{task_id}")
async def get_task_trajectory_endpoint(task_id: str):
    """
    Get the trajectory (steps) of a task.
    """
    try:
        api_key = get_mobilerun_api_key()
        steps, final_answer = await get_task_trajectory(api_key, task_id)
        
        return {
            "task_id": task_id,
            "steps": [step.model_dump() for step in steps],
            "total_steps": len(steps),
            "final_answer": final_answer,
        }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trajectory: {e}")
        raise HTTPException(status_code=500, detail=str(e))
