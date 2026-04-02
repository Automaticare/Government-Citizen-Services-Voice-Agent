"""
Escalation node.

Returns a message indicating human transfer. When connected to
ElevenLabs via Custom LLM (ISSUE-08), this will return an OpenAI
function call for the transfer_to_number system tool.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)


def escalate(state: AgentState) -> dict:
    """Escalate to human operator."""
    language = state.get("language", "tr")

    if language == "en":
        msg = ("I'm transferring you to a human operator who can assist you further. "
               "Please hold for a moment.")
    else:
        msg = ("Sizi daha detayli yardimci olabilecek bir operatore bagliyorum. "
               "Lutfen bir an bekleyin.")

    logger.info(f"Escalation triggered for session")

    return {
        "messages": [AIMessage(content=msg)],
        "completed_intents": mark_completed(state, "escalate"),
    }
