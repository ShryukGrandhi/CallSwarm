"""smallest.ai voice model client.

This module provides a direct integration with smallest.ai's TTS/STT API
for cases where you want to use smallest.ai outside of Vapi's pipeline.

In the default CallSwarm flow, smallest.ai is used as the voice provider
within Vapi (configured in vapi_client.py). This client is available for
standalone voice synthesis if needed.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SMALLEST_API_URL = "https://api.smallest.ai/v1"


class SmallestClient:
    """Client for smallest.ai voice models."""

    def __init__(self):
        self.api_key = os.getenv("SMALLEST_API_KEY", "")

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def text_to_speech(
        self,
        text: str,
        voice_id: str = "emily",
        speed: float = 1.0,
    ) -> Optional[bytes]:
        """Convert text to speech audio bytes."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{SMALLEST_API_URL}/synthesize",
                    headers=self._headers(),
                    json={
                        "text": text,
                        "voice_id": voice_id,
                        "speed": speed,
                    },
                )
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                logger.error("TTS failed: %s", e)
                return None

    async def speech_to_text(
        self,
        audio_bytes: bytes,
        language: str = "en",
    ) -> Optional[str]:
        """Convert speech audio to text."""
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.post(
                    f"{SMALLEST_API_URL}/transcribe",
                    headers=self._headers(),
                    files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"language": language},
                )
                resp.raise_for_status()
                return resp.json().get("text", "")
            except Exception as e:
                logger.error("STT failed: %s", e)
                return None
