"""
Unit tests for Iron Claw Webhook Skill.

Run with: pytest test_ironclaw_skill.py -v
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from ironclaw_skill import (
    IronClawSkill,
    SkillConfig,
    IronClawError,
    AuthenticationError,
    TaskNotFoundError,
    run_step,
    query_status,
    cancel_task,
)


class TestSkillConfig:
    """Tests for SkillConfig."""
    
    def test_config_creation(self):
        """Test creating config directly."""
        config = SkillConfig(
            base_url="https://example.com",
            token="test-token"
        )
        assert config.base_url == "https://example.com"
        assert config.token == "test-token"
        assert config.timeout == 30.0
    
    def test_config_from_env(self, monkeypatch):
        """Test creating config from environment."""
        monkeypatch.setenv("IRONCLAW_WEBHOOK_URL", "https://tunnel.example.com")
        monkeypatch.setenv("OPENCLAW_HOOK_TOKEN", "env-token")
        
        config = SkillConfig.from_env()
        
        assert config.base_url == "https://tunnel.example.com"
        assert config.token == "env-token"
    
    def test_config_from_env_missing_token(self, monkeypatch):
        """Test that missing token raises error."""
        monkeypatch.delenv("OPENCLAW_HOOK_TOKEN", raising=False)
        
        with pytest.raises(ValueError, match="OPENCLAW_HOOK_TOKEN"):
            SkillConfig.from_env()


class TestIronClawSkill:
    """Tests for IronClawSkill."""
    
    @pytest.fixture
    def skill(self):
        """Create a skill instance for testing."""
        return IronClawSkill(
            base_url="https://test.trycloudflare.com",
            token="test-token"
        )
    
    @pytest.fixture
    def mock_response_ok(self):
        """Create a mock successful response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 202
        response.json.return_value = {
            "ok": True,
            "runId": "test-run-123",
            "status": "queued",
            "message": "Task queued for execution",
        }
        return response
    
    @pytest.fixture
    def mock_response_auth_error(self):
        """Create a mock 403 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 403
        response.text = "Invalid token"
        return response
    
    @pytest.fixture
    def mock_response_not_found(self):
        """Create a mock 404 response."""
        response = MagicMock(spec=httpx.Response)
        response.status_code = 404
        response.text = "Task not found"
        return response
    
    def test_webhook_url(self, skill):
        """Test webhook URL construction."""
        assert skill.webhook_url == "https://test.trycloudflare.com/openclaw/webhook"
    
    def test_headers(self, skill):
        """Test headers include auth token."""
        headers = skill.headers
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Content-Type"] == "application/json"
    
    @pytest.mark.asyncio
    async def test_run_step_success(self, skill, mock_response_ok):
        """Test successful run_step action."""
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response_ok
            mock_get_client.return_value = mock_client
            
            result = await skill.run_step(
                task_id="task-001",
                step_type="log",
                params={"message": "test"}
            )
            
            assert result["ok"] is True
            assert result["runId"] == "test-run-123"
            assert result["status"] == "queued"
            
            # Verify correct payload was sent
            call_args = mock_client.post.call_args
            payload = call_args.kwargs["json"]
            assert payload["taskId"] == "task-001"
            assert payload["type"] == "execute-step"
            assert payload["payload"]["stepType"] == "log"
    
    @pytest.mark.asyncio
    async def test_run_step_auth_error(self, skill, mock_response_auth_error):
        """Test run_step with invalid token."""
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response_auth_error
            mock_get_client.return_value = mock_client
            
            with pytest.raises(AuthenticationError):
                await skill.run_step("task-001", "log")
    
    @pytest.mark.asyncio
    async def test_query_status_success(self, skill, mock_response_ok):
        """Test successful query_status action."""
        mock_response_ok.json.return_value = {
            "ok": True,
            "runId": "test-run-123",
            "status": "completed",
        }
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response_ok
            mock_get_client.return_value = mock_client
            
            result = await skill.query_status("test-run-123")
            
            assert result["ok"] is True
            assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_query_status_not_found(self, skill, mock_response_not_found):
        """Test query_status for non-existent task."""
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response_not_found
            mock_get_client.return_value = mock_client
            
            with pytest.raises(TaskNotFoundError):
                await skill.query_status("nonexistent")
    
    @pytest.mark.asyncio
    async def test_cancel_task_success(self, skill):
        """Test successful cancel_task action."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "runId": "test-run-123",
            "status": "cancelled",
            "message": "Task cancelled",
        }
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.delete.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await skill.cancel_task("test-run-123")
            
            assert result["ok"] is True
            assert result["status"] == "cancelled"
    
    @pytest.mark.asyncio
    async def test_list_tasks(self, skill):
        """Test list_tasks method."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "tasks": [
                {"run_id": "run-1", "status": "completed"},
                {"run_id": "run-2", "status": "running"},
            ],
            "total": 2,
        }
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await skill.list_tasks(limit=10)
            
            assert result["ok"] is True
            assert len(result["tasks"]) == 2
    
    @pytest.mark.asyncio
    async def test_health_check(self, skill):
        """Test health_check method."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "ok": True,
            "service": "openclaw-webhook",
            "status": "ready",
        }
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            result = await skill.health_check()
            
            assert result["ok"] is True
            assert result["service"] == "openclaw-webhook"
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test skill as async context manager."""
        async with IronClawSkill(
            base_url="https://test.com",
            token="test"
        ) as skill:
            assert skill is not None


class TestEntryPoints:
    """Tests for OpenClaw action entry points."""
    
    @pytest.mark.asyncio
    async def test_run_step_entry_point(self, monkeypatch):
        """Test run_step entry point function."""
        monkeypatch.setenv("IRONCLAW_WEBHOOK_URL", "https://test.com")
        monkeypatch.setenv("OPENCLAW_HOOK_TOKEN", "test-token")
        
        with patch('ironclaw_skill.IronClawSkill.run_step') as mock_run:
            mock_run.return_value = {"ok": True, "runId": "test-123"}
            
            # The entry point creates a new skill, so we need to patch differently
            with patch('ironclaw_skill.IronClawSkill') as MockSkill:
                mock_instance = AsyncMock()
                mock_instance.run_step.return_value = {"ok": True, "runId": "test-123"}
                mock_instance.__aenter__.return_value = mock_instance
                mock_instance.__aexit__.return_value = None
                MockSkill.return_value = mock_instance
                
                result = await run_step("task-1", "log", {"message": "hi"})
                
                assert result["ok"] is True


class TestPayloadFormats:
    """Tests for various payload formats."""
    
    @pytest.fixture
    def skill(self):
        return IronClawSkill(
            base_url="https://test.com",
            token="test"
        )
    
    @pytest.mark.asyncio
    async def test_log_step_payload(self, skill):
        """Test log step payload format."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 202
        mock_response.json.return_value = {"ok": True, "runId": "123"}
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            await skill.run_step("task-1", "log", {"message": "test log"})
            
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["payload"]["stepType"] == "log"
            assert payload["payload"]["params"]["message"] == "test log"
    
    @pytest.mark.asyncio
    async def test_http_action_payload(self, skill):
        """Test http_action step payload format."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 202
        mock_response.json.return_value = {"ok": True, "runId": "123"}
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            await skill.run_step("task-1", "http_action", {
                "url": "https://api.example.com",
                "method": "POST",
                "body": {"key": "value"}
            })
            
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["payload"]["stepType"] == "http_action"
            assert payload["payload"]["params"]["url"] == "https://api.example.com"
    
    @pytest.mark.asyncio
    async def test_mobile_action_payload(self, skill):
        """Test mobile_action step payload format."""
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 202
        mock_response.json.return_value = {"ok": True, "runId": "123"}
        
        with patch.object(skill, '_get_client') as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client
            
            await skill.run_step("task-1", "mobile_action", {
                "action": "click",
                "selector": "button[id='submit']"
            })
            
            payload = mock_client.post.call_args.kwargs["json"]
            assert payload["payload"]["stepType"] == "mobile_action"
            assert payload["payload"]["params"]["action"] == "click"
