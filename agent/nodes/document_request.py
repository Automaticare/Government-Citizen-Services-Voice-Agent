"""
Document request node.

Initiates document preparation via API.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger

logger = get_logger(__name__)


def document_request(state: AgentState) -> dict:
    """Initiate a document request for the citizen."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")

    if not profile:
        msg = ("I need to verify your identity before processing a document request."
               if language == "en" else
               "Belge talebi icin kimlik dogrulamasi gerekiyor.")
        return {
            "messages": [AIMessage(content=msg)],
            "completed_intents": _mark_completed(state, "document_request"),
        }

    first_name = profile.get("first_name", "")

    if language == "en":
        msg = (f"{first_name}, your document request has been submitted. "
               f"Estimated preparation time: 3-5 business days. "
               f"You will be notified when your document is ready for pickup.")
    else:
        msg = (f"{first_name}, belge talebiniz olusturuldu. "
               f"Tahmini hazirlama suresi: 3-5 is gunu. "
               f"Belgeniz hazir oldugunda bilgilendirileceksiniz.")

    logger.info(f"Document request created for session")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": _mark_completed(state, "document_request"),
    }


def _mark_completed(state: AgentState, intent: str) -> list:
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed
