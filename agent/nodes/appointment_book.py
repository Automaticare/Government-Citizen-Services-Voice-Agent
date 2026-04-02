"""
Appointment booking node.

Validates request and books appointment. In production this would
call a real government scheduling API.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger

logger = get_logger(__name__)

# Mock available slots
MOCK_SLOTS = [
    {"date": "2026-04-07", "time": "10:00", "office": "Kadikoy Nufus Mudurlugu"},
    {"date": "2026-04-07", "time": "14:00", "office": "Kadikoy Nufus Mudurlugu"},
    {"date": "2026-04-08", "time": "09:00", "office": "Uskudar Nufus Mudurlugu"},
    {"date": "2026-04-09", "time": "11:00", "office": "Besiktas Nufus Mudurlugu"},
]


def appointment_book(state: AgentState) -> dict:
    """Book an appointment for the citizen."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I need to verify your identity before booking an appointment."
               if language == "en" else
               "Randevu almak icin kimlik dogrulamasi gerekiyor.")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": _mark_completed(state, "appointment_book"),
        }

    first_name = profile.get("first_name", "")
    slot = MOCK_SLOTS[0]  # Pick first available slot

    if language == "en":
        msg = (f"{first_name}, your appointment has been booked. "
               f"Date: {slot['date']}, Time: {slot['time']}, "
               f"Location: {slot['office']}. "
               f"Please bring your ID card and any required documents.")
    else:
        msg = (f"{first_name}, randevunuz olusturuldu. "
               f"Tarih: {slot['date']}, Saat: {slot['time']}, "
               f"Yer: {slot['office']}. "
               f"Lutfen nufus cuzdaninizi ve gerekli belgeleri yaninda getirin.")

    logger.info(f"Appointment booked for session | slot={slot['date']} {slot['time']}")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": _mark_completed(state, "appointment_book"),
    }


def _mark_completed(state: AgentState, intent: str) -> list:
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed
