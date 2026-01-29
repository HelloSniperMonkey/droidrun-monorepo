"""
Speech-to-Text WebSocket endpoint for real-time transcription using Google Cloud Speech-to-Text API.
"""

import asyncio
import json
import logging
import os
import queue
import threading
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google.cloud import speech

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Path to Google Cloud credentials - looks for credential.json in various locations
# speech.py is at: apps/gateway/src/ironclaw/api/speech.py
# We need to go up 6 levels to reach monorepo root
CREDENTIALS_PATHS = [
    Path(__file__).parent.parent.parent.parent.parent.parent / "credential.json",  # monorepo root
    Path(__file__).parent.parent.parent.parent.parent / "credential.json",  # apps/gateway/credential.json
    Path.home() / "credential.json",  # Home directory fallback
]


def get_credentials_path() -> str | None:
    """Find the credentials file path."""
    # First check environment variable
    env_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env_path and os.path.exists(env_path):
        return env_path
    
    # Search in known locations
    for path in CREDENTIALS_PATHS:
        if path.exists():
            return str(path)
    
    return None


class SpeechToTextSession:
    """
    Manages a single speech-to-text streaming session.
    Handles the async/sync bridge between WebSocket and Google's synchronous API.
    """
    
    def __init__(self, websocket: WebSocket, language_code: str = "en-US"):
        self.websocket = websocket
        self.language_code = language_code
        self.audio_queue: queue.Queue[bytes | None] = queue.Queue()
        self.result_queue: asyncio.Queue[dict] = asyncio.Queue()
        self.is_running = False
        self.recognition_thread: threading.Thread | None = None
        self.client: speech.SpeechClient | None = None
        
    def _audio_generator(self) -> Generator[speech.StreamingRecognizeRequest, None, None]:
        """Generator that yields audio requests from the queue."""
        while self.is_running:
            try:
                # Wait for audio chunk with timeout
                chunk = self.audio_queue.get(timeout=1.0)
                if chunk is None:
                    logger.info("Received stop signal in audio generator")
                    break
                yield speech.StreamingRecognizeRequest(audio_content=chunk)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Audio generator error: {e}")
                break
                
    def _recognition_worker(self):
        """Worker thread that runs the synchronous streaming recognition."""
        try:
            # Initialize client in the worker thread
            creds_path = get_credentials_path()
            if creds_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path
                logger.info(f"Using credentials from: {creds_path}")
            else:
                logger.warning("No credentials file found!")
                
            self.client = speech.SpeechClient()
            
            # Configure recognition
            recognition_config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code=self.language_code,
                enable_automatic_punctuation=True,
                model="latest_short",
            )
            
            streaming_config = speech.StreamingRecognitionConfig(
                config=recognition_config,
                interim_results=True,
                single_utterance=False,
            )
            
            logger.info("Starting streaming recognition...")
            
            # Start streaming recognition
            responses = self.client.streaming_recognize(
                streaming_config,
                self._audio_generator()
            )
            
            # Process responses
            for response in responses:
                if not self.is_running:
                    break
                    
                if not response.results:
                    continue
                
                result = response.results[0]
                if not result.alternatives:
                    continue
                
                alternative = result.alternatives[0]
                
                # Put result in the async queue
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(
                        self.result_queue.put({
                            "type": "final" if result.is_final else "interim",
                            "transcript": alternative.transcript,
                            "confidence": alternative.confidence if result.is_final else 0.0,
                            "is_final": result.is_final,
                        })
                    )
                finally:
                    loop.close()
                
                logger.debug(f"[{'final' if result.is_final else 'interim'}] {alternative.transcript}")
                
        except Exception as e:
            logger.error(f"Recognition worker error: {e}")
            try:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(
                    self.result_queue.put({
                        "type": "error",
                        "message": str(e)
                    })
                )
                loop.close()
            except:
                pass
        finally:
            self.is_running = False
            logger.info("Recognition worker stopped")
    
    def start(self):
        """Start the recognition session."""
        self.is_running = True
        self.recognition_thread = threading.Thread(target=self._recognition_worker, daemon=True)
        self.recognition_thread.start()
        logger.info("Speech-to-text session started")
        
    def stop(self):
        """Stop the recognition session."""
        self.is_running = False
        self.audio_queue.put(None)  # Signal the generator to stop
        if self.recognition_thread:
            self.recognition_thread.join(timeout=5.0)
        logger.info("Speech-to-text session stopped")
        
    def add_audio(self, audio_data: bytes):
        """Add audio data to the queue."""
        if self.is_running:
            self.audio_queue.put(audio_data)
            
    async def get_result(self, timeout: float = 0.1) -> dict | None:
        """Get a result from the queue with timeout."""
        try:
            return await asyncio.wait_for(self.result_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None


@router.websocket("/ws/speech-to-text")
async def websocket_speech_to_text(websocket: WebSocket):
    """
    WebSocket endpoint for real-time speech-to-text.
    
    Client Protocol:
    - Send {"type": "start", "language": "en-US"} to start recognition
    - Send binary audio data (16-bit PCM, 16kHz, mono)
    - Send {"type": "stop"} to stop recognition
    
    Server Response:
    - {"type": "ready"} when session is ready
    - {"type": "interim", "transcript": "...", "confidence": 0.0} for partial results
    - {"type": "final", "transcript": "...", "confidence": 0.95} for final results
    - {"type": "error", "message": "..."} on error
    - {"type": "stopped"} when session stops
    """
    await websocket.accept()
    logger.info("Speech-to-text WebSocket connection established")
    
    session: SpeechToTextSession | None = None
    
    try:
        while True:
            # Check for results if session is running
            if session and session.is_running:
                result = await session.get_result(timeout=0.05)
                if result:
                    await websocket.send_json(result)
            
            try:
                # Receive message with short timeout to allow processing results
                data = await asyncio.wait_for(websocket.receive(), timeout=0.05)
            except asyncio.TimeoutError:
                continue
            
            if "bytes" in data:
                # Audio data
                if session and session.is_running:
                    session.add_audio(data["bytes"])
                    
            elif "text" in data:
                # Control message
                msg = json.loads(data["text"])
                msg_type = msg.get("type")
                
                if msg_type == "start":
                    # Start new session
                    language = msg.get("language", "en-US")
                    
                    # Stop existing session if any
                    if session:
                        session.stop()
                    
                    # Create and start new session
                    session = SpeechToTextSession(websocket, language_code=language)
                    session.start()
                    await websocket.send_json({"type": "ready"})
                    
                elif msg_type == "stop":
                    # Stop session
                    if session:
                        session.stop()
                        session = None
                    await websocket.send_json({"type": "stopped"})
                    
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        if session:
            session.stop()
        logger.info("Speech-to-text WebSocket connection closed")
