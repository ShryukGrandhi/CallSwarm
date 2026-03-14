"""Intent parsing agent - converts natural language to structured task."""

import json
import logging
import os

from google import genai

from callswarm.models.data_models import ParsedIntent

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a task parser. Given a user request, extract structured information.

Return a JSON object with these fields:
- service_type: what service the user needs (e.g. "haircut", "oil change", "dental cleaning")
- location: where the user wants the service (city, neighborhood, or "nearby" if not specified)
- time_preference: when they want it (e.g. "today", "tomorrow", "this week", "Saturday")
- urgency: "high" if today/ASAP, "normal" if within a few days, "low" if flexible
- constraints: list of any additional requirements (e.g. ["walk-in", "under $30", "speaks Spanish"])

Return ONLY valid JSON, no markdown or explanation."""


async def parse_intent(query: str, default_location: str = "nearby") -> ParsedIntent:
    """Parse a user query into a structured intent."""
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=query,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0,
            ),
        )

        raw = json.loads(response.text)
        intent = ParsedIntent(
            service_type=raw.get("service_type", "service"),
            location=raw.get("location", default_location),
            time_preference=raw.get("time_preference", "today"),
            urgency=raw.get("urgency", "normal"),
            constraints=raw.get("constraints", []),
        )
        logger.info("Parsed intent: %s", intent.model_dump())
        return intent

    except Exception as e:
        logger.error("Intent parsing failed: %s", e)
        # Fallback: basic keyword extraction
        return ParsedIntent(
            service_type=query.split()[-1] if query.split() else "service",
            location=default_location,
            time_preference="today",
            urgency="normal",
        )
