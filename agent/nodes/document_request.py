"""
Document request node.

Calls the government API to initiate document preparation.
Falls back to confirmation message if API is unavailable.
"""

import httpx
from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

API_BASE = "http://localhost:8080"


def _request_via_api(citizen_id: int, document_type: str) -> dict | None:
    """Call government API to request document."""
    try:
        payload = {
            "citizen_id": citizen_id,
            "document_type": document_type,
        }
        r = httpx.post(f"{API_BASE}/documents/request", json=payload, timeout=5.0)
        if r.status_code == 200:
            return r.json()
        logger.warning(f"Document API returned {r.status_code}: {r.text}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Document API unreachable: {e}")
        return None


def document_request(state: AgentState) -> dict:
    """Initiate a document request via government API."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I can help you with your document request. First, I need to verify your identity. "
               "Could you please tell me the last four digits of your TC Kimlik number?"
               if language == "en" else
               "Belge talebiniz icin yardimci olabilirim. Oncelikle kimliginizi dogrulamam gerekiyor. "
               "TC Kimlik numaranizin son dort hanesini soyler misiniz?")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": mark_completed(state, "document_request"),
        }

    first_name = profile.get("first_name", "")
    citizen_id = profile.get("citizen_id")

    # Call government API
    result = _request_via_api(citizen_id, "general")

    if result:
        ref = result.get("request_ref", "")
        days = result.get("estimated_days", 5)

        if language == "en":
            msg = (f"{first_name}, your document request has been submitted. "
                   f"Reference: {ref}. Estimated preparation: {days} business days. "
                   f"You will be notified when ready for pickup.")
        else:
            msg = (f"{first_name}, belge talebiniz olusturuldu. "
                   f"Referans: {ref}. Tahmini hazirlama suresi: {days} is gunu. "
                   f"Belgeniz hazir oldugunda bilgilendirileceksiniz.")
    else:
        if language == "en":
            msg = (f"{first_name}, I wasn't able to process your document request right now. "
                   f"Please try again later or contact us at ALO 181.")
        else:
            msg = (f"{first_name}, su anda belge talebinizi isleyemedim. "
                   f"Lutfen daha sonra tekrar deneyin veya ALO 181'i arayin.")

    logger.info(f"Document request | citizen_id={citizen_id} | success={bool(result)}")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "document_request"),
    }
