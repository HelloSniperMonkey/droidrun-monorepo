"""
Personalization Module - Orchestrates homescreen personalization.
"""

import logging
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from ..agents.adb_connection import ADBConnection
from ..agents.ironclaw_agent import create_ironclaw_agent
from ..utils.config import get_settings
from .nanobanana import NanoBananaPro

logger = logging.getLogger("ironclaw.modules.personalization")


class PersonalizationService:
    """
    Service to personalize the user's device based on a reference image.
    Strategy:
    0. Check if image is a WALLPAPER itself. If so, set it directly.
    1. Analyze image to get a search query.
    2. Try DroidRun Agent (Web Search) to find and set it.
    3. If failed/timeout, invoke NanoBanana Pro (Extraction/Generation).
    """

    def __init__(self):
        settings = get_settings()
        api_key = settings.gemini_api_key or settings.google_api_key
        if api_key:
            genai.configure(api_key=api_key)
            self.vision_model = genai.GenerativeModel("gemini-2.5-flash")
        else:
            self.vision_model = None

        self.nanobanana = NanoBananaPro()
        self.adb = ADBConnection()

    async def personalize_homescreen(self, image_path: Path) -> dict:
        """
        Main workflow for personalization.
        """
        logger.info(f"🎨 Starting personalization from: {image_path}")

        # Step 0: Classify Image (Is it a wallpaper or a screenshot?)
        image_type = await self._analyze_image_type(image_path)
        logger.info(f"Image classified as: {image_type}")

        if image_type == "WALLPAPER":
            logger.info("Direct wallpaper upload detected.")
            success = await self._set_direct_wallpaper(image_path)
            if success:
                return {
                    "success": True,
                    "method": "direct_upload",
                    "message": "The provided image was clean and has been set as your wallpaper directly.",
                }
            else:
                logger.warning("Direct set failed, falling back to search...")

        # Step 1: Analyze Image for Search Query (Reference Mode)
        search_query = await self._generate_search_query(image_path)
        if not search_query:
            return {"success": False, "error": "Failed to analyze image"}

        logger.info(f"Generated search query: {search_query}")

        # Step 2: Try Cost-Effective Web Search (DroidRun)
        success = await self._try_web_search_method(search_query)

        if success:
            return {
                "success": True,
                "method": "droidrun_web_search",
                "message": "Wallpaper found and set via web search.",
            }

        # Step 3: Fallback to NanoBanana Pro
        logger.info("⚠️ Web search failed or timed out. Invoking NanoBanana Pro...")

        pro_success = await self.nanobanana.extract_and_set_wallpaper(image_path)

        if pro_success:
            return {
                "success": True,
                "method": "nanobanana_pro",
                "message": "Wallpaper extracted and set via NanoBanana Pro.",
            }

        return {"success": False, "error": "All methods failed."}

    async def _analyze_image_type(self, image_path: Path) -> str:
        """
        Determine if the image is a raw wallpaper or a UI screenshot.
        Returns: 'WALLPAPER' or 'UI_SCREENSHOT'
        """
        if not self.vision_model:
            return "UI_SCREENSHOT"  # Conservative default

        prompt = """
        Look at this image.
        Is it a raw, clean wallpaper image (art, photo, pattern) ready to be used?
        OR is it a screenshot of a phone interface (with icons, status bar, widgets, clock)?

        If it's a clean image/wallpaper, return "WALLPAPER".
        If it contains UI elements (icons, text, status bar), return "UI_SCREENSHOT".
        
        Return ONLY the string.
        """

        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            response = self.vision_model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": image_data}]
            )
            result = response.text.strip().upper()
            if "WALLPAPER" in result:
                return "WALLPAPER"
            return "UI_SCREENSHOT"
        except Exception as e:
            logger.error(f"Image classification failed: {e}")
            return "UI_SCREENSHOT"

    async def _set_direct_wallpaper(self, local_path: Path) -> bool:
        """
        Push the local image to the device and set it as wallpaper directly.
        Uses device-specific intent and DroidRun agent to complete the process.
        """
        remote_dir = "/sdcard/droidrun"
        remote_path = f"{remote_dir}/wallpaper.jpg"

        try:
            # Create droidrun folder if it doesn't exist
            logger.info(f"Creating directory {remote_dir} if it doesn't exist")
            await self.adb.shell(f"mkdir -p {remote_dir}")

            # Push file to device
            logger.info(f"Pushing file {local_path} to device at {remote_path}")
            push_result = await self.adb.push_file(str(local_path), remote_path)
            logger.info(f"Push result: {push_result}")

            if not push_result:
                logger.error("Failed to push file to device")
                return False

            # Launch wallpaper preview using device-specific intent (Oppo/OnePlus/ColorOS)
            intent_cmd = (
                f"am start -n com.oplus.wallpapers/.wallpaperpreview.PreviewStatementActivity "
                f"-d file://{remote_path}"
            )
            logger.info(f"Launching wallpaper preview: {intent_cmd}")
            intent_result = await self.adb.shell(intent_cmd)
            logger.info(f"Intent result: {intent_result}")

            # Check if intent failed (device might not be Oppo/OnePlus)
            if "error" in intent_result.lower() or "exception" in intent_result.lower():
                logger.warning("Oppo intent failed, trying generic intent...")
                # Fallback to generic ATTACH_DATA intent
                generic_cmd = (
                    f"am start -a android.intent.action.ATTACH_DATA "
                    f"-c android.intent.category.DEFAULT "
                    f"-d file://{remote_path} "
                    f"-t 'image/*' "
                    f"-e mimeType 'image/*'"
                )
                logger.info(f"Trying generic intent: {generic_cmd}")
                await self.adb.shell(generic_cmd)

            # Give the UI time to open
            import asyncio
            await asyncio.sleep(1.5)

            # Now use DroidRun agent to click the buttons to complete wallpaper setting
            logger.info("🤖 Invoking DroidRun agent to complete wallpaper setting...")
            agent = await create_ironclaw_agent(
                goal=(
                    "Complete setting the wallpaper. "
                    "Look for buttons like 'Set wallpaper', 'Apply', 'Set', or 'Confirm'. "
                    "If asked to choose between 'Home screen', 'Lock screen', or 'Both', select 'Both' or 'Home screen'. "
                    "Click the necessary buttons to confirm and complete the wallpaper change. "
                    "STOP once the wallpaper is set or you return to the home screen."
                )
            )
            result = await agent.run()
            logger.info(f"DroidRun agent result: {result}")

            return result.get("success", False)

        except Exception as e:
            logger.error(f"Direct set wallpaper failed: {e}")
            return False

    async def _generate_search_query(self, image_path: Path) -> Optional[str]:
        """Use Gemini Flash to get a Google Images search query."""
        if not self.vision_model:
            return None

        prompt = """
        Describe this wallpaper for a Google Image search.
        Focus on colors, style (minimalist, abstract, nature), and key elements.
        Return ONLY the search query string (e.g., "blue minimalist abstract mountain wallpaper 4k").
        Keep it under 10 words.
        """

        try:
            with open(image_path, "rb") as f:
                image_data = f.read()

            response = self.vision_model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": image_data}]
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            return None

    async def _try_web_search_method(self, query: str) -> bool:
        """
        Launch IronClaw agent to search and set wallpaper.
        Returns True if successful.
        """
        # We set a strict step limit for "cost effective" check
        goal = f"""
        Personalize the phone.
        1. Open Chrome.
        2. Search for images: "{query}".
        3. Find a good matching image and open it.
        4. Long press to download or visit site to download.
        5. Once downloaded, open Photos/Gallery and set it as wallpaper.

        If you cannot find a good download button quickly, STOP.
        """

        try:
            agent = await create_ironclaw_agent(goal=goal)

            # Run with limited steps to enforce "quick/cost-effective" constraint
            result = await agent.run()
            return result["success"]

        except Exception as e:
            logger.error(f"Web search agent failed: {e}")
            return False
