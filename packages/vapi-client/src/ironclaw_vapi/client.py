"""
Vapi API client for voice calls.
"""
import logging
from datetime import datetime
from typing import Optional

import httpx

logger = logging.getLogger("ironclaw.vapi.client")

VAPI_API_URL = "https://api.vapi.ai"


class VapiClient:
    """
    Client for Vapi REST API.
    Handles outbound calls and call management.
    """

    def __init__(self, api_key: str, phone_number_id: str):
        """
        Initialize Vapi client.

        Args:
            api_key: Vapi API key
            phone_number_id: Vapi phone number ID for outbound calls
        """
        self.api_key = api_key
        self.phone_number_id = phone_number_id

    def _get_headers(self) -> dict:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_call(
        self,
        phone_number: str,
        assistant_config: dict,
        name: Optional[str] = None,
        customer_name: str = "Iron Claw User",
    ) -> str:
        """
        Create an outbound call.

        Args:
            phone_number: Customer phone number (E.164 format)
            assistant_config: Vapi assistant configuration
            name: Optional name for the call
            customer_name: Name for the customer

        Returns:
            Call ID from Vapi
        """
        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": phone_number,
                "name": customer_name,
            },
            "assistant": assistant_config,
            "name": name or f"Call {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{VAPI_API_URL}/call",
                headers=self._get_headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        call_id = data.get("id", "unknown")
        logger.info(f"Call created: {call_id}")
        return call_id

    async def get_call(self, call_id: str) -> dict:
        """Get call details."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{VAPI_API_URL}/call/{call_id}",
                headers=self._get_headers(),
            )
            response.raise_for_status()
            return response.json()

    async def list_calls(self, limit: int = 10) -> list:
        """List recent calls."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{VAPI_API_URL}/call",
                headers=self._get_headers(),
                params={"limit": limit},
            )
            response.raise_for_status()
            return response.json()

    async def end_call(self, call_id: str) -> bool:
        """End an active call."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{VAPI_API_URL}/call/{call_id}",
                    headers=self._get_headers(),
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to end call {call_id}: {e}")
            return False
