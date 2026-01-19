"""
ADB Connection Module for Iron Claw.
Provides utilities for connecting to Android devices via ADB.
"""
import logging
import re
from typing import Optional

from droidrun.tools.android.adb import AdbTools

from ..utils.config import get_settings

logger = logging.getLogger("ironclaw.agents.adb")


class ADBConnection:
    """
    Manages ADB connection to Android device.
    Supports both TCP/IP (Mobilerun) and USB connections.
    """

    _instance: Optional["ADBConnection"] = None
    _tools: Optional[AdbTools] = None

    def __new__(cls):
        """Singleton pattern - one connection per application."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def get_tools(self) -> AdbTools:
        """Get or create AdbTools instance."""
        if self._tools is None:
            settings = get_settings()

            logger.info(f"Initializing ADB connection: {settings.device_serial or 'auto-detect'}")

            self._tools = AdbTools(
                serial=settings.device_serial,
                use_tcp=settings.use_tcp,
            )

        return self._tools

    async def ping(self) -> dict:
        """Test connection to the device."""
        try:
            tools = await self.get_tools()
            await tools.connect()
            logger.info(f"ADB tools: {tools}")
            result = await tools.ping()
            logger.info(f"Device ping result: {result}")
            return {"status": "connected", "result": result}
        except Exception as e:
            logger.error(f"Device ping failed: {e}")
            return {"status": "error", "error": str(e)}

    async def take_screenshot(self) -> tuple[str, bytes]:
        """Capture a screenshot from the device."""
        tools = await self.get_tools()
        format_type, data = await tools.take_screenshot()
        return format_type, data

    async def get_current_package(self) -> str:
        """Get the currently focused app package."""
        tools = await self.get_tools()
        state = await tools.get_state()
        # State can be tuple or dict depending on droidrun version
        if isinstance(state, dict):
            activity = state.get("phone_state", {}).get("current_activity", "")
        elif isinstance(state, tuple) and len(state) >= 4:
            # Tuple format: (format, screenshot, tree, phone_state)
            phone_state = state[3] if isinstance(state[3], dict) else {}
            activity = phone_state.get("current_activity", "")
        else:
            activity = ""
        # Extract package from activity (format: package/activity)
        if "/" in activity:
            return activity.split("/")[0]
        return activity

    async def shell(self, command: str) -> str:
        """Execute a shell command on the device."""
        # Use adb directly for shell commands
        import subprocess
        settings = get_settings()

        adb_cmd = ["adb"]
        if settings.device_serial:
            adb_cmd.extend(["-s", settings.device_serial])
        adb_cmd.extend(["shell", command])

        logger.info(f"Executing ADB shell: {' '.join(adb_cmd)}")
        result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=30)
        logger.info(f"ADB shell stdout: {result.stdout.strip()}")
        if result.stderr:
            logger.warning(f"ADB shell stderr: {result.stderr.strip()}")
        return result.stdout.strip()

    async def start_app(self, package: str) -> str:
        """Start an app by package name."""
        tools = await self.get_tools()
        return await tools.start_app(package)

    async def input_text(self, text: str) -> str:
        """Input text on the device."""
        tools = await self.get_tools()
        return await tools.input_text(text)

    async def tap(self, x: int, y: int) -> str:
        """Tap at coordinates."""
        return await self.shell(f"input tap {x} {y}")

    async def press_key(self, keycode: int) -> str:
        """Press a key by keycode."""
        tools = await self.get_tools()
        return await tools.press_key(keycode)

    async def push_file(self, local_path: str, remote_path: str) -> bool:
        """Push a file to the device."""
        import subprocess
        settings = get_settings()

        adb_cmd = ["adb"]
        if settings.device_serial:
            adb_cmd.extend(["-s", settings.device_serial])
        adb_cmd.extend(["push", local_path, remote_path])

        try:
            logger.info(f"Executing ADB push: {' '.join(adb_cmd)}")
            result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=60)
            logger.info(f"ADB push stdout: {result.stdout.strip()}")
            if result.stderr:
                logger.warning(f"ADB push stderr: {result.stderr.strip()}")
            logger.info(f"ADB push return code: {result.returncode}")
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to push file: {e}")
            return False

    async def get_location(self) -> Optional[dict]:
        """
        Get device GPS location.
        Returns dict with lat, lon, and timezone.
        """
        try:
            # Get location from dumpsys
            output = await self.shell("dumpsys location")

            # Parse GPS coordinates - look for "last location=" or similar patterns
            lat_match = re.search(r"Location\[.*?(\d+\.\d+),(-?\d+\.\d+)", output)
            if lat_match:
                lat = float(lat_match.group(1))
                lon = float(lat_match.group(2))

                # Get timezone from coordinates
                from timezonefinder import TimezoneFinder
                tf = TimezoneFinder()
                timezone = tf.timezone_at(lat=lat, lng=lon)

                return {
                    "latitude": lat,
                    "longitude": lon,
                    "timezone": timezone or "UTC",
                }

            # Fallback: get timezone from device settings
            tz_output = await self.shell("getprop persist.sys.timezone")
            return {
                "latitude": None,
                "longitude": None,
                "timezone": tz_output or "UTC",
            }

        except Exception as e:
            logger.error(f"Failed to get location: {e}")
            return {"latitude": None, "longitude": None, "timezone": "UTC"}

    async def get_device_time(self) -> str:
        """Get current time from device."""
        return await self.shell("date '+%Y-%m-%d %H:%M:%S %Z'")


# Module-level convenience function
async def get_adb_connection() -> ADBConnection:
    """Get the singleton ADB connection."""
    return ADBConnection()
