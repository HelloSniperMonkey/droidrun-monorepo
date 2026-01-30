"""
MobileRun Cloud API data models.
"""
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


class TaskStatusEnum(str, Enum):
    """Status of a MobileRun task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Device(BaseModel):
    """MobileRun device representation."""
    device_id: str = Field(alias="deviceId")
    status: str
    platform: str = "android"
    created_at: Optional[datetime] = None

    class Config:
        populate_by_name = True


class TaskStatus(BaseModel):
    """Status of a MobileRun task."""
    task_id: str = Field(alias="taskId")
    status: TaskStatusEnum
    progress: Optional[int] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    class Config:
        populate_by_name = True


class Task(BaseModel):
    """MobileRun task representation."""
    task_id: str = Field(alias="taskId")
    device_id: str = Field(alias="deviceId")
    command: str
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    screenshots: list[str] = Field(default_factory=list)
    trajectory: list[dict] = Field(default_factory=list)
    stream_url: Optional[str] = None  # For v1 API streaming

    class Config:
        populate_by_name = True


class Screenshot(BaseModel):
    """Screenshot from device."""
    url: Optional[str] = None
    base64: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
