"""
Configuration management for Iron Claw.
Loads settings from environment variables and config files.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings


# Find the monorepo root (has pyproject.toml with [tool.uv.workspace])
def find_monorepo_root() -> Path:
    """Find the monorepo root directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "apps").exists():
            return parent
    return Path.cwd()


MONOREPO_ROOT = find_monorepo_root()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM
    gemini_api_key: str = Field(default="", description="Google Gemini API key")
    google_api_key: str = Field(default="", description="Google API key (alias for Gemini)")
    openai_api_key: str = Field(default="", description="OpenAI API key for Whisper transcription")

    # Vapi
    vapi_api_key: str = Field(default="", description="Vapi API key")
    vapi_phone_number_id: str = Field(default="", description="Vapi phone number ID")

    # Telegram (optional for MVP)
    telegram_bot_token: Optional[str] = Field(default=None, description="Telegram bot token")

    # Device
    device_serial: Optional[str] = Field(default=None, description="ADB device serial or IP:PORT")
    use_tcp: bool = Field(default=True, description="Use TCP for ADB connection")

    # User
    user_phone_number: str = Field(default="", description="User's phone number for wake-up calls")

    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    debug: bool = Field(default=False)

    class Config:
        # Load from monorepo root .env file
        env_file = str(MONOREPO_ROOT / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


class AppConfig:
    """Application configuration from YAML file."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            # Default to config.yaml in gateway directory (apps/gateway/config.yaml)
            # path: .../apps/gateway/src/ironclaw/utils/config.py
            # -> utils -> ironclaw -> src -> gateway
            config_path = Path(__file__).parent.parent.parent.parent / "config.yaml"

        self._config = {}
        if config_path.exists():
            with open(config_path) as f:
                self._config = yaml.safe_load(f) or {}

    @property
    def safe_packages(self) -> list[str]:
        """List of packages the agent is allowed to access."""
        return self._config.get("safe_packages", [])

    @property
    def agent_config(self) -> dict:
        """Agent configuration settings."""
        return self._config.get("agent", {})

    @property
    def alarm_config(self) -> dict:
        """Alarm configuration settings."""
        return self._config.get("alarm", {})

    @property
    def vapi_config(self) -> dict:
        """Vapi voice configuration."""
        return self._config.get("vapi", {})

    @property
    def job_hunter_config(self) -> dict:
        """Job hunter module configuration."""
        return self._config.get("job_hunter", {})

    @property
    def tab_manager_config(self) -> dict:
        """Tab manager module configuration."""
        return self._config.get("tab_manager", {})


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache
def get_app_config() -> AppConfig:
    """Get cached app config instance."""
    return AppConfig()
