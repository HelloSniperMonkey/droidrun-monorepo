"""Configuration management for AI Job Hunter"""
import os
import subprocess
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # Execution Mode: "cloud" (MobileRun) or "local" (DroidRun)
    # In cloud mode, will fallback to local if MobileRun fails and ADB device is connected
    EXECUTION_MODE = os.getenv("EXECUTION_MODE", "cloud").lower()

    # MobileRun API Configuration (for cloud mode)
    MOBILERUN_API_KEY = os.getenv("MOBILERUN_API_KEY")
    MOBILERUN_API_URL = os.getenv("MOBILERUN_API_URL", "https://api.mobilerun.ai/v1")

    # DroidRun Configuration (for local mode)
    ADB_DEVICE_SERIAL = os.getenv("ADB_DEVICE_SERIAL", "")  # e.g., "localhost:5555" or device serial
    DROIDRUN_LLM_PROVIDER = os.getenv("DROIDRUN_LLM_PROVIDER", "google")  # google, openai, anthropic
    DROIDRUN_LLM_MODEL = os.getenv("DROIDRUN_LLM_MODEL", "gemini-2.5-pro")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")  # Required for DroidRun with Google

    # MongoDB Configuration
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
    MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "ai_job_hunter")

    # Google Sheets Configuration
    GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")

    # OpenRouter Configuration (for resume parsing - FREE model)
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")

    # Anthropic Configuration (alternative for resume parsing)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

    # Agent Configuration
    MAX_STEPS_QUOTA = int(os.getenv("MAX_STEPS_QUOTA", "100"))
    MIN_JOBS_APPLIED = int(os.getenv("MIN_JOBS_APPLIED", "10"))

    # LLM Model for MobileRun Agent
    LLM_MODEL = os.getenv("LLM_MODEL", "google/gemini-2.5-flash")

    # Agent Execution Settings
    AGENT_EXECUTION_TIMEOUT = int(os.getenv("AGENT_EXECUTION_TIMEOUT", "300"))
    AGENT_TEMPERATURE = float(os.getenv("AGENT_TEMPERATURE", "0.5"))

    # Flask Configuration
    FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5123"))

    # Default Job Portals
    DEFAULT_JOB_PORTALS = [
        "https://www.linkedin.com/jobs",
        "https://www.indeed.com",
        "https://www.glassdoor.com",
        "https://www.monster.com",
        "https://www.ziprecruiter.com",
        "https://angel.co/jobs",
        "https://wellfound.com/jobs",
    ]

    @classmethod
    def is_adb_device_connected(cls) -> bool:
        """Check if an ADB device is connected"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split("\n")
            # First line is "List of devices attached", check for actual devices
            for line in lines[1:]:
                if line.strip() and "device" in line and "offline" not in line:
                    return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return False

    @classmethod
    def get_connected_device_serial(cls) -> str:
        """Get the serial of the first connected ADB device"""
        try:
            result = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            lines = result.stdout.strip().split("\n")
            for line in lines[1:]:
                if line.strip() and "device" in line and "offline" not in line:
                    return line.split()[0]
            return ""
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return ""

    @classmethod
    def validate(cls):
        """Validate required configuration based on execution mode"""
        errors = []

        # Validate execution mode
        if cls.EXECUTION_MODE not in ("cloud", "local"):
            errors.append(f"EXECUTION_MODE must be 'cloud' or 'local', got '{cls.EXECUTION_MODE}'")

        # Mode-specific validation
        if cls.EXECUTION_MODE == "cloud":
            if not cls.MOBILERUN_API_KEY:
                errors.append("MOBILERUN_API_KEY is required for cloud mode")
        elif cls.EXECUTION_MODE == "local":
            if not cls.ADB_DEVICE_SERIAL and not cls.is_adb_device_connected():
                errors.append("ADB_DEVICE_SERIAL or a connected ADB device is required for local mode")
            if cls.DROIDRUN_LLM_PROVIDER == "google" and not cls.GEMINI_API_KEY:
                errors.append("GEMINI_API_KEY is required for DroidRun with Google provider")

        # Common requirements
        if not cls.MONGODB_URI:
            errors.append("MONGODB_URI is required")

        if not cls.GOOGLE_SHEETS_SPREADSHEET_ID:
            errors.append("GOOGLE_SHEETS_SPREADSHEET_ID is required")

        if not cls.OPENROUTER_API_KEY and not cls.ANTHROPIC_API_KEY:
            errors.append("Either OPENROUTER_API_KEY or ANTHROPIC_API_KEY is required for resume parsing")

        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")

        return True

    @classmethod
    def should_fallback_to_local(cls) -> bool:
        """Check if we should fallback to local DroidRun (only in cloud mode with connected device)"""
        return cls.EXECUTION_MODE == "cloud" and cls.is_adb_device_connected()
