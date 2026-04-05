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

API_BASE = "http://localhost:8080"


def _book_via_api(citizen_id: int, service_type: str, preferred_date: str | None) -> tuple[dict | None, str | None]:
    """Call government API to book appointment.

    Returns (result_dict, error_message). On success error is None.
    """
    try:
        payload = {
            "citizen_id": citizen_id,
            "service_type": service_type,
            "preferred_date": preferred_date or "2026-04-07",
        }
        r = httpx.post(f"{API_BASE}/appointments", json=payload, timeout=5.0)
        if r.status_code == 200:
            return r.json(), None

        # Parse API error message for user-friendly feedback
        error_detail = r.json().get("detail", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        logger.warning(f"Appointment API returned {r.status_code}: {error_detail}")
        return None, error_detail

    except httpx.RequestError as e:
        logger.error(f"Appointment API unreachable: {e}")
        return None, "service_unavailable"


def appointment_book(state: AgentState) -> dict:
    """Book an appointment for the citizen via government API."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I can help you book an appointment. First, I need to verify your identity. "
               "Could you please tell me the last four digits of your TC Kimlik number?"
               if language == "en" else
               "Randevu almaniza yardimci olabilirim. Oncelikle kimliginizi dogrulamam gerekiyor. "
               "TC Kimlik numaranizin son dort hanesini soyler misiniz?")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": mark_completed(state, "appointment_book"),
        }

    first_name = profile.get("first_name", "")
    citizen_id = profile.get("citizen_id")

    # Call government API
    result, error = _book_via_api(citizen_id, "general", None)

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
    elif error and "past" in error.lower():
        msg = (f"{first_name}, past dates cannot be selected for appointments. Please choose a future date."
               if language == "en" else
               f"{first_name}, gecmis bir tarih icin randevu alinamaz. Lutfen ileri bir tarih secin.")
    elif error and "already have" in error.lower():
        msg = (f"{first_name}, {error}"
               if language == "en" else
               f"{first_name}, bu hizmet icin ayni tarihte zaten bir randevunuz var.")
    elif error and "no available" in error.lower():
        msg = (f"{first_name}, there are no available slots for that date. Would you like to try a different date?"
               if language == "en" else
               f"{first_name}, bu tarih icin musait randevu yok. Baska bir tarih denemek ister misiniz?")
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
