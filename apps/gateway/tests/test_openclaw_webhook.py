"""
Unit tests for OpenClaw webhook integration.

Tests cover:
- Token validation (valid, invalid, missing)
- Webhook request parsing
- Task queueing and status
- Execute-step, query-status, cancel-task flows
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

# Set test token before importing the modules
import os
os.environ["OPENCLAW_HOOK_TOKEN"] = "test-secret-token"


class TestOpenClawWebhook:
    """Tests for the OpenClaw webhook endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client with mocked settings."""
        from ironclaw.main import app
        return TestClient(app)

    @pytest.fixture
    def valid_token(self):
        """Valid authorization token."""
        return "Bearer test-secret-token"

    @pytest.fixture
    def invalid_token(self):
        """Invalid authorization token."""
        return "Bearer wrong-token"

    @pytest.fixture
    def sample_execute_payload(self):
        """Sample execute-step webhook payload."""
        return {
            "taskId": "test-task-001",
            "type": "execute-step",
            "metadata": {
                "source": "openclaw",
                "timestamp": "2025-01-31T00:00:00Z",
            },
            "payload": {
                "stepType": "log",
                "params": {
                    "message": "Hello from OpenClaw test",
                },
            },
        }

    @pytest.fixture
    def sample_http_action_payload(self):
        """Sample HTTP action webhook payload."""
        return {
            "taskId": "test-task-002",
            "type": "execute-step",
            "metadata": {
                "source": "openclaw",
            },
            "payload": {
                "stepType": "http_action",
                "params": {
                    "url": "https://example.com/api",
                    "method": "GET",
                },
            },
        }

    # === Token Validation Tests ===

    def test_webhook_missing_auth_returns_401(self, client, sample_execute_payload):
        """Test that missing authorization returns 401."""
        response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
        )
        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_webhook_invalid_token_returns_403(
        self, client, invalid_token, sample_execute_payload
    ):
        """Test that invalid token returns 403."""
        response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
            headers={"Authorization": invalid_token},
        )
        assert response.status_code == 403
        assert "invalid" in response.json()["detail"].lower()

    def test_webhook_malformed_auth_header(self, client, sample_execute_payload):
        """Test that malformed auth header returns 401."""
        # Missing 'Bearer' prefix
        response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
            headers={"Authorization": "test-secret-token"},
        )
        assert response.status_code == 401

    # === Successful Webhook Tests ===

    def test_webhook_execute_step_success(
        self, client, valid_token, sample_execute_payload
    ):
        """Test successful execute-step webhook."""
        response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True
        assert "runId" in data
        assert data["status"] == "queued"

    def test_webhook_http_action_success(
        self, client, valid_token, sample_http_action_payload
    ):
        """Test successful HTTP action webhook."""
        response = client.post(
            "/openclaw/webhook",
            json=sample_http_action_payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["ok"] is True
        assert "runId" in data

    def test_webhook_returns_unique_run_ids(
        self, client, valid_token, sample_execute_payload
    ):
        """Test that each webhook call returns a unique runId."""
        run_ids = set()

        for _ in range(5):
            response = client.post(
                "/openclaw/webhook",
                json=sample_execute_payload,
                headers={"Authorization": valid_token},
            )
            assert response.status_code == 202
            run_ids.add(response.json()["runId"])

        assert len(run_ids) == 5  # All unique

    # === Query Status Tests ===

    def test_query_status_for_queued_task(
        self, client, valid_token, sample_execute_payload
    ):
        """Test querying status of a queued task."""
        # First, create a task
        create_response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
            headers={"Authorization": valid_token},
        )
        run_id = create_response.json()["runId"]

        # Then query its status
        status_response = client.get(
            f"/openclaw/tasks/{run_id}",
            headers={"Authorization": valid_token},
        )

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["ok"] is True
        assert data["runId"] == run_id
        assert data["status"] in ["queued", "running", "completed"]

    def test_query_status_not_found(self, client, valid_token):
        """Test querying status for non-existent task."""
        response = client.get(
            "/openclaw/tasks/nonexistent-run-id",
            headers={"Authorization": valid_token},
        )
        assert response.status_code == 404

    def test_query_status_requires_auth(self, client):
        """Test that query status requires authorization."""
        response = client.get("/openclaw/tasks/some-run-id")
        assert response.status_code == 403

    # === Cancel Task Tests ===

    def test_cancel_task_success(self, client, valid_token, sample_execute_payload):
        """Test cancelling a queued task."""
        # Create a task
        create_response = client.post(
            "/openclaw/webhook",
            json=sample_execute_payload,
            headers={"Authorization": valid_token},
        )
        run_id = create_response.json()["runId"]

        # Cancel it
        cancel_response = client.delete(
            f"/openclaw/tasks/{run_id}",
            headers={"Authorization": valid_token},
        )

        # Note: Task might already be completed by the time we cancel
        # So we accept either success or "cannot cancel" error
        assert cancel_response.status_code in [200, 400]

    def test_cancel_nonexistent_task(self, client, valid_token):
        """Test cancelling a non-existent task."""
        response = client.delete(
            "/openclaw/tasks/nonexistent-run-id",
            headers={"Authorization": valid_token},
        )
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    # === List Tasks Tests ===

    def test_list_tasks_empty(self, client, valid_token):
        """Test listing tasks returns valid response."""
        response = client.get(
            "/openclaw/tasks",
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "tasks" in data
        assert "total" in data

    def test_list_tasks_with_limit(self, client, valid_token, sample_execute_payload):
        """Test listing tasks with limit parameter."""
        # Create a few tasks
        for _ in range(3):
            client.post(
                "/openclaw/webhook",
                json=sample_execute_payload,
                headers={"Authorization": valid_token},
            )

        # List with limit
        response = client.get(
            "/openclaw/tasks?limit=2",
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["tasks"]) <= 2

    def test_list_tasks_filter_by_status(self, client, valid_token):
        """Test filtering tasks by status."""
        response = client.get(
            "/openclaw/tasks?status=completed",
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 200
        data = response.json()
        # All returned tasks should be completed (or empty)
        for task in data["tasks"]:
            assert task["status"] == "completed"

    def test_list_tasks_invalid_status(self, client, valid_token):
        """Test filtering with invalid status returns error."""
        response = client.get(
            "/openclaw/tasks?status=invalid_status",
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 400
        assert "invalid status" in response.json()["detail"].lower()

    # === Health Check Tests ===

    def test_openclaw_health_endpoint(self, client):
        """Test OpenClaw health endpoint."""
        response = client.get("/openclaw/health")

        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["service"] == "openclaw-webhook"
        assert "status" in data

    # === Unknown Request Type Tests ===

    def test_unknown_request_type(self, client, valid_token):
        """Test handling of unknown request type."""
        payload = {
            "taskId": "test-task-unknown",
            "type": "unknown-type",
            "payload": {
                "stepType": "log",
                "params": {},
            },
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 400
        assert "unknown" in response.json()["detail"].lower()


class TestOpenClawService:
    """Unit tests for OpenClawService class directly."""

    @pytest.fixture
    def service(self):
        """Create a fresh service instance."""
        from ironclaw.services.openclaw_service import OpenClawService
        return OpenClawService(hook_token="test-token")

    def test_validate_token_success(self, service):
        """Test token validation with correct token."""
        assert service.validate_token("Bearer test-token") is True

    def test_validate_token_wrong_token(self, service):
        """Test token validation with wrong token."""
        assert service.validate_token("Bearer wrong-token") is False

    def test_validate_token_missing_bearer(self, service):
        """Test token validation without Bearer prefix."""
        assert service.validate_token("test-token") is False

    def test_validate_token_none(self, service):
        """Test token validation with None."""
        assert service.validate_token(None) is False

    def test_validate_token_empty(self, service):
        """Test token validation with empty string."""
        assert service.validate_token("") is False

    @pytest.mark.asyncio
    async def test_handle_execute_step(self, service):
        """Test handling execute-step request."""
        from ironclaw.services.openclaw_service import (
            WebhookRequest,
            WebhookPayload,
            StepParams,
        )

        request = WebhookRequest(
            taskId="test-123",
            type="execute-step",
            payload=WebhookPayload(
                stepType="log",
                params=StepParams(message="test message"),
            ),
        )

        response = await service.handle_webhook(request, "Bearer test-token")

        assert response.ok is True
        assert response.runId is not None
        assert response.status == "queued"

    @pytest.mark.asyncio
    async def test_handle_webhook_invalid_token(self, service):
        """Test handling webhook with invalid token."""
        from ironclaw.services.openclaw_service import (
            WebhookRequest,
            WebhookPayload,
            StepParams,
        )

        request = WebhookRequest(
            taskId="test-123",
            type="execute-step",
            payload=WebhookPayload(
                stepType="log",
                params=StepParams(),
            ),
        )

        response = await service.handle_webhook(request, "Bearer wrong")

        assert response.ok is False
        assert "authorization" in response.error.lower()

    def test_get_task_status_not_found(self, service):
        """Test getting status for non-existent task."""
        assert service.get_task_status("nonexistent") is None

    def test_get_all_tasks_empty(self, service):
        """Test getting all tasks when empty."""
        tasks = service.get_all_tasks()
        assert isinstance(tasks, list)


class TestWebhookPayloadValidation:
    """Tests for webhook payload validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from ironclaw.main import app
        return TestClient(app)

    @pytest.fixture
    def valid_token(self):
        return "Bearer test-secret-token"

    def test_missing_task_id(self, client, valid_token):
        """Test payload without taskId."""
        payload = {
            "type": "execute-step",
            "payload": {
                "stepType": "log",
                "params": {},
            },
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 422  # Validation error

    def test_missing_type(self, client, valid_token):
        """Test payload without type."""
        payload = {
            "taskId": "test-task",
            "payload": {
                "stepType": "log",
                "params": {},
            },
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 422

    def test_missing_payload(self, client, valid_token):
        """Test payload without payload field."""
        payload = {
            "taskId": "test-task",
            "type": "execute-step",
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 422

    def test_minimal_valid_payload(self, client, valid_token):
        """Test minimal valid payload."""
        payload = {
            "taskId": "test-task",
            "type": "execute-step",
            "payload": {
                "stepType": "log",
            },
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 202

    def test_payload_with_extra_fields(self, client, valid_token):
        """Test that extra fields are allowed."""
        payload = {
            "taskId": "test-task",
            "type": "execute-step",
            "extraField": "should be ignored",
            "payload": {
                "stepType": "log",
                "params": {
                    "message": "test",
                    "customField": "also allowed",
                },
            },
        }

        response = client.post(
            "/openclaw/webhook",
            json=payload,
            headers={"Authorization": valid_token},
        )

        assert response.status_code == 202
