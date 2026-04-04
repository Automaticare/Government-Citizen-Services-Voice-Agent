"""
Escalation node.

Generates an empathetic transfer message based on conversation context.
Uses LLM to adapt tone — frustrated caller gets acknowledgment,
normal request gets standard transfer message.

In production with Twilio (ENABLE_PHONE_TRANSFER=true), also returns
a transfer_to_number system tool call.
"""

import json
import os
import uuid

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

_TRANSFER_NUMBER = "+905001234567"
_ENABLE_TRANSFER = os.getenv("ENABLE_PHONE_TRANSFER", "false").lower() == "true"

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

ESCALATE_PROMPT = """You are a government citizen services assistant named Umut.
The caller needs to be transferred to a human operator.

Based on the caller's last message, generate a SHORT (1-2 sentences) transfer message.
Your response will be read aloud by text-to-speech.

Rules:
- If the caller is frustrated or angry: acknowledge their frustration first, then transfer
  Example: "Yasadiginiz sorunu anliyorum ve ozur dilerim. Sizi hemen bir yetkiliyle gorusturecegim."
- If the caller simply requested an operator: standard polite transfer
  Example: "Sizi bir operatore bagliyorum, lutfen bir an bekleyin."
- Never use formatting, bullet points, or numbers
- Respond in {language_name}
- Keep it warm and human — this person is about to talk to a real person"""


def escalate(state: AgentState) -> dict:
    """Escalate to human operator with context-aware empathetic message."""
    language = state.get("language", "tr")
    messages = state.get("messages", [])
    language_name = "English" if language == "en" else "Turkish"

    # Get last user message for context
    user_msg = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) or getattr(msg, "type", "") == "human":
            user_msg = msg.content
            break

    # LLM generates context-aware transfer message
    response = _llm.invoke([
        SystemMessage(content=ESCALATE_PROMPT.format(language_name=language_name)),
        HumanMessage(content=user_msg or "Operator ile gorusmek istiyorum"),
    ])
    client_message = response.content

    logger.info(f"Escalation triggered | transfer_enabled={_ENABLE_TRANSFER}")

    if _ENABLE_TRANSFER:
        if language == "en":
            agent_message = "Citizen requesting human assistance via voice agent."
        else:
            agent_message = "Vatandas sesli asistan uzerinden operator yardimi talep ediyor."

        tool_call = {
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": "transfer_to_number",
                "arguments": json.dumps({
                    "reason": "Citizen escalation",
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
        msg = AIMessage(content=client_message)

    return {
        "messages": [msg],
        "completed_intents": mark_completed(state, "escalate"),
    }
