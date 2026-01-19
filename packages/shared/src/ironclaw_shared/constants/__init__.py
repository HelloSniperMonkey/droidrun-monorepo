"""
Shared constants for Iron Claw.
"""

# Android Key Codes
KEYCODE_HOME = 3
KEYCODE_BACK = 4
KEYCODE_ENTER = 66
KEYCODE_DEL = 67

# Default safe packages that the agent can access
DEFAULT_SAFE_PACKAGES = [
    "com.android.chrome",
    "com.google.android.calendar",
    "com.google.android.deskclock",
    "com.google.android.apps.nexuslauncher",
    "com.google.android.gm",
    "com.android.documentsui",
]

# API endpoints
VAPI_API_URL = "https://api.vapi.ai"

# Timeouts (in seconds)
DEFAULT_ADB_TIMEOUT = 30
DEFAULT_AGENT_TIMEOUT = 300
DEFAULT_HTTP_TIMEOUT = 30

# Limits
MAX_APPLICATIONS_PER_SESSION = 10
MAX_SCREENSHOT_SIZE_MB = 5
MAX_RESUME_SIZE_MB = 10

# HITL settings
HITL_DEFAULT_TIMEOUT_SECONDS = 300  # 5 minutes to respond
HITL_MAX_RETRIES = 3
