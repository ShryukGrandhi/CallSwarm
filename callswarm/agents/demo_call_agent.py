"""Demo call agent - simulates realistic calls with fake transcript streaming."""

import asyncio
import logging
import random
from datetime import datetime

from callswarm.models.data_models import (
    AgentState,
    AgentStatus,
    Business,
    CallResult,
)

logger = logging.getLogger(__name__)

# Realistic conversation templates
CONVERSATIONS = [
    {
        "available": True,
        "times": ["2:00 PM", "3:30 PM", "5:00 PM"],
        "walk_in": True,
        "notes": "30 min session $45, 60 min $80",
        "lines": [
            ("agent", "Hi, I'm calling to check on availability for an appointment today."),
            ("biz", "Hi there! Yes, we're open today. What kind of service are you looking for?"),
            ("agent", "I'm looking for availability today, any time works."),
            ("biz", "Let me check... We have openings at 2 PM, 3:30 PM, and 5 PM."),
            ("agent", "That's great. Do you accept walk-ins as well?"),
            ("biz", "Yes, we do accept walk-ins but appointments are recommended."),
            ("agent", "Perfect. And what are the prices?"),
            ("biz", "A 30-minute session is $45 and a 60-minute session is $80."),
            ("agent", "Wonderful, thank you so much for the information!"),
            ("biz", "You're welcome! Have a great day."),
        ],
    },
    {
        "available": True,
        "times": ["11:30 AM", "1:00 PM"],
        "walk_in": False,
        "notes": "Appointment required, no walk-ins today",
        "lines": [
            ("agent", "Hello, I'm calling to see if you have any availability today."),
            ("biz", "Hello! Let me pull up the schedule. What time were you thinking?"),
            ("agent", "Anytime today would work. What do you have open?"),
            ("biz", "We have an 11:30 AM and a 1 PM slot available."),
            ("agent", "Do you take walk-ins?"),
            ("biz", "Not today, we're pretty booked up. You'd need to make an appointment."),
            ("agent", "Understood, thank you for checking!"),
            ("biz", "Of course, just give us a call back to book. Bye!"),
        ],
    },
    {
        "available": False,
        "times": [],
        "walk_in": False,
        "notes": "Fully booked today, suggested trying tomorrow morning",
        "lines": [
            ("agent", "Hi there, I'm calling to check on availability for today."),
            ("biz", "Hi! Unfortunately we're completely booked for today."),
            ("agent", "Oh I see. Is there anything available tomorrow?"),
            ("biz", "Tomorrow morning we have a few openings. Would you like me to book something?"),
            ("agent", "I'm just gathering information for now. Thank you for letting me know!"),
            ("biz", "No problem. Give us a call tomorrow and we'll get you in."),
        ],
    },
    {
        "available": True,
        "times": ["4:00 PM", "4:30 PM", "6:00 PM"],
        "walk_in": True,
        "notes": "Late afternoon slots available, walk-ins welcome after 3 PM",
        "lines": [
            ("agent", "Good afternoon! I'm checking if you have openings today."),
            ("biz", "Hey! Yeah we do. Our morning is full but the afternoon is pretty open."),
            ("agent", "What times are available?"),
            ("biz", "We've got 4 PM, 4:30, and 6 PM. Take your pick!"),
            ("agent", "Great options. Are walk-ins welcome too?"),
            ("biz", "After 3 PM, absolutely. Come on by anytime."),
            ("agent", "Thank you so much, that's really helpful!"),
            ("biz", "Happy to help! See you soon hopefully."),
        ],
    },
    {
        "available": False,
        "times": [],
        "walk_in": False,
        "notes": "No answer - voicemail",
        "lines": [
            ("agent", "Hi, I'm calling to check on availability for today."),
            ("biz", "You've reached our voicemail. We're unable to take your call right now. Please leave a message after the beep."),
            ("agent", "Thank you, I'll try calling back later. Goodbye."),
        ],
    },
    {
        "available": True,
        "times": ["12:00 PM", "2:30 PM"],
        "walk_in": True,
        "notes": "Lunch special discount 20% off until 2 PM",
        "lines": [
            ("agent", "Hi, I'm calling to ask about availability today."),
            ("biz", "Welcome! Yes, we have some openings. Are you flexible on time?"),
            ("agent", "Yes, any time today works for me."),
            ("biz", "Perfect. We can fit you in at noon or 2:30 PM."),
            ("agent", "Sounds good. Do you offer walk-ins?"),
            ("biz", "We sure do! And if you come before 2 PM, there's a 20% lunch special."),
            ("agent", "That's a great deal! Thank you for the information."),
            ("biz", "Anytime! Hope to see you soon."),
        ],
    },
]


async def run_demo_call_agent(
    business: Business,
    service_type: str,
    time_preference: str,
    agent_state: AgentState,
    on_status_change=None,
) -> CallResult:
    """Simulate a call agent with realistic delays and streaming transcript."""

    async def _update(status: AgentStatus, error: str = None):
        agent_state.status = status
        if error:
            agent_state.error = error
        if on_status_change:
            await on_status_change(agent_state)

    convo = random.choice(CONVERSATIONS)

    try:
        # --- DIALING ---
        agent_state.started_at = datetime.utcnow()
        await _update(AgentStatus.DIALING)
        await asyncio.sleep(random.uniform(1.5, 3.5))

        # --- SPEAKING (stream transcript line by line) ---
        await _update(AgentStatus.SPEAKING)

        transcript_lines = []
        for role, text in convo["lines"]:
            prefix = "Agent" if role == "agent" else "Business"
            transcript_lines.append(f"{prefix}: {text}")
            agent_state.transcript = "\n".join(transcript_lines)
            if on_status_change:
                await on_status_change(agent_state)
            await asyncio.sleep(random.uniform(1.2, 2.5))

        # --- EXTRACTING ---
        await _update(AgentStatus.EXTRACTING)
        await asyncio.sleep(random.uniform(0.8, 1.5))

        # --- FINISHED ---
        result = CallResult(
            business=business,
            available=convo["available"],
            times=convo["times"],
            walk_in=convo["walk_in"],
            notes=convo["notes"],
            transcript="\n".join(transcript_lines),
            call_duration=random.uniform(30, 90),
        )

        agent_state.finished_at = datetime.utcnow()
        agent_state.result = result
        await _update(AgentStatus.FINISHED)

        return result

    except Exception as e:
        logger.error("Demo agent error for %s: %s", business.name, e)
        await _update(AgentStatus.FAILED, str(e))
        return CallResult(business=business, available=False, notes=f"Error: {e}")
