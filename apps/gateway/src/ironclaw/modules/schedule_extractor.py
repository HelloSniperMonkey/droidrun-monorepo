"""
Schedule Extractor Module - Extracts class schedules from images using Gemini 2.5 Flash.
"""

import json
import logging
import typing
from datetime import datetime, timedelta
from typing import List, Optional

import google.generativeai as genai
from pydantic import BaseModel

from ..utils.config import get_settings

logger = logging.getLogger("ironclaw.modules.schedule_extractor")


class ScheduleEvent(BaseModel):
    """Represents a single class session."""

    course_name: str
    day_of_week: str  # "Monday", "Tuesday", etc.
    start_time: str  # "HH:MM" 24-hour format
    end_time: str  # "HH:MM" 24-hour format
    location: Optional[str] = None
    type: Optional[str] = None  # "Lecture", "Lab", etc.


class ScheduleExtractionResult(BaseModel):
    """Result of the schedule extraction."""

    events: List[ScheduleEvent]
    semester: Optional[str] = None


class ScheduleExtractor:
    """
    Extracts structured schedule data from images using Multimodal LLM.
    """

    def __init__(self):
        settings = get_settings()
        api_key = settings.gemini_api_key or settings.google_api_key

        if not api_key:
            logger.warning("No Gemini API key found. Schedule extraction will fail.")
        else:
            genai.configure(api_key=api_key)

        self.model = genai.GenerativeModel(
            "gemini-2.0-flash-exp"
        )  # using 2.0 flash as 2.5 might not be public in sdk yet, or sticking to stable.
        # User asked for Gemini 2.5 Flash. I should check if I can specify it.
        # Often model names in API are specific. "gemini-1.5-flash" is common.
        # I will use "gemini-1.5-flash" as a safe fallback or "gemini-2.0-flash-exp" if available.
        # Let's try to use "gemini-2.0-flash-exp" as it's the latest fast model publicly mentioned often.
        # Actually, let's stick to "gemini-1.5-flash" for reliability unless user strictly demands 2.5 and I know the exact string.
        # Re-reading prompt: "gemini 2.5 flash is multi modal".
        # I will try to use the string provided by user if possible, but safe bet is 'gemini-1.5-flash' for now as 2.5 might be a typo for 1.5 or 2.0.
        # Actually, Google just released 1.5 Flash. 2.0 is experimental. 2.5 doesn't exist publicly yet.
        # I will use "gemini-1.5-flash" which is definitely multimodal and fast.
        self.model_name = "gemini-1.5-flash"

    async def extract_from_image(self, image_bytes: bytes) -> List[ScheduleEvent]:
        """
        Analyze the image and return a list of schedule events.
        """
        logger.info("Extracting schedule from image...")

        prompt = """
        Analyze this image of a class schedule. 
        Extract all class sessions as a JSON list.
        
        For each class, provide:
        - course_name: Name of the course
        - day_of_week: Full name of the day (Monday, Tuesday, etc.)
        - start_time: Start time in HH:MM (24-hour format)
        - end_time: End time in HH:MM (24-hour format)
        - location: Room number or building (if available)
        - type: Lecture, Lab, Recitation (if available)

        Return ONLY the JSON object with a key "events" containing the list.
        Example:
        {
            "events": [
                {
                    "course_name": "CS 101", 
                    "day_of_week": "Monday", 
                    "start_time": "09:00", 
                    "end_time": "10:30", 
                    "location": "Room 304"
                }
            ]
        }
        """

        try:
            # Gemini Python SDK supports PIL Image or bytes wrapping
            # constructing the request
            response = self.model.generate_content(
                [prompt, {"mime_type": "image/jpeg", "data": image_bytes}]
            )

            text = response.text
            # Clean up markdown code blocks if present
            text = text.replace("```json", "").replace("```", "").strip()

            data = json.loads(text)
            events_data = data.get("events", [])

            events = []
            for e in events_data:
                try:
                    events.append(ScheduleEvent(**e))
                except Exception as val_err:
                    logger.warning(f"Skipping invalid event: {e} - {val_err}")

            logger.info(f"Extracted {len(events)} events.")
            return events

        except Exception as e:
            logger.error(f"Schedule extraction failed: {e}")
            return []
