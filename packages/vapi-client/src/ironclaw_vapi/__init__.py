"""
Iron Claw Vapi Client Package.
Voice AI integration for wake-up calls and notifications.
"""
from .assistant import WakeUpAssistant
from .client import VapiClient

__version__ = "0.1.0"
__all__ = ["VapiClient", "WakeUpAssistant"]
