"""
Temporal Guardian API endpoints.
Handles alarm scheduling and calendar management.
"""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..modules.temporal_guardian import TemporalGuardianService

logger = logging.getLogger("ironclaw.api.alarms")
router = APIRouter()


class SetAlarmRequest(BaseModel):
    """Request model for setting an alarm."""
    hour: int  # 0-23
    minute: int  # 0-59
    label: Optional[str] = None
    days: Optional[list[str]] = None  # e.g., ["monday", "tuesday"]


class SetAlarmResponse(BaseModel):
    """Response model for alarm operations."""
    success: bool
    message: str
    alarm_time: Optional[str] = None


class ScheduleEventRequest(BaseModel):
    """Request model for scheduling a calendar event."""
    title: str
    start_time: datetime
    end_time: Optional[datetime] = None
    description: Optional[str] = None


@router.post("/set", response_model=SetAlarmResponse)
async def set_alarm(request: SetAlarmRequest):
    """
    Set an alarm on the Android device.
    Uses native Android intents for reliability.
    """
    # Validate time
    if not (0 <= request.hour <= 23):
        raise HTTPException(status_code=400, detail="Hour must be 0-23")
    if not (0 <= request.minute <= 59):
        raise HTTPException(status_code=400, detail="Minute must be 0-59")

    try:
        service = TemporalGuardianService()
        result = await service.set_alarm(
            hour=request.hour,
            minute=request.minute,
            label=request.label,
        )

        alarm_time = f"{request.hour:02d}:{request.minute:02d}"
        return SetAlarmResponse(
            success=result,
            message=f"Alarm set for {alarm_time}" if result else "Failed to set alarm",
            alarm_time=alarm_time if result else None,
        )
    except Exception as e:
        logger.error(f"Failed to set alarm: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cancel")
async def cancel_alarm():
    """Cancel all pending alarms (opens clock app for manual selection)."""
    try:
        service = TemporalGuardianService()
        await service.open_clock_app()
        return {"success": True, "message": "Clock app opened for manual alarm management"}
    except Exception as e:
        logger.error(f"Failed to open clock app: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calendar/event")
async def schedule_event(request: ScheduleEventRequest):
    """
    Schedule a calendar event.
    Opens the calendar app and creates an event.
    """
    try:
        service = TemporalGuardianService()
        result = await service.create_calendar_event(
            title=request.title,
            start_time=request.start_time,
            end_time=request.end_time,
            description=request.description,
        )
        return {"success": result, "event": request.title}
    except Exception as e:
        logger.error(f"Failed to schedule event: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time")
async def get_device_time():
    """Get the current time from the connected Android device."""
    try:
        service = TemporalGuardianService()
        device_time = await service.get_device_time()
        return {"device_time": device_time}
    except Exception as e:
        logger.error(f"Failed to get device time: {e}")
        raise HTTPException(status_code=500, detail=str(e))
