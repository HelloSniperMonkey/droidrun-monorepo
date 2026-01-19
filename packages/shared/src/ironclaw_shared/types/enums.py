"""
Shared enumerations for Iron Claw.
"""
from enum import Enum


class TaskStatusEnum(str, Enum):
    """Status of a background task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    WAITING_HITL = "waiting_hitl"  # Waiting for human intervention
    CANCELLED = "cancelled"


class HITLType(str, Enum):
    """Type of human-in-the-loop intervention needed."""
    CAPTCHA = "captcha"
    LOGIN_REQUIRED = "login_required"
    CONFIRMATION = "confirmation"
    FILE_UPLOAD = "file_upload"
    CUSTOM = "custom"


class ModuleType(str, Enum):
    """Available Iron Claw modules."""
    JOB_HUNTER = "job_hunter"
    TEMPORAL_GUARDIAN = "temporal_guardian"
    VAPI_INTERRUPTER = "vapi_interrupter"
