"""
Appointment cancellation node.

Cancels the most recent confirmed appointment for the citizen.
"""

import httpx
from langchain_core.messages import AIMessage

from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

API_BASE = "http://localhost:8080"


def _fetch_appointments(citizen_id: int) -> list[dict]:
    """Call government API for citizen's appointments."""
    try:
        r = httpx.get(f"{API_BASE}/appointments/{citizen_id}", timeout=5.0)
        if r.status_code == 200:
            return r.json()
        return []
    except httpx.RequestError as e:
        logger.error(f"Appointments API unreachable: {e}")
        return []


def _cancel_appointment(appointment_id: int) -> bool:
    """Call government API to cancel an appointment."""
    try:
        r = httpx.delete(f"{API_BASE}/appointments/{appointment_id}", timeout=5.0)
        return r.status_code == 200
    except httpx.RequestError as e:
        logger.error(f"Appointment cancel API unreachable: {e}")
        return False


def appointment_cancel(state: AgentState) -> dict:
    """Cancel the most recent confirmed appointment."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I need to verify your identity before cancelling an appointment."
               if language == "en" else
               "Randevu iptal etmek icin kimlik dogrulamasi gerekiyor.")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": mark_completed(state, "appointment_cancel"),
        }

    citizen_id = profile.get("citizen_id")
    first_name = profile.get("first_name", "")

    appointments = _fetch_appointments(citizen_id) if citizen_id else []
    confirmed = [a for a in appointments if a.get("status") == "confirmed"]

    if not confirmed:
        msg = (f"{first_name}, you have no confirmed appointments to cancel."
               if language == "en" else
               f"{first_name}, iptal edilebilecek onaylanmis bir randevunuz bulunmuyor.")
    elif len(confirmed) == 1:
        a = confirmed[0]
        success = _cancel_appointment(a["id"])
        if success:
            if language == "en":
                msg = (f"{first_name}, your {a['service_type']} appointment on "
                       f"{a['appointment_date']} at {a['appointment_time']} has been cancelled.")
            else:
                msg = (f"{first_name}, {a['appointment_date']} tarihli {a['service_type']} "
                       f"randevunuz iptal edilmistir.")
        else:
            msg = (f"{first_name}, I couldn't cancel your appointment right now. Please try again later."
                   if language == "en" else
                   f"{first_name}, randevunuzu su anda iptal edemedim. Lutfen daha sonra tekrar deneyin.")
    else:
        if language == "en":
            msg = f"{first_name}, you have {len(confirmed)} confirmed appointments. "
            for a in confirmed:
                msg += f"{a['service_type']} on {a['appointment_date']} at {a['appointment_time']}. "
            msg += "Which one would you like to cancel?"
        else:
            msg = f"{first_name}, {len(confirmed)} onaylanmis randevunuz var. "
            for a in confirmed:
                msg += f"{a['service_type']} icin {a['appointment_date']} saat {a['appointment_time']}. "
            msg += "Hangisini iptal etmek istersiniz?"

    logger.info(f"Appointment cancel | citizen={first_name} | confirmed={len(confirmed)}")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "appointment_cancel"),
    }
