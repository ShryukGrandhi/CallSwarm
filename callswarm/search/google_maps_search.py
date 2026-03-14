"""Google Maps Places API search agent."""

import logging
import os

import httpx

from callswarm.models.data_models import Business

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


async def search_businesses(
    service_type: str,
    location: str,
    max_results: int = 10,
) -> list[Business]:
    """Search Google Maps for businesses matching the service type and location."""
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.error("GOOGLE_MAPS_API_KEY not set")
        return []

    query = f"{service_type} near {location}"
    logger.info("Searching Google Maps: %s", query)

    async with httpx.AsyncClient(timeout=15) as client:
        # Text search for businesses
        resp = await client.get(
            PLACES_TEXT_SEARCH_URL,
            params={"query": query, "key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            logger.warning("Places API status: %s", data.get("status"))
            return []

        results = data.get("results", [])[:max_results]
        businesses: list[Business] = []

        # Fetch phone numbers via Place Details
        for place in results:
            place_id = place.get("place_id", "")
            phone = await _get_phone_number(client, api_key, place_id)
            if not phone:
                continue  # skip businesses without phone numbers

            businesses.append(
                Business(
                    name=place.get("name", "Unknown"),
                    phone=phone,
                    address=place.get("formatted_address", ""),
                    rating=place.get("rating", 0.0),
                    place_id=place_id,
                )
            )

        logger.info("Found %d businesses with phone numbers", len(businesses))
        return businesses


async def _get_phone_number(
    client: httpx.AsyncClient, api_key: str, place_id: str
) -> str:
    """Fetch phone number for a place via Place Details API."""
    try:
        resp = await client.get(
            PLACE_DETAILS_URL,
            params={
                "place_id": place_id,
                "fields": "formatted_phone_number,international_phone_number",
                "key": api_key,
            },
        )
        resp.raise_for_status()
        result = resp.json().get("result", {})
        return (
            result.get("international_phone_number")
            or result.get("formatted_phone_number")
            or ""
        )
    except Exception as e:
        logger.warning("Failed to get phone for %s: %s", place_id, e)
        return ""
