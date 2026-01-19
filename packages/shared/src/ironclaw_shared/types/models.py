"""
Shared Pydantic models for Iron Claw.
These models are used across all services for consistent data structures.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .enums import HITLType, TaskStatusEnum


class TaskStatus(BaseModel):
    """Status of a background task."""
    task_id: str
    status: TaskStatusEnum
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    result: Optional[dict] = None
    error: Optional[str] = None


class TaskState(BaseModel):
    """Full state of a running task."""
    task_id: str
    status: TaskStatusEnum
    module: str
    query: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    logs: list[dict] = Field(default_factory=list)
    result: Optional[dict] = None
    hitl_request: Optional["HITLRequest"] = None


class BioMemory(BaseModel):
    """User profile/bio-memory for form filling."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)
    resume_file: Optional[str] = None
    resume_text: Optional[str] = None
    urls: dict[str, str] = Field(default_factory=dict)  # linkedin, github, etc.
    parsed_at: Optional[datetime] = None


class JobSearchRequest(BaseModel):
    """Request for job search and application."""
    query: str
    max_applications: int = 3
    filters: Optional[dict] = None


class JobSearchResult(BaseModel):
    """Result of a job search task."""
    success: bool
    applications_submitted: int = 0
    jobs_found: int = 0
    errors: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)


class AlarmRequest(BaseModel):
    """Request to set an alarm."""
    hour: int = Field(ge=0, le=23)
    minute: int = Field(ge=0, le=59)
    label: Optional[str] = None


class WakeCallRequest(BaseModel):
    """Request for a wake-up call."""
    phone_number: str
    scheduled_time: Optional[datetime] = None  # If None, call immediately
    custom_message: Optional[str] = None
    verification_question: Optional[str] = None


class HITLRequest(BaseModel):
    """Request for human-in-the-loop intervention."""
    request_id: str
    task_id: str
    hitl_type: HITLType
    message: str
    screenshot_base64: Optional[str] = None
    options: list[str] = Field(default_factory=lambda: ["Retry", "Abort", "I solved it"])
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class HITLResponse(BaseModel):
    """Response from human to HITL request."""
    request_id: str
    action: str  # One of the options or custom response
    custom_input: Optional[str] = None
    resolved_at: datetime = Field(default_factory=datetime.now)


class DeviceLocation(BaseModel):
    """Device GPS location and timezone."""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: str = "UTC"


class AgentResult(BaseModel):
    """Result from IronClawAgent execution."""
    success: bool
    reason: Optional[str] = None
    steps: int = 0
    output: Optional[Any] = None
    error: Optional[str] = None
    screenshots: list[str] = Field(default_factory=list)
