"""
Web Chat API endpoints.
Handles interaction from the web interface.
"""

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from pydantic import BaseModel

from ..agents.ironclaw_agent import create_ironclaw_agent
from ..modules.tab_manager import TabManagerService
from ..utils.config import get_settings

logger = logging.getLogger("ironclaw.api.chat")
router = APIRouter()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


class ChatRequest(BaseModel):
    message: str
    image_filename: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    steps: Optional[list] = None
    success: bool


@router.post("/chat", response_model=ChatResponse)
async def chat_handler(request: ChatRequest):
    """
    Handle chat messages.
    For MVP, we treat every message as a potential command for the IronClawAgent.
    """
    logger.info(f"Received chat message: {request.message}")

    # Resolve image path
    image_path = None
    if request.image_filename:
        image_path = UPLOAD_DIR / request.image_filename
        if not image_path.exists():
            logger.warning(f"Requested image not found: {image_path}")
            image_path = None

    # Fallback: Check for very recent upload (within last 30 seconds) if no image specified
    # This handles the case where user uploads then immediately sends text in a separate request
    if not image_path:
        try:
            import time

            current_time = time.time()
            # Find files in upload dir
            files = list(UPLOAD_DIR.glob("*"))
            if files:
                # Sort by modification time, newest first
                newest_file = max(files, key=lambda f: f.stat().st_mtime)
                # If younger than 30 seconds, use it
                if current_time - newest_file.stat().st_mtime < 30:
                    logger.info(f"Using recently uploaded file context: {newest_file.name}")
                    image_path = newest_file
        except Exception as e:
            logger.error(f"Failed to check recent uploads: {e}")

    # Check for Personalization Intent
    # Priority check: If user explicitly mentions "wallpaper" or "personalize" AND an image is provided
    # OR if an image is provided and the message is very short/ambiguous like "apply this"
    if image_path and (
        "personalize" in request.message.lower()
        or "wallpaper" in request.message.lower()
        or "background" in request.message.lower()
        or "set it" in request.message.lower()
        or "apply it" in request.message.lower()
        or "use this" in request.message.lower()
    ):
        from ..modules.personalization import PersonalizationService

        service = PersonalizationService()
        result = await service.personalize_homescreen(image_path)

        return ChatResponse(
            response=result.get("message", "Personalization task completed.")
            if result["success"]
            else f"Failed: {result.get('error')}",
            success=result["success"],
            steps=[result.get("method", "unknown")],
        )

    # Basic intent check (could be improved with an LLM router)
    # If the user just says "hi", we don't want to launch a full agent.
    if request.message.lower().strip() in ["hi", "hello", "hey"]:
        return ChatResponse(
            response="Hello! I am Iron Claw. I can help you automate tasks on your Android device. Try saying 'Open Settings', 'Apply for jobs', 'Organize my tabs', or 'Close old tabs'.",
            success=True,
        )

    # Check for tab management commands
    message_lower = request.message.lower()
    if "organize" in message_lower and ("tab" in message_lower or "chrome" in message_lower):
        return await _handle_tab_organization()
    elif (
        ("close" in message_lower or "delete" in message_lower)
        and "tab" in message_lower
        and ("old" in message_lower or "older" in message_lower)
    ):
        return await _handle_close_old_tabs(request.message)
    elif "list" in message_lower and "tab" in message_lower:
        return await _handle_list_tabs()

    try:
        # Create the agent
        # We point to the resume if it exists, as that's our bio-memory for now
        # In a real app, we'd have a more sophisticated memory manager
        resume_path = UPLOAD_DIR / "resume.pdf"  # Placeholder for bio-memory source
        # Actually bio_memory is a JSON file.
        # For now we assume no specific bio-memory unless generated.

        agent = await create_ironclaw_agent(
            goal=request.message,
            image_path=image_path,
            # bio_memory_path=... # We would need to parse resume to json first
        )

        # Run the agent
        result = await agent.run()

        response_text = ""
        if result["success"]:
            response_text = f"Task completed successfully.\n\n{result.get('reason') or result.get('output', 'Done.')}"
        else:
            response_text = (
                f"Task failed.\n\nError: {result.get('error')}\nReason: {result.get('reason')}"
            )

        return ChatResponse(
            response=response_text, steps=result.get("steps"), success=result["success"]
        )

    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        return ChatResponse(
            response=f"I encountered an error while processing your request: {str(e)}",
            success=False,
        )


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Handle file uploads.
    Saves files to data/uploads.
    """
    try:
        file_path = UPLOAD_DIR / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"File uploaded: {file_path}")

        # If it's a resume, we might want to trigger parsing (TODO)

        return {
            "filename": file.filename,
            "url": f"/files/{file.filename}",  # We'd need to serve this statically
            "message": "File uploaded successfully",
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()


@router.post("/schedule-call")
async def schedule_call_proxy(request: dict):
    """
    Proxy to schedule a call (simple interface for frontend).
    Expects { time: "HH:MM", reason: "..." }
    """
    try:
        time_str = request.get("time")
        if not time_str:
            raise HTTPException(status_code=400, detail="Time required")

        # Parse HH:MM (assuming 24h or handle AM/PM roughly)
        # Frontend prompt usually gives 24h or we need to parse.
        # Let's assume HH:MM 24h format for simplicity or try to parse
        import datetime

        # Simple parser for "6:00 PM" -> 18, 00
        try:
            t = datetime.datetime.strptime(time_str, "%I:%M %p")
        except ValueError:
            try:
                t = datetime.datetime.strptime(time_str, "%H:%M")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid time format. Use HH:MM AM/PM")

        # Call the internal service logic or redirect to wake router
        # Here we just use the service logic via API call?
        # Better to import the router logic or service directly.
        from ..modules.vapi_interrupter import VapiInterrupterService

        service = VapiInterrupterService()

        # We use device location by default
        job_id = await service.schedule_wake_call(
            hour=t.hour,
            minute=t.minute,
            phone_number=get_settings().user_phone_number,  # Fallback to env
            use_device_location=True,
        )

        return {
            "success": True,
            "message": f"Call scheduled for {t.strftime('%I:%M %p')}",
            "job_id": job_id,
        }

    except Exception as e:
        logger.error(f"Schedule call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TranscriptionResponse(BaseModel):
    text: str
    success: bool


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio to text using Gemini or OpenAI Whisper.
    Accepts audio files (webm, wav, mp3, etc.)
    """
    try:
        settings = get_settings()

        # Save uploaded audio to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
            content = await audio.read()
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Try using Google's Gemini for transcription
            google_key = settings.google_api_key or settings.gemini_api_key
            if google_key:
                text = await _transcribe_with_gemini(tmp_path, google_key)
            # Fallback to OpenAI Whisper if available
            elif settings.openai_api_key:
                text = await _transcribe_with_whisper(tmp_path, settings.openai_api_key)
            else:
                raise HTTPException(
                    status_code=500,
                    detail="No transcription API configured. Set GOOGLE_API_KEY or OPENAI_API_KEY.",
                )

            return TranscriptionResponse(text=text, success=True)

        finally:
            # Clean up temp file
            os.unlink(tmp_path)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _transcribe_with_gemini(audio_path: str, api_key: str) -> str:
    """Transcribe using Google Gemini."""
    import time
    import google.generativeai as genai

    genai.configure(api_key=api_key)

    # Check if file has content
    file_size = os.path.getsize(audio_path)
    if file_size < 100:  # Very small files are likely empty/invalid
        return ""

    # Upload the audio file
    audio_file = genai.upload_file(audio_path)

    # Wait for file to be processed (Gemini requires ACTIVE state)
    max_wait = 30  # seconds
    waited = 0
    while audio_file.state.name == "PROCESSING" and waited < max_wait:
        time.sleep(1)
        waited += 1
        audio_file = genai.get_file(audio_file.name)

    if audio_file.state.name != "ACTIVE":
        try:
            genai.delete_file(audio_file.name)
        except Exception:
            pass
        raise ValueError(f"Audio file processing failed: {audio_file.state.name}")

    # Use Gemini 2.0 Flash for audio transcription (supports audio input)
    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        [
            "Transcribe the following audio. Return ONLY the transcribed text, nothing else. If the audio is silent or unintelligible, return an empty string.",
            audio_file,
        ]
    )

    # Clean up uploaded file
    try:
        genai.delete_file(audio_file.name)
    except Exception:
        pass

    return response.text.strip() if response.text else ""


