"""
Intent classification node.

Uses LLM to classify the caller's intent from conversation context.
Returns one of the supported intent types, including edge cases.
"""

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState, Intent
from agent.logging_config import get_logger

logger = get_logger(__name__)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a government citizen services voice agent.
Analyze the user's latest message and classify their intent into exactly ONE of these categories:

- status_check: User wants to check their own application status
- appointment_book: User wants to book a NEW appointment
- appointment_list: User wants to VIEW or LIST their existing appointments
- appointment_cancel: User wants to CANCEL an existing appointment
- document_request: User wants to request a NEW official document
- document_status: User wants to check the status of an existing document request
- faq: User has a general question about services, requirements, procedures, OR any of the following edge cases:
  - User refuses to provide identity ("kimliğimi vermek istemiyorum", "I don't want to give my ID")
  - User asks about someone else's application ("arkadaşımın başvurusu", "my friend's application")
  - User provides only partial ID information ("sonu 901 ile bitiyor", "last digits are 901")
  - User asks if you are a robot/AI ("sen robot musun?", "are you a real person?")
  - User references a previous call ("geçen aradığımda", "last time I called")
  - User asks what you can do ("ne yapabilirsin?", "what can you help with?")
- fee_inquiry: User asks about fees, costs, or payment methods
- complaint: User wants to file a complaint or give negative feedback about a service experience
- escalate: User explicitly wants to speak with a human operator, OR user is angry/abusive/using profanity

Important rules:
- If the user asks about SOMEONE ELSE's application (friend, spouse, parent), classify as "faq" NOT "status_check"
- If the user mentions a PREVIOUS CALL or prior conversation, classify as "faq" NOT "complaint"
- If the user is angry or using ACTUAL profanity/swear words, classify as "escalate"
- If the user simply changes topic ("bırak onu, şikayet etmek istiyorum"), classify based on the NEW topic, not frustration
- Topic change phrases like "bırak", "geç onu", "tamam onu boşver" are NOT anger — they just mean the user wants to move on
- If unclear, respond with "faq"

Respond with ONLY the intent name, nothing else."""

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def intent_classify(state: AgentState) -> dict:
    """Classify the caller's intent from conversation context."""
    messages = state.get("messages", [])
    if not messages:
        return {"current_intent": "unknown"}

    # Send last 4 messages for context (not just last message).
    # This helps the LLM understand follow-up responses like "pasaport"
    # after the agent listed multiple applications.
    # System messages are filtered out to avoid confusing the classifier.
    conv_messages = [m for m in messages if not isinstance(m, SystemMessage)]
    context = conv_messages[-4:] if len(conv_messages) > 4 else conv_messages
    response = _llm.invoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        *context,
    ])

    raw_intent = response.content.strip().lower()

    valid_intents: list[Intent] = [
        "status_check", "appointment_book", "appointment_list",
        "appointment_cancel", "document_request", "document_status",
        "faq", "fee_inquiry", "complaint", "escalate",
    ]

    intent: Intent = raw_intent if raw_intent in valid_intents else "faq"
    logger.info(f"Intent classified: {intent} (raw: {raw_intent})")

    return {"current_intent": intent}
