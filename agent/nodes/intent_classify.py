"""
Intent classification node.

Uses LLM to classify the caller's intent from conversation context.
Returns one of the supported intent types.
"""

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState, Intent
from agent.logging_config import get_logger

logger = get_logger(__name__)

INTENT_SYSTEM_PROMPT = """You are an intent classifier for a government citizen services agent.
Analyze the user's latest message and classify their intent into exactly ONE of these categories:

- status_check: User wants to check application status
- appointment_book: User wants to book, change, or cancel an appointment
- document_request: User wants to request an official document
- faq: User has a general question about services, requirements, or procedures
- fee_inquiry: User asks about fees, costs, or payment methods
- complaint: User wants to file a complaint or give negative feedback
- escalate: User explicitly wants to speak with a human operator

Respond with ONLY the intent name, nothing else. If unclear, respond with "faq"."""

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


def intent_classify(state: AgentState) -> dict:
    """Classify the caller's intent from conversation context."""
    messages = state.get("messages", [])
    if not messages:
        return {"current_intent": "unknown"}

    response = _llm.invoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        messages[-1],  # Latest user message
    ])

    raw_intent = response.content.strip().lower()

    # Validate against known intents
    valid_intents: list[Intent] = [
        "status_check", "appointment_book", "document_request",
        "faq", "fee_inquiry", "complaint", "escalate",
    ]

    intent: Intent = raw_intent if raw_intent in valid_intents else "faq"
    logger.info(f"Intent classified: {intent} (raw: {raw_intent})")

    return {"current_intent": intent}
