"""Individual call agent - handles one business call with live transcript updates."""

import asyncio
import json
import logging
import os
from datetime import datetime

from google import genai

from callswarm.models.data_models import (
    AgentState,
    AgentStatus,
    Business,
    CallResult,
)
from callswarm.voice.vapi_client import VapiClient

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze this phone call transcript between an AI assistant and a business.

Extract the following information as JSON:
- available: boolean - is the service available at the requested time?
- times: list of strings - specific time slots mentioned (e.g. ["2:00pm", "3:30pm"])
- walk_in: boolean - are walk-ins accepted?
- notes: string - any other relevant information (pricing, special conditions, etc.)

If the business didn't answer, hung up, or the call failed, set available to false.

Return ONLY valid JSON, no markdown or explanation.

Transcript:
{transcript}"""


def _extract_transcript_from_call(call: dict) -> str:
    """Extract transcript text from a Vapi call object.

    Tries multiple locations where transcript data might be found.
    """
    # Try artifact.transcript first
    artifact = call.get("artifact", {})
    if artifact:
        transcript = artifact.get("transcript", "")
        if transcript:
            return transcript

        # Try building from artifact.messages
        messages = artifact.get("messages", [])
        if messages:
            return _format_messages(messages)

    # Try top-level transcript
    transcript = call.get("transcript", "")
    if transcript:
        return transcript

    # Try top-level messages
    messages = call.get("messages", [])
    if messages:
        return _format_messages(messages)

    return ""


def _format_messages(messages: list[dict]) -> str:
    """Format a list of message objects into readable transcript lines."""
    lines = []
    for msg in messages:
        role = msg.get("role", "")
        content = (
            msg.get("content", "")
            or msg.get("message", "")
            or msg.get("text", "")
        )
        if not content or not content.strip():
            continue
        if role in ("assistant", "bot", "ai"):
            lines.append(f"Agent: {content}")
        elif role in ("user", "customer", "human"):
            lines.append(f"Business: {content}")
        else:
            lines.append(content)
    return "\n".join(lines)


async def run_call_agent(
    business: Business,
    service_type: str,
    time_preference: str,
    agent_state: AgentState,
    on_status_change=None,
) -> CallResult:
    """Execute a single call agent's lifecycle.

    1. Dial the business via Vapi
    2. Poll for call completion with live transcript updates
    3. Extract structured results from transcript
    """
    vapi = VapiClient()

    async def _update_status(status: AgentStatus, error: str = None):
        agent_state.status = status
        if error:
            agent_state.error = error
        if on_status_change:
            await on_status_change(agent_state)

    try:
        # --- DIALING ---
        await _update_status(AgentStatus.DIALING)
        agent_state.started_at = datetime.utcnow()

        prompt = vapi.build_assistant_prompt(
            service_type=service_type,
            time_preference=time_preference,
            business_name=business.name,
        )

        call_data = await vapi.create_call(
            phone_number=business.phone,
            assistant_prompt=prompt,
        )

        if not call_data:
            await _update_status(AgentStatus.FAILED, "Failed to create call")
            return CallResult(
                business=business, available=False, notes="Call failed to connect"
            )

        call_id = call_data["id"]
        agent_state.call_id = call_id

        # --- SPEAKING (with live transcript polling) ---
        await _update_status(AgentStatus.SPEAKING)

        elapsed = 0.0
        timeout = 180
        poll_interval = 3
        completed_call = None

        while elapsed < timeout:
            call = await vapi.get_call(call_id)
            if call:
                # Extract live transcript and broadcast if changed
                transcript = _extract_transcript_from_call(call)
                if transcript and transcript != agent_state.transcript:
                    agent_state.transcript = transcript
                    if on_status_change:
                        await on_status_change(agent_state)

                # Check if call ended
                if call.get("status") in ("ended", "failed"):
                    completed_call = call
                    break

            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if not completed_call:
            completed_call = await vapi.get_call(call_id)

        if not completed_call:
            await _update_status(AgentStatus.FAILED, "Call timed out")
            return CallResult(
                business=business, available=False, notes="Call timed out"
            )

        # --- EXTRACTING ---
        await _update_status(AgentStatus.EXTRACTING)

        # Final transcript extraction
        transcript = _extract_transcript_from_call(completed_call) or ""
        agent_state.transcript = transcript
        call_duration = completed_call.get("duration", 0)

        result = await _extract_results(business, transcript, call_duration)

        # --- FINISHED ---
        agent_state.finished_at = datetime.utcnow()
        agent_state.result = result
        await _update_status(AgentStatus.FINISHED)

        return result

    except Exception as e:
        logger.error("Call agent error for %s: %s", business.name, e)
        await _update_status(AgentStatus.FAILED, str(e))
        return CallResult(
            business=business,
            available=False,
            notes=f"Error: {e}",
        )


async def _extract_results(
    business: Business, transcript: str, call_duration: float
) -> CallResult:
    """Use Gemini to extract structured results from call transcript."""
    if not transcript or not transcript.strip():
        return CallResult(
            business=business,
            available=False,
            transcript="",
            call_duration=call_duration,
            notes="No transcript available (call may not have connected)",
        )

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=EXTRACTION_PROMPT.format(transcript=transcript),
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0,
            ),
        )

        raw = json.loads(response.text)

        return CallResult(
            business=business,
            available=raw.get("available", False),
            times=raw.get("times", []),
            walk_in=raw.get("walk_in", False),
            notes=raw.get("notes", ""),
            transcript=transcript,
            call_duration=call_duration,
        )

    except Exception as e:
        logger.error("Extraction failed for %s: %s", business.name, e)
        return CallResult(
            business=business,
            available=False,
            transcript=transcript,
            call_duration=call_duration,
            notes=f"Extraction error: {e}",
        )
