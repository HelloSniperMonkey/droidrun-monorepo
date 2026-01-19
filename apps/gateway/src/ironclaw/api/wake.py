"""
Active Interrupter (Vapi Wake-up Call) API endpoints.
Handles voice call scheduling and wake-up verification.
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..modules.vapi_interrupter import VapiInterrupterService
from ..utils.config import get_settings

logger = logging.getLogger("ironclaw.api.wake")
router = APIRouter()


class WakeCallRequest(BaseModel):
    """Request model for wake-up call."""
    phone_number: Optional[str] = None  # Uses default from config if not provided
    message: Optional[str] = None  # Custom wake-up message
    verification_question: Optional[str] = None  # e.g., "What is 7 times 8?"


class WakeCallResponse(BaseModel):
    """Response model for wake-up call."""
    success: bool
    call_id: Optional[str] = None
    message: str


class ScheduleWakeRequest(BaseModel):
    """Request model for scheduling a wake-up call."""
    hour: int  # 0-23, in user's local timezone
    minute: int  # 0-59
    phone_number: Optional[str] = None
    use_device_location: bool = True  # Auto-detect timezone from device


@router.post("/call-now", response_model=WakeCallResponse)
async def trigger_wake_call(request: WakeCallRequest):
    """
    Immediately trigger a wake-up call.
    The AI will call and verify the user is awake.
    """
    settings = get_settings()

    if not settings.vapi_api_key:
        raise HTTPException(status_code=503, detail="Vapi not configured")

    phone_number = request.phone_number or settings.user_phone_number
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number required")

    try:
        service = VapiInterrupterService()
        call_id = await service.trigger_wake_call(
            phone_number=phone_number,
            custom_message=request.message,
            verification_question=request.verification_question,
        )

        return WakeCallResponse(
            success=True,
            call_id=call_id,
            message=f"Wake-up call initiated to {phone_number}",
        )
    except Exception as e:
        logger.error(f"Failed to trigger wake call: {e}")
        return WakeCallResponse(
            success=False,
            message=str(e),
        )


@router.post("/schedule")
async def schedule_wake_call(request: ScheduleWakeRequest):
    """
    Schedule a wake-up call for a specific time.
    If use_device_location is true, timezone is determined from the Android device's GPS.
    """
    settings = get_settings()

    if not settings.vapi_api_key:
        raise HTTPException(status_code=503, detail="Vapi not configured")

    # Validate time
    if not (0 <= request.hour <= 23):
        raise HTTPException(status_code=400, detail="Hour must be 0-23")
    if not (0 <= request.minute <= 59):
        raise HTTPException(status_code=400, detail="Minute must be 0-59")

    phone_number = request.phone_number or settings.user_phone_number
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number required")

    try:
        service = VapiInterrupterService()
        job_id = await service.schedule_wake_call(
            hour=request.hour,
            minute=request.minute,
            phone_number=phone_number,
            use_device_location=request.use_device_location,
        )

        return {
            "success": True,
            "job_id": job_id,
            "scheduled_time": f"{request.hour:02d}:{request.minute:02d}",
            "message": "Wake-up call scheduled",
        }
    except Exception as e:
        logger.error(f"Failed to schedule wake call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/location")
async def get_device_location():
    """
    Get the current location and timezone from the Android device.
    Used for timezone-aware scheduling.
    """
    try:
        service = VapiInterrupterService()
        location = await service.get_device_location()
        return location
    except Exception as e:
        logger.error(f"Failed to get device location: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/schedule/{job_id}")
async def cancel_scheduled_wake(job_id: str):
    """Cancel a scheduled wake-up call."""
    try:
        service = VapiInterrupterService()
        result = await service.cancel_scheduled_call(job_id)
        return {"success": result, "message": "Scheduled call cancelled" if result else "Job not found"}
    except Exception as e:
        logger.error(f"Failed to cancel scheduled call: {e}")
        raise HTTPException(status_code=500, detail=str(e))
