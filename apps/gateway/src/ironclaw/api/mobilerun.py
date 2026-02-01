"""
MobileRun API proxy endpoints for cloud device streaming.
This proxy avoids CORS issues when calling the MobileRun API from the browser.
"""

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

from ..utils.config import get_settings

router = APIRouter()

MOBILERUN_API_URL = "https://api.mobilerun.ai/v1"


def get_mobilerun_api_key() -> str:
    """Get MobileRun API key from settings."""
    settings = get_settings()
    key = settings.mobilerun_api_key
    if not key:
        raise HTTPException(
            status_code=500,
            detail="MOBILERUN_API_KEY not configured on server"
        )
    return key


class DeviceInfo(BaseModel):
    id: str
    name: Optional[str] = None
    state: Optional[str] = None
    stateMessage: Optional[str] = None
    streamUrl: Optional[str] = None
    streamToken: Optional[str] = None
    deviceType: Optional[str] = None
    country: Optional[str] = None
    provider: Optional[str] = None
    apps: Optional[List[str]] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None
    assignedAt: Optional[str] = None
    taskCount: Optional[int] = None


class PaginationInfo(BaseModel):
    hasNext: bool
    hasPrev: bool
    page: int
    pageSize: int
    pages: int
    total: int


class DevicesResponse(BaseModel):
    items: List[DeviceInfo]
    pagination: PaginationInfo


class DeviceCountResponse(BaseModel):
    count: int


@router.get("/devices", response_model=DevicesResponse)
async def list_devices(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    orderBy: str = Query(default="createdAt"),
    orderByDirection: str = Query(default="desc"),
    state: Optional[str] = None,
    provider: Optional[str] = None,
):
    """
    List MobileRun cloud devices.
    Proxies requests to avoid CORS issues.
    """
    api_key = get_mobilerun_api_key()
    
    params = {
        "page": page,
        "pageSize": pageSize,
        "orderBy": orderBy,
        "orderByDirection": orderByDirection,
    }
    
    if state:
        params["state"] = state
    if provider:
        params["provider"] = provider
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MOBILERUN_API_URL}/devices",
                params=params,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"MobileRun API error: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to MobileRun API: {str(e)}"
        )


@router.get("/devices/count", response_model=DeviceCountResponse)
async def get_device_count():
    """
    Get total count of MobileRun cloud devices.
    Proxies requests to avoid CORS issues.
    """
    api_key = get_mobilerun_api_key()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MOBILERUN_API_URL}/devices/count",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"MobileRun API error: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to MobileRun API: {str(e)}"
        )


@router.get("/devices/{device_id}")
async def get_device(device_id: str):
    """
    Get a specific MobileRun cloud device by ID.
    Proxies requests to avoid CORS issues.
    """
    api_key = get_mobilerun_api_key()
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{MOBILERUN_API_URL}/devices/{device_id}",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=30.0,
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"MobileRun API error: {response.text}"
                )
            
            return response.json()
            
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to MobileRun API: {str(e)}"
        )


@router.get("/physical-device")
async def get_physical_device():
    """
    Get the configured physical device ID from environment variables.
    Returns the device_id if configured, otherwise returns null.
    """
    settings = get_settings()
    device_id = settings.mobilerun_device_id
    
    if not device_id:
        return {"device_id": None}
    
    return {"device_id": device_id}
