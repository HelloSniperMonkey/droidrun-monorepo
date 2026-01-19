"""
Tests for shared types and models.
"""

import pytest
from ironclaw_shared.types import (
    AlarmRequest,
    BioMemory,
    HITLRequest,
    HITLType,
    TaskStatus,
    TaskStatusEnum,
)


class TestTaskStatus:
    """Tests for TaskStatus model."""

    def test_creation(self):
        status = TaskStatus(
            task_id="test-123",
            status=TaskStatusEnum.RUNNING,
        )
        assert status.task_id == "test-123"
        assert status.status == TaskStatusEnum.RUNNING
        assert status.created_at is not None

    def test_with_result(self):
        status = TaskStatus(
            task_id="test-123",
            status=TaskStatusEnum.COMPLETED,
            result={"success": True, "count": 5},
        )
        assert status.result["success"] is True


class TestBioMemory:
    """Tests for BioMemory model."""

    def test_empty_creation(self):
        bio = BioMemory()
        assert bio.name is None
        assert bio.skills == []
        assert bio.urls == {}

    def test_full_creation(self):
        bio = BioMemory(
            name="John Doe",
            email="john@example.com",
            skills=["Python", "JavaScript"],
            urls={"linkedin": "https://linkedin.com/in/johndoe"},
        )
        assert bio.name == "John Doe"
        assert len(bio.skills) == 2


class TestAlarmRequest:
    """Tests for AlarmRequest model."""

    def test_valid_time(self):
        alarm = AlarmRequest(hour=7, minute=30, label="Wake up")
        assert alarm.hour == 7
        assert alarm.minute == 30

    def test_invalid_hour(self):
        with pytest.raises(ValueError):
            AlarmRequest(hour=25, minute=0)

    def test_invalid_minute(self):
        with pytest.raises(ValueError):
            AlarmRequest(hour=7, minute=60)


class TestHITLRequest:
    """Tests for HITLRequest model."""

    def test_creation(self):
        hitl = HITLRequest(
            request_id="hitl-123",
            task_id="task-456",
            hitl_type=HITLType.CAPTCHA,
            message="Please solve the CAPTCHA",
        )
        assert hitl.hitl_type == HITLType.CAPTCHA
        assert "Retry" in hitl.options  # Default options
