"""
Escalation node.

Returns an AIMessage with transfer confirmation. In production with
Twilio/SIP, this would include a transfer_to_number system tool call.
In demo mode, returns text-only to avoid ElevenLabs retry loops
(platform retries when transfer can't execute without real phone line).

To enable real transfer, set ENABLE_PHONE_TRANSFER=true in .env and
configure a real operator number.
"""

import json
import os
import uuid

from langchain_core.messages import AIMessage
from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

# Demo transfer number — replace with real operator line in production
_TRANSFER_NUMBER = "+905001234567"
_ENABLE_TRANSFER = os.getenv("ENABLE_PHONE_TRANSFER", "false").lower() == "true"


def escalate(state: AgentState) -> dict:
    """Escalate to human operator.

    In production (ENABLE_PHONE_TRANSFER=true): returns transfer_to_number
    tool call for ElevenLabs to execute.
    In demo: returns text-only confirmation (avoids retry loop).
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

    if _ENABLE_TRANSFER:
        logger.info("Escalation triggered — returning transfer_to_number tool call")

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
    else:
        logger.info("Escalation triggered — demo mode (text-only, no phone transfer)")
        if language == "en":
            demo_msg = ("I would transfer you to a human operator now. "
                        "In production, this triggers a phone transfer via Twilio/SIP. "
                        "Is there anything else I can help you with?")
        else:
            demo_msg = ("Sizi bir operatore baglamam gerekiyor. "
                        "Gercek ortamda bu noktada telefon transferi gerceklesir. "
                        "Baska yardimci olabilecegim bir konu var mi?")
        msg = AIMessage(content=demo_msg)

    return {
        "messages": [msg],
        "completed_intents": mark_completed(state, "escalate"),
    }
