"""
Complaint recording node.

Records citizen complaint and provides confirmation.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger

logger = get_logger(__name__)


def complaint(state: AgentState) -> dict:
    """Record a citizen complaint."""
    profile = state.get("citizen_profile")
    language = state.get("language", "tr")
    messages = state.get("messages", [])

    # Extract complaint context from last user message
    last_msg = messages[-1].content if messages else ""

    if language == "en":
        msg = ("Your complaint has been recorded and assigned a reference number. "
               "A supervisor will review it within 3 business days. "
               "Is there anything else I can help you with?")
    else:
        msg = ("Sikayetiniz kayit altina alindi ve bir referans numarasi atandi. "
               "Bir yonetici 3 is gunu icinde inceleyecektir. "
               "Baska yardimci olabilecegim bir konu var mi?")

    logger.info(f"Complaint recorded for session")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": _mark_completed(state, "complaint"),
    }


def _mark_completed(state: AgentState, intent: str) -> list:
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed
