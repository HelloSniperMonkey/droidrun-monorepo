# gateway/main.py

import time
import json
import logging
import asyncio
import re
from droidrun import DroidAgent, DroidrunConfig, DeviceConfig

# Configure logging
logging.basicConfig(level=logging.INFO)

# --- Configuration ---
DUOLINGO_PACKAGE_NAME = "com.duolingo"
STATE_FILE = "gateway/daily_bonus_state.json"
CHECK_INTERVAL_SECONDS = 10
DAILY_BONUS_COOLDOWN_SECONDS = 24 * 60 * 60

# --- State Management ---


def read_state():
    """Reads the last login timestamp from the state file."""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_login": 0}


def write_state(state):
    """Writes the current login timestamp to the state file."""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


# --- Duolingo Actions ---


async def claim_daily_bonus():
    """
    Uses the DroidAgent to navigate to the Duolingo shop and claim the daily bonus.
    """
    logging.info("Initializing DroidAgent to claim daily bonus...")
    try:
        config = DroidrunConfig(device=DeviceConfig(platform="android"))
        agent = DroidAgent(
            goal="Open the Duolingo app, navigate to the shop, and claim the daily bonus or reward.",
            config=config,
        )
        result = await agent.run()
        logging.info(f"Agent finished with result: {result.reason}")
        return result.success
    except Exception as e:
        logging.error(f"An error occurred while running the DroidAgent: {e}")
        return False


async def get_current_focused_app():
    """
    Checks the currently focused app using adb.
    """
    try:
        cmd = "adb shell dumpsys window windows | grep -E 'mCurrentFocus'"
        proc = await asyncio.create_subprocess_shell(
            cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode == 0 and stdout:
            output = stdout.decode()
            match = re.search(r"com.[a-zA-Z0-9_.]+", output)
            if match:
                return match.group(0)
    except FileNotFoundError:
        logging.error("`adb` command not found. Make sure it's in your system's PATH.")
    except Exception as e:
        logging.error(f"Could not determine the current focused app: {e}")
    return None


# --- Main Service Logic ---


async def daily_bonus_service():
    """
    The main background service that checks for Duolingo app launches
    and triggers the daily bonus logic.
    """
    logging.info("Starting the Duolingo Daily Bonus service...")

    while True:
        try:
            current_app_package = await get_current_focused_app()

            if current_app_package == DUOLINGO_PACKAGE_NAME:
                logging.info("Duolingo app is in the foreground.")

                state = read_state()
                current_time = time.time()
                time_since_last_login = current_time - state.get("last_login", 0)

                if time_since_last_login > DAILY_BONUS_COOLDOWN_SECONDS:
                    logging.info("Eligible for daily bonus. Claiming now...")
                    success = await claim_daily_bonus()
                    if success:
                        state["last_login"] = int(current_time)
                        write_state(state)
                        logging.info(f"Updated last login time to: {current_time}")
                else:
                    logging.info(
                        f"Not yet eligible for daily bonus. Time since last login: {time_since_last_login / 3600:.2f} hours."
                    )

        except Exception as e:
            logging.error(f"An error occurred in the service loop: {e}")

        # Wait for the next check
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(daily_bonus_service())
    except KeyboardInterrupt:
        logging.info("Service stopped by user.")
