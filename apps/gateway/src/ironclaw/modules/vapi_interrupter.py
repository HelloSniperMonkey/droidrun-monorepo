"""
Vapi Interrupter Module - Voice AI wake-up calls.
Uses Vapi REST API directly for server-side outbound calls.
"""
import logging
import random
import uuid
from datetime import datetime
from typing import Optional

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..agents.adb_connection import ADBConnection
from ..utils.config import get_app_config, get_settings

logger = logging.getLogger("ironclaw.modules.vapi_interrupter")

# Vapi API base URL
VAPI_API_URL = "https://api.vapi.ai"

# Global scheduler instance
_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
    return _scheduler


class VapiInterrupterService:
    """
    Service for voice-based wake-up calls using Vapi REST API.

    Features:
    - Immediate wake-up calls
    - Scheduled calls with timezone awareness
    - Cognitive verification (math questions, etc.)
    """

    def __init__(self):
        self.settings = get_settings()
        self.config = get_app_config().vapi_config
        self.adb = ADBConnection()

    def _get_headers(self) -> dict:
        """Get authorization headers for Vapi API."""
        if not self.settings.vapi_api_key:
            raise ValueError("VAPI_API_KEY not configured")
        return {
            "Authorization": f"Bearer {self.settings.vapi_api_key}",
            "Content-Type": "application/json",
        }

    def _build_wake_assistant_config(
        self,
        custom_message: Optional[str] = None,
        verification_question: Optional[str] = None,
    ) -> dict:
        """Build the Vapi assistant configuration for wake-up calls."""

        # Default verification question
        if verification_question is None:
            a, b = random.randint(3, 9), random.randint(3, 9)
            verification_question = f"What is {a} times {b}?"

        first_message = custom_message or (
            "WAKE UP! This is Iron Claw. "
            "I need to verify you're fully conscious. "
            f"{verification_question}"
        )

        system_prompt = f"""
You are Iron Claw, a ruthless but caring productivity assistant.
Your mission is to ensure the user is FULLY AWAKE.

Current time verification question: {verification_question}

Rules:
1. Be energetic and motivating, but firm
2. Do NOT accept "I'm awake" or "I'm up" as proof - they could be half-asleep
3. Ask them to answer the verification question
4. If they get it wrong, encourage them to try again
5. If they answer correctly, congratulate them and wish them a productive day
6. If they seem confused or groggy, ask them to splash water on their face and try again
7. Do not end the call until they prove they're cognitively alert

Remember: You're helping them achieve their goals. Being firm is being kind.
"""

        return {
            "transcriber": {
                "provider": self.config.get("transcriber_provider", "deepgram"),
                "model": self.config.get("transcriber_model", "nova-2"),
                "language": "en",
            },
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_prompt}
                ],
                "temperature": 0.7,
            },
            "voice": {
                "provider": self.config.get("voice_provider", "11labs"),
                "voiceId": self.config.get("voice_id", "rachel"),
            },
            "firstMessage": first_message,
            "maxDurationSeconds": self.config.get("max_call_duration", 300),
        }

    async def trigger_wake_call(
        self,
        phone_number: str,
        custom_message: Optional[str] = None,
        verification_question: Optional[str] = None,
    ) -> str:
        """
        Immediately trigger a wake-up call using Vapi REST API.

        Args:
            phone_number: User's phone number (E.164 format)
            custom_message: Optional custom first message
            verification_question: Optional custom verification question

        Returns:
            Call ID from Vapi
        """
        logger.info(f"🔔 Triggering wake-up call to {phone_number}")

        assistant_config = self._build_wake_assistant_config(
            custom_message=custom_message,
            verification_question=verification_question,
        )

        # Build the API request payload
        payload = {
            "phoneNumberId": self.settings.vapi_phone_number_id,
            "customer": {
                "number": phone_number,
                "name": "Iron Claw User",
            },
            "assistant": assistant_config,
            "name": f"Wake-up Call {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{VAPI_API_URL}/call",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            call_id = data.get("id", "unknown")
            logger.info(f"✅ Wake-up call initiated: {call_id}")
            return call_id

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Vapi API error: {e.response.status_code} - {e.response.text}")
            raise RuntimeError(f"Vapi API error: {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Failed to trigger wake-up call: {e}")
            raise

    async def schedule_wake_call(
        self,
        hour: int,
        minute: int,
        phone_number: str,
        use_device_location: bool = True,
    ) -> str:
        """
        Schedule a wake-up call for a specific time.

        Args:
            hour: Hour (0-23) in local timezone
            minute: Minute (0-59)
            phone_number: User's phone number
            use_device_location: If True, determine timezone from device GPS

        Returns:
            Job ID for the scheduled task
        """
        # Determine timezone
        if use_device_location:
            location = await self.get_device_location()
            timezone = location.get("timezone", "UTC")
        else:
            timezone = "UTC"

        logger.info(f"📅 Scheduling wake-up call for {hour:02d}:{minute:02d} ({timezone})")

        scheduler = get_scheduler()

        # Create unique job ID
        job_id = f"wake-{uuid.uuid4().hex[:8]}"

        # Schedule the job
        scheduler.add_job(
            self._execute_scheduled_call,
            CronTrigger(hour=hour, minute=minute, timezone=timezone),
            args=[phone_number],
            id=job_id,
            name=f"Wake Call {hour:02d}:{minute:02d}",
            replace_existing=True,
        )

        logger.info(f"✅ Wake-up call scheduled: {job_id}")
        return job_id

    async def _execute_scheduled_call(self, phone_number: str):
        """Execute a scheduled wake-up call."""
        logger.info(f"⏰ Executing scheduled wake-up call to {phone_number}")
        try:
            await self.trigger_wake_call(phone_number)
        except Exception as e:
            logger.error(f"Scheduled wake-up call failed: {e}")

    async def cancel_scheduled_call(self, job_id: str) -> bool:
        """Cancel a scheduled wake-up call."""
        scheduler = get_scheduler()
        try:
            scheduler.remove_job(job_id)
            logger.info(f"Cancelled scheduled call: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    async def get_device_location(self) -> dict:
        """
        Get the device's current location and timezone.

        Returns dict with:
        - latitude
        - longitude
        - timezone (IANA timezone string)
        """
        result = await self.adb.get_location()
        return result or {"latitude": None, "longitude": None, "timezone": "UTC"}

    async def list_calls(self, limit: int = 10) -> list:
        """List recent calls from Vapi."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{VAPI_API_URL}/call",
                    headers=self._get_headers(),
                    params={"limit": limit},
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to list calls: {e}")
            return []
