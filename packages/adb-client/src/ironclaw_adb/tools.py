"""
High-level ADB tools built on top of the connection.
"""
import logging
from typing import Optional

from .connection import ADBConnection

logger = logging.getLogger("ironclaw.adb.tools")


class ADBTools:
    """
    High-level ADB tools for common operations.
    """

    def __init__(self, connection: Optional[ADBConnection] = None):
        self.conn = connection or ADBConnection()

    async def set_alarm(
        self,
        hour: int,
        minute: int,
        label: str = "Iron Claw Reminder",
        skip_ui: bool = True,
    ) -> bool:
        """
        Set an alarm using Android Intent.
        More reliable than UI automation.
        """
        cmd = (
            f"am start -a android.intent.action.SET_ALARM "
            f"--ei android.intent.extra.alarm.HOUR {hour} "
            f"--ei android.intent.extra.alarm.MINUTES {minute} "
            f'--es android.intent.extra.alarm.MESSAGE "{label}" '
            f"--ez android.intent.extra.alarm.SKIP_UI {str(skip_ui).lower()}"
        )

        try:
            result = await self.conn.shell(cmd)
            logger.info(f"Alarm set: {hour:02d}:{minute:02d} - {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to set alarm: {e}")
            return False

    async def create_calendar_event(
        self,
        title: str,
        start_millis: int,
        end_millis: int,
        description: Optional[str] = None,
    ) -> bool:
        """Create a calendar event using Intent."""
        cmd = (
            f"am start -a android.intent.action.INSERT "
            f"-d content://com.android.calendar/events "
            f"--el beginTime {start_millis} "
            f"--el endTime {end_millis} "
            f'--es title "{title}"'
        )

        if description:
            cmd += f' --es description "{description}"'

        try:
            await self.conn.shell(cmd)
            return True
        except Exception as e:
            logger.error(f"Failed to create calendar event: {e}")
            return False

    async def open_url(self, url: str) -> bool:
        """Open a URL in the default browser."""
        cmd = f'am start -a android.intent.action.VIEW -d "{url}"'
        try:
            await self.conn.shell(cmd)
            return True
        except Exception as e:
            logger.error(f"Failed to open URL: {e}")
            return False

    async def go_home(self) -> None:
        """Navigate to home screen."""
        await self.conn.press_key(3)  # KEYCODE_HOME

    async def go_back(self) -> None:
        """Press back button."""
        await self.conn.press_key(4)  # KEYCODE_BACK

    async def is_screen_on(self) -> bool:
        """Check if device screen is on."""
        output = await self.conn.shell("dumpsys power | grep 'Display Power'")
        return "state=ON" in output

    async def wake_screen(self) -> None:
        """Wake up the device screen."""
        await self.conn.press_key(26)  # KEYCODE_POWER