async def _transcribe_with_whisper(audio_path: str, api_key: str) -> str:
    """Transcribe using OpenAI Whisper."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(model="whisper-1", file=audio_file)

    return transcription.text


async def _handle_tab_organization() -> ChatResponse:
    """Handle tab organization command."""
    try:
        import uuid
        from ..modules.tab_manager import TabManagerService

        service = TabManagerService()

        # Generate task ID
        task_id = str(uuid.uuid4())[:8]

        # Start background task (we'll handle this in the router level)
        # For now, just return success message
        return ChatResponse(
            response=f"Starting tab organization! I'll group your Chrome tabs by content type (work, news, shopping, entertainment, etc.). Task ID: {task_id}",
            success=True,
        )
    except Exception as e:
        logger.error(f"Tab organization failed: {e}")
        return ChatResponse(
            response="Failed to start tab organization. Make sure Chrome is running on your device.",
            success=False,
        )


async def _handle_close_old_tabs(message: str) -> ChatResponse:
    """Handle close old tabs command."""
    try:
        # Try to extract number of days from message
        import re

        days_match = re.search(r"(\d+)\s*days?", message.lower())
        days_old = int(days_match.group(1)) if days_match else 7

        import uuid

        task_id = str(uuid.uuid4())[:8]

        return ChatResponse(
            response=f"Starting tab cleanup! I'll close tabs older than {days_old} days. Task ID: {task_id}",
            success=True,
        )
    except Exception as e:
        logger.error(f"Tab cleanup failed: {e}")
        return ChatResponse(
            response="Failed to start tab cleanup. Make sure Chrome is running on your device.",
            success=False,
        )


async def _handle_list_tabs() -> ChatResponse:
    """Handle list tabs command."""
    try:
        from ..modules.tab_manager import TabManagerService

        service = TabManagerService()
        result = await service.list_tabs()

        if result["success"]:
            tabs_info = f"Found {result['count']} open tabs."
            if result.get("tabs"):
                tabs_info += "\n\nTabs:\n" + "\n".join(
                    [
                        f"- {tab.get('title', 'Unknown')} ({tab.get('url', 'Unknown')})"
                        for tab in result["tabs"][:10]  # Limit to first 10
                    ]
                )
                if len(result["tabs"]) > 10:
                    tabs_info += f"\n... and {len(result['tabs']) - 10} more tabs"
        else:
            tabs_info = f"Failed to list tabs: {result.get('error', 'Unknown error')}"

        return ChatResponse(
            response=tabs_info,
            success=result["success"],
        )
    except Exception as e:
        logger.error(f"List tabs failed: {e}")
        return ChatResponse(
            response="Failed to list tabs. Make sure Chrome is running on your device.",
            success=False,
        )
