"""
Tests for the HITL (Human-in-the-Loop) service.
"""
import pytest
import asyncio
from ironclaw.services.hitl_service import HITLService, HITLTimeoutError


@pytest.fixture
def hitl_service():
    """Create a fresh HITL service for each test."""
    return HITLService()


class TestHITLService:
    """Test suite for HITLService."""

    @pytest.mark.asyncio
    async def test_request_and_respond(self, hitl_service):
        """Test basic HITL request and response flow."""
        # Start request in background
        async def make_request():
            return await hitl_service.request_hitl(
                task_id="test-task-1",
                hitl_type="captcha",
                message="Test CAPTCHA",
                timeout_seconds=5,
            )

        # Start request
        request_task = asyncio.create_task(make_request())

        # Give it time to register
        await asyncio.sleep(0.1)

        # Get pending requests
        pending = await hitl_service.get_pending_requests()
        assert len(pending) == 1
        request_id = pending[0]["request_id"]

        # Respond
        success = await hitl_service.respond_hitl(request_id, "I solved it")
        assert success

        # Wait for request to complete
        response = await request_task
        assert response["action"] == "I solved it"

    @pytest.mark.asyncio
    async def test_request_timeout(self, hitl_service):
        """Test that requests timeout correctly."""
        with pytest.raises(HITLTimeoutError):
            await hitl_service.request_hitl(
                task_id="test-task-2",
                hitl_type="captcha",
                message="This will timeout",
                timeout_seconds=1,  # Very short timeout
            )

    @pytest.mark.asyncio
    async def test_get_pending_requests_filter(self, hitl_service):
        """Test filtering pending requests by task_id."""
        # Create multiple requests in background (they'll timeout but we check before)
        async def make_request(task_id):
            try:
                await hitl_service.request_hitl(
                    task_id=task_id,
                    hitl_type="test",
                    message="Test",
                    timeout_seconds=10,
                )
            except HITLTimeoutError:
                pass

        task1 = asyncio.create_task(make_request("task-a"))
        task2 = asyncio.create_task(make_request("task-b"))

        await asyncio.sleep(0.1)

        # Filter by task_id
        pending_a = await hitl_service.get_pending_requests("task-a")
        pending_b = await hitl_service.get_pending_requests("task-b")
        pending_all = await hitl_service.get_pending_requests()

        assert len(pending_a) == 1
        assert len(pending_b) == 1
        assert len(pending_all) == 2

        # Cancel to cleanup
        for req in pending_all:
            await hitl_service.cancel_request(req["request_id"])

    @pytest.mark.asyncio
    async def test_cancel_request(self, hitl_service):
        """Test cancelling a HITL request."""
        async def make_request():
            return await hitl_service.request_hitl(
                task_id="test-cancel",
                hitl_type="captcha",
                message="Will be cancelled",
                timeout_seconds=10,
            )

        request_task = asyncio.create_task(make_request())
        await asyncio.sleep(0.1)

        pending = await hitl_service.get_pending_requests()
        assert len(pending) == 1
        request_id = pending[0]["request_id"]

        # Cancel
        success = await hitl_service.cancel_request(request_id)
        assert success

        # Request should return with Abort action
        response = await request_task
        assert response["action"] == "Abort"

    @pytest.mark.asyncio
    async def test_callback_registration(self, hitl_service):
        """Test that callbacks are called on new requests."""
        received_requests = []

        async def callback(request):
            received_requests.append(request)

        hitl_service.register_callback(callback)

        # Make request (will timeout quickly)
        try:
            await hitl_service.request_hitl(
                task_id="callback-test",
                hitl_type="test",
                message="Testing callback",
                timeout_seconds=1,
            )
        except HITLTimeoutError:
            pass

        assert len(received_requests) == 1
        assert received_requests[0]["task_id"] == "callback-test"
