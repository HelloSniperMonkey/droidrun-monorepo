"""
WebSocket proxy for MobileRun cloud streaming.
This proxy is necessary because browsers cannot set custom headers on WebSocket connections,
but MobileRun's streaming API requires the Authorization header.
"""

import asyncio
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
import websockets
from websockets.exceptions import ConnectionClosed

from ..utils.config import get_settings

router = APIRouter()
logger = logging.getLogger("ironclaw.mobilerun_ws")

MOBILERUN_WS_BASE = "wss://api.mobilerun.ai/v1/devices"


@router.websocket("/devices/{device_id}/stream")
async def proxy_device_stream(websocket: WebSocket, device_id: str):
    """
    WebSocket proxy for MobileRun device streaming.
    Forwards messages between the browser and MobileRun, adding the required Authorization header.
    """
    settings = get_settings()
    api_key = settings.mobilerun_api_key
    
    if not api_key:
        await websocket.close(code=4001, reason="MOBILERUN_API_KEY not configured")
        return
    
    # Accept the browser WebSocket connection
    await websocket.accept()
    logger.info(f"[WS Proxy] Browser connected for device: {device_id}")
    
    # Connect to MobileRun with Authorization header
    mobilerun_url = f"{MOBILERUN_WS_BASE}/{device_id}/stream"
    headers = {
        "Authorization": api_key,
    }
    
    try:
        async with websockets.connect(
            mobilerun_url,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=10,
        ) as mobilerun_ws:
            logger.info(f"[WS Proxy] Connected to MobileRun: {mobilerun_url}")
            
            async def forward_to_mobilerun():
                """Forward messages from browser to MobileRun."""
                try:
                    while True:
                        data = await websocket.receive_text()
                        await mobilerun_ws.send(data)
                except WebSocketDisconnect:
                    logger.info("[WS Proxy] Browser disconnected")
                except Exception as e:
                    logger.error(f"[WS Proxy] Error forwarding to MobileRun: {e}")
            
            async def forward_to_browser():
                """Forward messages from MobileRun to browser."""
                try:
                    async for message in mobilerun_ws:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except ConnectionClosed:
                    logger.info("[WS Proxy] MobileRun disconnected")
                except Exception as e:
                    logger.error(f"[WS Proxy] Error forwarding to browser: {e}")
            
            # Run both forwarding tasks concurrently
            browser_task = asyncio.create_task(forward_to_mobilerun())
            mobilerun_task = asyncio.create_task(forward_to_browser())
            
            # Wait for either to complete (one side disconnects)
            done, pending = await asyncio.wait(
                [browser_task, mobilerun_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining task
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                    
    except websockets.exceptions.InvalidStatusCode as e:
        logger.error(f"[WS Proxy] MobileRun connection failed: {e.status_code}")
        await websocket.close(code=4002, reason=f"MobileRun error: {e.status_code}")
    except Exception as e:
        logger.error(f"[WS Proxy] Connection error: {e}")
        await websocket.close(code=4003, reason=str(e))
    finally:
        logger.info(f"[WS Proxy] Session ended for device: {device_id}")
