"""
Test configuration for Iron Claw Gateway.
"""
import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_settings(monkeypatch):
    """Mock settings for testing."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("VAPI_API_KEY", "test-vapi-key")
    monkeypatch.setenv("VAPI_PHONE_NUMBER_ID", "test-phone-id")
    monkeypatch.setenv("USER_PHONE_NUMBER", "+15555555555")
    monkeypatch.setenv("DEBUG", "true")
