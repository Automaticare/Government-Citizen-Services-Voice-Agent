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


def _normalize_turkish(text: str) -> str:
    """Normalize Turkish special characters to ASCII for keyword matching."""
    tr_map = str.maketrans("ğüşıöçĞÜŞİÖÇ", "gusioçGUSIOC")
    return text.translate(tr_map).lower()


def _pre_classify_edge_case(text: str) -> Intent | None:
    """Catch edge cases that should always route to faq (for edge case handling).

    These are messages that LLM might misclassify — e.g. "arkadaşımın başvurusu"
    goes to status_check but should be caught as a third-party edge case in faq.
    """
    lower = _normalize_turkish(text)

    # Third-party inquiry — must go to faq for edge case handling, not status_check
    third_party = ["arkadasimin", "esimin", "annemin", "babamin", "kardesimin",
                    "baskasinin", "onun basvurusu", "my friend", "someone else"]
    if any(kw in lower for kw in third_party):
        logger.info(f"Pre-classify edge case: third_party -> faq")
        return "faq"

    # Previous call reference — we can't access prior calls
    previous = ["gecen aradigimda", "daha once aramistim", "onceki gorusmemde",
                 "gecen sefer", "last time i called", "previous call"]
    if any(kw in lower for kw in previous):
        logger.info(f"Pre-classify edge case: previous_call -> faq")
        return "faq"

    # Anger/profanity — route to escalate immediately
    anger = ["siktir", "amina", "orospu", "salak", "aptal", "sikeyim",
             "fuck", "shit", "bullshit", "asshole"]
    if any(kw in lower for kw in anger):
        logger.info(f"Pre-classify edge case: anger -> escalate")
        return "escalate"

    return None


def intent_classify(state: AgentState) -> dict:
    """Classify the caller's intent from conversation context."""
    messages = state.get("messages", [])
    if not messages:
        return {"current_intent": "unknown"}

    latest_text = messages[-1].content if hasattr(messages[-1], "content") else ""

    # Check edge cases before LLM — some messages get misclassified
    edge_intent = _pre_classify_edge_case(latest_text)
    if edge_intent:
        return {"current_intent": edge_intent}

    response = _llm.invoke([
        SystemMessage(content=INTENT_SYSTEM_PROMPT),
        messages[-1],
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
