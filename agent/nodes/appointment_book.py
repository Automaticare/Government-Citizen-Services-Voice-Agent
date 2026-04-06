"""
Appointment booking node.

Asks the citizen which service type they need, checks for existing
appointments, then calls the government API to book.
Detects service type from conversation context when possible.
"""

import httpx
from langchain_core.messages import AIMessage, HumanMessage

from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

API_BASE = "http://localhost:8080"

SERVICE_TYPES = {
    "passport": {
        "tr": "pasaport",
        "en": "passport",
        "keywords_tr": ["pasaport"],
        "keywords_en": ["passport"],
    },
    "id_card": {
        "tr": "kimlik karti",
        "en": "ID card",
        "keywords_tr": ["kimlik", "kimlik karti", "nufus cuzdani"],
        "keywords_en": ["id card", "identity card", "id"],
    },
    "driver_license": {
        "tr": "ehliyet",
        "en": "driver's license",
        "keywords_tr": ["ehliyet", "surucu belgesi"],
        "keywords_en": ["driver", "license", "driving"],
    },
    "civil_registry": {
        "tr": "nufus islemi",
        "en": "civil registry",
        "keywords_tr": ["nufus", "dogum belgesi", "ikametgah", "evlilik"],
        "keywords_en": ["civil", "birth certificate", "residence", "marriage"],
    },
}


def _normalize(text: str) -> str:
    """Normalize Turkish characters for matching."""
    return (text.replace("ı", "i").replace("İ", "i")
            .replace("ş", "s").replace("Ş", "s")
            .replace("ğ", "g").replace("Ğ", "g")
            .replace("ü", "u").replace("Ü", "u")
            .replace("ö", "o").replace("Ö", "o")
            .replace("ç", "c").replace("Ç", "c")
            .lower())


def _detect_service_type(messages: list, language: str) -> str | None:
    """Try to detect service type from conversation history."""
    for msg in reversed(messages[-4:]):
        if not isinstance(msg, HumanMessage) and getattr(msg, "type", "") != "human":
            continue
        normalized = _normalize(msg.content)
        for svc_type, info in SERVICE_TYPES.items():
            key = "keywords_tr" if language != "en" else "keywords_en"
            for keyword in info[key]:
                if _normalize(keyword) in normalized:
                    return svc_type
    return None


def _fetch_appointments(citizen_id: int) -> list[dict]:
    """Call government API to get existing appointments."""
    try:
        r = httpx.get(f"{API_BASE}/appointments/{citizen_id}", timeout=5.0)
        if r.status_code == 200:
            return r.json()
        return []
    except httpx.RequestError:
        return []


def _book_via_api(citizen_id: int, service_type: str, preferred_date: str | None) -> tuple[dict | None, str | None]:
    """Call government API to book appointment."""
    try:
        payload = {
            "citizen_id": citizen_id,
            "service_type": service_type,
            "preferred_date": preferred_date or "2026-04-07",
        }
        r = httpx.post(f"{API_BASE}/appointments", json=payload, timeout=5.0)
        if r.status_code == 200:
            return r.json(), None

        error_detail = ""
        if r.headers.get("content-type", "").startswith("application/json"):
            detail = r.json().get("detail", "")
            error_detail = str(detail) if not isinstance(detail, str) else detail
        logger.warning(f"Appointment API returned {r.status_code}: {error_detail}")
        return None, error_detail

    except httpx.RequestError as e:
        logger.error(f"Appointment API unreachable: {e}")
        return None, "service_unavailable"


def appointment_book(state: AgentState) -> dict:
    """Book an appointment — detect service type, check conflicts, book."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")
    messages = state.get("messages", [])

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

    # Detect service type from conversation
    service_type = _detect_service_type(messages, language)

    if not service_type:
        if language == "en":
            msg = (f"{first_name}, which service would you like to book an appointment for? "
                   f"Passport, ID card, driver's license, or civil registry?")
        else:
            msg = (f"{first_name}, hangi hizmet icin randevu almak istiyorsunuz? "
                   f"Pasaport, kimlik karti, ehliyet veya nufus islemi?")
        return {"messages": [AIMessage(content=msg)]}

    svc_name = SERVICE_TYPES[service_type]["tr" if language != "en" else "en"]

    # Check for existing appointment conflict
    if citizen_id:
        existing = _fetch_appointments(citizen_id)
        conflicts = [a for a in existing
                     if a.get("service_type") == service_type and a.get("status") == "confirmed"]
        if conflicts:
            a = conflicts[0]
            if language == "en":
                msg = (f"{first_name}, you already have a confirmed {svc_name} appointment "
                       f"on {a['appointment_date']} at {a['appointment_time']}. "
                       f"Would you like to book for a different service?")
            else:
                msg = (f"{first_name}, {svc_name} icin zaten {a['appointment_date']} tarihinde "
                       f"saat {a['appointment_time']} icin onaylanmis bir randevunuz var. "
                       f"Baska bir hizmet icin randevu almak ister misiniz?")
            return {
                "messages": [AIMessage(content=msg)],
                "completed_intents": mark_completed(state, "appointment_book"),
            }

    # Book the appointment
    result, error = _book_via_api(citizen_id, service_type, None)

    if result:
        date = result.get("appointment_date", "")
        time = result.get("appointment_time", "")
        office = result.get("office", "")

        if language == "en":
            msg = (f"{first_name}, your {svc_name} appointment has been booked. "
                   f"Date: {date}, Time: {time}, Location: {office}. "
                   f"Please bring your ID card and any required documents.")
        else:
            msg = (f"{first_name}, {svc_name} randevunuz olusturuldu. "
                   f"Tarih: {date}, Saat: {time}, Yer: {office}. "
                   f"Lutfen nufus cuzdaninizi ve gerekli belgeleri yaninizda getirin.")
    elif error and "no available" in error.lower():
        if language == "en":
            msg = (f"{first_name}, there are no available {svc_name} slots. "
                   f"Would you like to try a different date?")
        else:
            msg = (f"{first_name}, {svc_name} icin musait randevu yok. "
                   f"Baska bir tarih denemek ister misiniz?")
    else:
        if language == "en":
            msg = (f"{first_name}, I wasn't able to book your {svc_name} appointment right now. "
                   f"Please try again later or contact us at ALO 181.")
        else:
            msg = (f"{first_name}, su anda {svc_name} randevunuzu olusturamadim. "
                   f"Lutfen daha sonra tekrar deneyin veya ALO 181'i arayin.")

    logger.info(f"Appointment booking | citizen_id={citizen_id} | type={service_type} | success={bool(result)}")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "appointment_book"),
    }
