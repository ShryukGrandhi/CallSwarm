"""Vapi API client for making outbound phone calls."""

import asyncio
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

VAPI_BASE_URL = "https://api.vapi.ai"


class VapiClient:
    """Client for Vapi outbound calling API."""

    def __init__(self):
        self.api_key = os.getenv("VAPI_API_KEY")
        self.phone_number_id = os.getenv("VAPI_PHONE_NUMBER_ID")
        if not self.api_key:
            logger.warning("VAPI_API_KEY not set")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def create_call(
        self,
        phone_number: str,
        assistant_prompt: str,
        first_message: str = "Hi, I'm calling to check on availability.",
    ) -> Optional[dict]:
        """Create an outbound phone call via Vapi.

        Returns the call object with call_id, or None on failure.
        """
        payload = {
            "phoneNumberId": self.phone_number_id,
            "customer": {
                "number": phone_number,
            },
            "assistant": {
                "model": {
                    "provider": "google",
                    "model": "gemini-2.5-flash",
                    "messages": [
                        {"role": "system", "content": assistant_prompt},
                    ],
                },
                "voice": {
                    "provider": "smallest-ai",
                    "voiceId": "emily",
                },
                "firstMessage": first_message,
                "endCallMessage": "Thank you for your time! Goodbye.",
                "transcriber": {
                    "provider": "deepgram",
                    "model": "nova-2",
                    "language": "en",
                },
            },
        }

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{VAPI_BASE_URL}/call/phone",
                    headers=self._headers(),
                    json=payload,
                )
                resp.raise_for_status()
                call_data = resp.json()
                logger.info(
                    "Call created: %s -> %s", call_data.get("id"), phone_number
                )
                return call_data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "Failed to create call to %s: %s | Response: %s",
                    phone_number, e, e.response.text,
                )
                return None
            except Exception as e:
                logger.error("Failed to create call to %s: %s", phone_number, e)
                return None

    async def get_call(self, call_id: str) -> Optional[dict]:
        """Get call status and details."""
        async with httpx.AsyncClient(timeout=15) as client:
            try:
                resp = await client.get(
                    f"{VAPI_BASE_URL}/call/{call_id}",
                    headers=self._headers(),
                )
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                logger.error("Failed to get call %s: %s", call_id, e)
                return None

    async def wait_for_call_completion(
        self, call_id: str, timeout: float = 180, poll_interval: float = 5
    ) -> Optional[dict]:
        """Poll until call is complete or timeout."""
        elapsed = 0.0
        while elapsed < timeout:
            call = await self.get_call(call_id)
            if call and call.get("status") in ("ended", "failed"):
                return call
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
        logger.warning("Call %s timed out after %.0fs", call_id, timeout)
        return await self.get_call(call_id)

    def build_assistant_prompt(
        self, service_type: str, time_preference: str, business_name: str
    ) -> str:
        """Build the conversation prompt for the AI assistant on the call."""
        return f"""You are a friendly AI assistant calling {business_name} on behalf of a customer.

Your goal: determine if the business has {service_type} availability {time_preference}.

Follow these conversation steps:
1. Introduce yourself politely: "Hi, I'm calling to check on availability for a {service_type}."
2. Ask if {service_type} appointments are available {time_preference}.
3. If available, ask what specific time slots are open.
4. Ask if walk-ins are accepted.
5. Thank them and end the call.

Important rules:
- Be concise and polite.
- Do not book an appointment, only gather information.
- If they ask who you are, say you're an AI assistant helping a customer find availability.
- If they can't help or hang up, end the call politely.
- Keep the conversation under 2 minutes."""
