"""
HITL (Human-in-the-Loop) API endpoints.
Allows users to view and respond to intervention requests.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services.hitl_service import get_hitl_service

logger = logging.getLogger("ironclaw.api.hitl")
router = APIRouter()


class HITLResponseRequest(BaseModel):
    """Request model for responding to HITL."""
    action: str
    custom_input: Optional[str] = None


class HITLRequestResponse(BaseModel):
    """Response model for HITL request details."""
    request_id: str
    task_id: str
    hitl_type: str
    message: str
    options: list[str]
    status: str
    created_at: str
    expires_at: str
    has_screenshot: bool = False


@router.get("/pending")
async def get_pending_requests(task_id: Optional[str] = None):
    """
    Get all pending HITL requests.
    Optionally filter by task_id.
    """
    service = get_hitl_service()
    requests = await service.get_pending_requests(task_id)

    # Remove screenshot data from response (too large)
    result = []
    for req in requests:
        req_copy = req.copy()
        req_copy["has_screenshot"] = bool(req_copy.pop("screenshot_base64", None))
        result.append(req_copy)

    return {"requests": result}


@router.get("/{request_id}")
async def get_request(request_id: str):
    """Get details of a specific HITL request."""
    service = get_hitl_service()
    request = await service.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="HITL request not found")

    # Include screenshot availability
    request_copy = request.copy()
    request_copy["has_screenshot"] = bool(request_copy.get("screenshot_base64"))

    return request_copy


@router.get("/{request_id}/screenshot")
async def get_screenshot(request_id: str):
    """Get the screenshot for a HITL request (base64 encoded)."""
    service = get_hitl_service()
    request = await service.get_request(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="HITL request not found")

    screenshot = request.get("screenshot_base64")
    if not screenshot:
        raise HTTPException(status_code=404, detail="No screenshot available")

    return {"screenshot_base64": screenshot}


@router.post("/{request_id}/respond")
async def respond_to_request(request_id: str, response: HITLResponseRequest):
    """
    Respond to a HITL request.

    Actions:
    - "Retry": Agent will retry the current step
    - "Abort": Agent will abort the task
    - "I solved it": Agent will continue from current state
    - Custom action with custom_input
    """
    service = get_hitl_service()
    success = await service.respond_hitl(
        request_id=request_id,
        action=response.action,
        custom_input=response.custom_input,
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to respond - request not found or already resolved"
        )

    return {"success": True, "message": f"Response recorded: {response.action}"}


@router.delete("/{request_id}")
async def cancel_request(request_id: str):
    """Cancel a pending HITL request."""
    service = get_hitl_service()
    success = await service.cancel_request(request_id)

    if not success:
        raise HTTPException(status_code=404, detail="HITL request not found")

    return {"success": True, "message": "Request cancelled"}
