"""
Appointment booking node.

Calls the government API to book a real appointment.
Falls back to mock data if API is unavailable.
"""

import httpx
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

API_BASE = "http://localhost:8001"


def _book_via_api(citizen_id: int, service_type: str, preferred_date: str | None) -> dict | None:
    """Call government API to book appointment."""
    try:
        payload = {
            "citizen_id": citizen_id,
            "service_type": service_type,
            "preferred_date": preferred_date or "2026-04-07",
        }
        r = httpx.post(f"{API_BASE}/appointments", json=payload, timeout=5.0)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"Appointment API returned {r.status_code}: {r.text}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Appointment API unreachable: {e}")
        return None


def appointment_book(state: AgentState) -> dict:
    """Book an appointment for the citizen via government API."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I need to verify your identity before booking an appointment."
               if language == "en" else
               "Randevu almak icin kimlik dogrulamasi gerekiyor.")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": mark_completed(state, "appointment_book"),
        }

    first_name = profile.get("first_name", "")
    citizen_id = profile.get("citizen_id")

    # Call government API
    result = _book_via_api(citizen_id, "general", None)

    if result:
        date = result.get("appointment_date", "")
        time = result.get("appointment_time", "")
        office = result.get("office", "")

        if language == "en":
            msg = (f"{first_name}, your appointment has been booked. "
                   f"Date: {date}, Time: {time}, Location: {office}. "
                   f"Please bring your ID card and any required documents.")
        else:
            msg = (f"{first_name}, randevunuz olusturuldu. "
                   f"Tarih: {date}, Saat: {time}, Yer: {office}. "
                   f"Lutfen nufus cuzdaninizi ve gerekli belgeleri yaninizda getirin.")
    else:
        if language == "en":
            msg = (f"{first_name}, I wasn't able to book an appointment right now. "
                   f"Please try again later or contact us at ALO 181.")
        else:
            msg = (f"{first_name}, su anda randevu olusturamadim. "
                   f"Lutfen daha sonra tekrar deneyin veya ALO 181'i arayin.")

    logger.info(f"Appointment booking | citizen_id={citizen_id} | success={bool(result)}")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "appointment_book"),
    }
