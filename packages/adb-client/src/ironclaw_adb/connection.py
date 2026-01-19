"""
ADB Connection management.
"""
import asyncio
import logging
import re
import subprocess
from typing import Optional

logger = logging.getLogger("ironclaw.adb.connection")


class ADBConnection:
    """
    Manages ADB connection to Android device.
    Supports both TCP/IP (Mobilerun) and USB connections.

    This is a singleton - one connection per application.
    """

    _instance: Optional["ADBConnection"] = None
    _serial: Optional[str] = None
    _use_tcp: bool = True

    def __new__(cls, serial: Optional[str] = None, use_tcp: bool = True):
        """Singleton pattern - one connection per application."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._serial = serial
            cls._use_tcp = use_tcp
        return cls._instance

    @classmethod
    def configure(cls, serial: Optional[str] = None, use_tcp: bool = True):
        """Configure the singleton instance."""
        cls._serial = serial
        cls._use_tcp = use_tcp

    @property
    def serial(self) -> Optional[str]:
        return self._serial

    @property
    def use_tcp(self) -> bool:
        return self._use_tcp

    async def _run_adb(self, *args: str, timeout: int = 30) -> str:
        """Run an ADB command and return output."""
        cmd = ["adb"]
        if self._serial:
            cmd.extend(["-s", self._serial])
        cmd.extend(args)

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0 and result.stderr:
                logger.warning(f"ADB stderr: {result.stderr}")
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error(f"ADB command timed out: {' '.join(cmd)}")
            raise TimeoutError(f"ADB command timed out after {timeout}s")

    async def ping(self) -> dict:
        """Test connection to the device."""
        try:
            logger.info(f"Chudne ghus gya ")
            result = await self._run_adb("shell", "echo", "ping")
            logger.info(f"ADB ping result: {result}")
            connected = "ping" in result
            logger.info(f"ADB ping connected: {connected}")
            return {"status": "connected" if connected else "disconnected", "result": result}
        except Exception as e:
            logger.error(f"Device ping failed: {e}")
            return {"status": "error", "error": str(e)}

    async def shell(self, command: str, timeout: int = 30) -> str:
        """Execute a shell command on the device."""
        return await self._run_adb("shell", command, timeout=timeout)

    async def take_screenshot(self) -> tuple[str, bytes]:
        """
        Capture a screenshot from the device.
        Returns (format, bytes).
        """
        # Capture to device
        await self._run_adb("shell", "screencap", "-p", "/sdcard/screen.png")

        # Pull to local temp
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name

        try:
            await self._run_adb("pull", "/sdcard/screen.png", temp_path)
            with open(temp_path, "rb") as f:
                data = f.read()
            return ("png", data)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            # Clean up device
            await self._run_adb("shell", "rm", "/sdcard/screen.png")

    async def get_current_package(self) -> str:
        """Get the currently focused app package."""
        output = await self.shell("dumpsys activity activities | grep mResumedActivity")
        # Parse: mResumedActivity: ActivityRecord{... com.package/.Activity ...}
        match = re.search(r"([a-zA-Z0-9_.]+)/[a-zA-Z0-9_.]+", output)
        return match.group(1) if match else ""

    async def press_key(self, keycode: int) -> str:
        """Press a key by keycode."""
        return await self.shell(f"input keyevent {keycode}")

    async def tap(self, x: int, y: int) -> str:
        """Tap at coordinates."""
        return await self.shell(f"input tap {x} {y}")

    async def input_text(self, text: str) -> str:
        """Input text on the device."""
        # Escape special characters for shell
        escaped = text.replace("'", "'\\''")
        return await self.shell(f"input text '{escaped}'")

    async def start_app(self, package: str) -> str:
        """Start an app by package name."""
        return await self.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")

    async def push_file(self, local_path: str, remote_path: str) -> bool:
        """Push a file to the device."""
        try:
            await self._run_adb("push", local_path, remote_path, timeout=60)
            return True
        except Exception as e:
            logger.error(f"Failed to push file: {e}")
            return False

    async def pull_file(self, remote_path: str, local_path: str) -> bool:
        """Pull a file from the device."""
        try:
            await self._run_adb("pull", remote_path, local_path, timeout=60)
            return True
        except Exception as e:
            logger.error(f"Failed to pull file: {e}")
            return False

    async def get_location(self) -> dict:
        """
        Get device GPS location.
        Returns dict with lat, lon, and timezone.
        """
        try:
            output = await self.shell("dumpsys location")

            # Parse GPS coordinates
            lat_match = re.search(r"Location\[.*?(\d+\.\d+),(-?\d+\.\d+)", output)
            if lat_match:
                lat = float(lat_match.group(1))
                lon = float(lat_match.group(2))

                # Get timezone from coordinates (requires timezonefinder)
                try:
                    from timezonefinder import TimezoneFinder
                    tf = TimezoneFinder()
                    timezone = tf.timezone_at(lat=lat, lng=lon) or "UTC"
                except ImportError:
                    timezone = "UTC"

                return {"latitude": lat, "longitude": lon, "timezone": timezone}

            # Fallback: get timezone from device settings
            tz_output = await self.shell("getprop persist.sys.timezone")
            return {"latitude": None, "longitude": None, "timezone": tz_output or "UTC"}

        except Exception as e:
            logger.error(f"Failed to get location: {e}")
            return {"latitude": None, "longitude": None, "timezone": "UTC"}

    async def get_device_time(self) -> str:
        """Get current time from device."""
        return await self.shell("date '+%Y-%m-%d %H:%M:%S %Z'")


# Module-level convenience function
def get_adb_connection(serial: Optional[str] = None, use_tcp: bool = True) -> ADBConnection:
    """Get the singleton ADB connection."""
    return ADBConnection(serial=serial, use_tcp=use_tcp)
