"""
Temporal Guardian Module - Alarm scheduling and calendar management.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional
from datetime import datetime, timedelta

from ..agents.adb_connection import ADBConnection
from ..utils.config import get_app_config
from .schedule_extractor import ScheduleEvent

logger = logging.getLogger("ironclaw.modules.temporal_guardian")


class TemporalGuardianService:
    """
    Service for time-based automation.

    Uses Android Intents for reliable alarm scheduling
    rather than UI automation (more precise).
    """

    def __init__(self):
        self.adb = ADBConnection()
        self.config = get_app_config().alarm_config

    async def set_alarm(
        self,
        hour: int,
        minute: int,
        label: Optional[str] = None,
    ) -> bool:
        """
        Set an alarm using Android Intent.

        This is more reliable than UI automation because:
        - No visual parsing needed
        - Works even if clock app changes
        - Precise timing

        Args:
            hour: Hour (0-23)
            minute: Minute (0-59)
            label: Optional alarm label

        Returns:
            True if alarm was set successfully
        """
        label = label or self.config.get("default_label", "Iron Claw Reminder")
        skip_ui = self.config.get("skip_ui", True)

        # Build the intent command
        cmd = (
            f"am start -a android.intent.action.SET_ALARM "
            f"--ei android.intent.extra.alarm.HOUR {hour} "
            f"--ei android.intent.extra.alarm.MINUTES {minute} "
            f'--es android.intent.extra.alarm.MESSAGE "{label}" '
            f"--ez android.intent.extra.alarm.SKIP_UI {str(skip_ui).lower()}"
        )

        logger.info(f"Setting alarm for {hour:02d}:{minute:02d} - {label}")

        try:
            result = await self.adb.shell(cmd)
            logger.info(f"Alarm set result: {result}")

            # Give the alarm app time to process
            await asyncio.sleep(1)

            # Navigate home to clean up
            await self.adb.press_key(3)  # KEYCODE_HOME

            return True
        except Exception as e:
            logger.error(f"Failed to set alarm: {e}")
            return False

    async def open_clock_app(self):
        """Open the native clock app for manual alarm management."""
        await self.adb.start_app("com.google.android.deskclock")

    async def create_calendar_event(
        self,
        title: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
    ) -> bool:
        """
        Create a calendar event using Intent.

        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time (defaults to 1 hour after start)
            description: Optional event description

        Returns:
            True if event was created
        """
        # Convert to epoch milliseconds
        start_millis = int(start_time.timestamp() * 1000)

        if end_time:
            end_millis = int(end_time.timestamp() * 1000)
        else:
            # Default 1 hour duration
            end_millis = start_millis + (60 * 60 * 1000)

        # Build calendar intent
        cmd = (
            f"am start -a android.intent.action.INSERT "
            f"-d content://com.android.calendar/events "
            f"--el beginTime {start_millis} "
            f"--el endTime {end_millis} "
            f'--es title "{title}"'
        )

        if description:
            cmd += f' --es description "{description}"'

        logger.info(f"Creating calendar event: {title} at {start_time}")

        try:
            result = await self.adb.shell(cmd)
            logger.info(f"Calendar event result: {result}")

            await asyncio.sleep(2)

            # The intent opens the event creation UI
            # For full automation, we'd use the agent to tap "Save"
            # For MVP, leave it for user confirmation

            return True
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return False

    async def get_device_time(self) -> str:
        """Get current time from the Android device."""
        return await self.adb.get_device_time()

    async def cancel_next_alarm(self) -> bool:
        """
        Cancel the next scheduled alarm.

        Note: Android doesn't have a direct intent for this.
        Opens the clock app for manual cancellation.
        """
        await self.open_clock_app()
        return True

    def _get_next_weekday(self, day_name: str) -> datetime:
        """Get the date of the next occurrence of the given day name."""
        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        try:
            target_day_index = days.index(day_name.lower())
        except ValueError:
            logger.warning(f"Invalid day name: {day_name}, defaulting to tomorrow")
            return datetime.now() + timedelta(days=1)

        today = datetime.now()
        current_day_index = today.weekday()

        days_ahead = target_day_index - current_day_index
        if days_ahead <= 0:  # Target day already happened this week or is today
            days_ahead += 7

        return today + timedelta(days=days_ahead)

    async def create_events_from_schedule(self, events: List[ScheduleEvent]) -> int:
        """
        Create calendar events from extracted schedule.
        Returns number of events created.
        """
        count = 0
        for event in events:
            try:
                # Calculate date
                base_date = self._get_next_weekday(event.day_of_week)

                # Parse times
                start_h, start_m = map(int, event.start_time.split(":"))
                end_h, end_m = map(int, event.end_time.split(":"))

                start_dt = base_date.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
                end_dt = base_date.replace(hour=end_h, minute=end_m, second=0, microsecond=0)

                description = (
                    f"Type: {event.type}\nLocation: {event.location}"
                    if event.location
                    else event.type
                )

                success = await self.create_calendar_event(
                    title=event.course_name,
                    start_time=start_dt,
                    end_time=end_dt,
                    description=description,
                )

                if success:
                    count += 1

                # Small delay between intents to avoid flooding
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Failed to schedule event {event.course_name}: {e}")

        return count
