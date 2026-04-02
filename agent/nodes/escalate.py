"""
Escalation node.

Returns an AIMessage with a transfer_to_number system tool call in
OpenAI function call format. ElevenLabs Custom LLM proxy forwards this
to ElevenLabs, which executes the transfer as a platform-native system tool.

The message content is also set so TTS speaks a verbal confirmation
before the transfer triggers.
"""

import json
import uuid

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

# Demo transfer number — replace with real operator line in production
_TRANSFER_NUMBER = "+905001234567"


def escalate(state: AgentState) -> dict:
    """Escalate to human operator via ElevenLabs transfer_to_number system tool.

    Returns an AIMessage with:
    - content: verbal confirmation (spoken by TTS before transfer)
    - additional_kwargs.tool_calls: OpenAI function call for transfer_to_number
    """
    language = state.get("language", "tr")

    if language == "en":
        reason = "Citizen requested assistance from a human operator"
        client_message = ("I'm transferring you to a human operator who can assist you further. "
                          "Please hold for a moment.")
        agent_message = "Citizen requesting human assistance via voice agent."
    else:
        reason = "Vatandas operator yardimi talep etti"
        client_message = ("Sizi daha detayli yardimci olabilecek bir operatore bagliyorum. "
                          "Lutfen bir an bekleyin.")
        agent_message = "Vatandas sesli asistan uzerinden operator yardimi talep ediyor."

    logger.info("Escalation triggered — returning transfer_to_number tool call")

    # OpenAI function call format — ElevenLabs executes this as a system tool
    # All four parameters required by ElevenLabs: reason, transfer_number,
    # client_message (read to caller while waiting), agent_message (briefing for operator)
    tool_call = {
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {
            "name": "transfer_to_number",
            "arguments": json.dumps({
                "reason": reason,
                "transfer_number": _TRANSFER_NUMBER,
                "client_message": client_message,
                "agent_message": agent_message,
            }),
        },
    }

    msg = AIMessage(
        content=client_message,
        additional_kwargs={"tool_calls": [tool_call]},
    )

    return {
        "messages": [msg],
        "completed_intents": mark_completed(state, "escalate"),
    }
