"""
Auth credential collection node.

Collects identity verification data step by step:
1. TC Kimlik last 4 digits
2. Date of birth
3. Father's name first letter

After all 3 are collected, asks for confirmation before the
ElevenLabs workflow dispatch tool triggers authentication.

This node works with ElevenLabs' stateless architecture — it reads
the full conversation history (sent by ElevenLabs each turn) to
determine which step we're on. No server-side state needed.
"""

from langchain_core.messages import AIMessage, HumanMessage

from agent.state import AgentState
from agent.logging_config import get_logger

logger = get_logger(__name__)

# Auth collection steps — each step checks if we already have the data
# by looking at conversation history patterns
STEPS = [
    {
        "field": "tc_last4",
        "ask_tr": "TC Kimlik numaranizin son dort hanesini soyler misiniz?",
        "ask_en": "Could you please tell me the last four digits of your TC Kimlik number?",
    },
    {
        "field": "dob",
        "ask_tr": "Dogum tarihinizi gun, ay ve yil olarak soyler misiniz?",
        "ask_en": "Could you please tell me your date of birth?",
    },
    {
        "field": "father_initial",
        "ask_tr": "Baba adinizin ilk harfini soyler misiniz?",
        "ask_en": "Could you please tell me the first letter of your father's name?",
    },
]

# Phrases that indicate the assistant was asking for auth credentials
AUTH_ASK_MARKERS_TR = [
    "son dort hane",
    "dogum tarihi",
    "baba adi",
]

AUTH_ASK_MARKERS_EN = [
    "last four digits",
    "date of birth",
    "father's name",
]


def _count_collected_fields(messages: list) -> int:
    """Count how many auth fields have been collected by looking at conversation history.

    Pattern: each collected field = one assistant question + one user answer.
    We count the number of auth-related assistant messages that have a
    subsequent user response.
    """
    collected = 0
    for i, msg in enumerate(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = (msg.content or "").lower()

        is_auth_ask = any(marker in content for marker in AUTH_ASK_MARKERS_TR + AUTH_ASK_MARKERS_EN)
        if not is_auth_ask:
            continue

        # Check if there's a user response after this ask
        has_response = False
        for j in range(i + 1, len(messages)):
            if isinstance(messages[j], HumanMessage):
                has_response = True
                break
            if isinstance(messages[j], AIMessage):
                break  # Another assistant message before user response

        if has_response:
            collected += 1

    return min(collected, len(STEPS))


def is_auth_collecting(messages: list) -> bool:
    """Check if we're in the middle of collecting auth credentials.

    Returns True if the last assistant message was asking for auth data.
    Used by intent_classify to skip re-classification during auth flow.
    """
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = (msg.content or "").lower()
            return any(
                marker in content
                for marker in AUTH_ASK_MARKERS_TR + AUTH_ASK_MARKERS_EN
            )
        if isinstance(msg, HumanMessage):
            # User message is the latest — check the assistant message before it
            continue
    return False


def auth_collect(state: AgentState) -> dict:
    """Collect auth credentials step by step from conversation history."""
    language = state.get("language", "tr")
    messages = state.get("messages", [])

    collected = _count_collected_fields(messages)

    logger.info(f"Auth collect | fields_collected={collected}/{len(STEPS)}")

    if collected < len(STEPS):
        # Ask for the next field
        step = STEPS[collected]
        msg = step["ask_en"] if language == "en" else step["ask_tr"]

        # If this is the first question, add context
        if collected == 0:
            prefix_tr = "Kimliginizi dogrulamam gerekiyor. "
            prefix_en = "I need to verify your identity. "
            msg = (prefix_en + msg) if language == "en" else (prefix_tr + msg)

        return {"messages": [AIMessage(content=msg)]}

    # All 3 fields collected — ask for confirmation
    # Extract the user responses for each field from conversation history
    user_responses = []
    auth_ask_count = 0
    for i, msg in enumerate(messages):
        if not isinstance(msg, AIMessage):
            continue
        content = (msg.content or "").lower()
        is_auth_ask = any(marker in content for marker in AUTH_ASK_MARKERS_TR + AUTH_ASK_MARKERS_EN)
        if not is_auth_ask:
            continue

        # Find the next user response
        for j in range(i + 1, len(messages)):
            if isinstance(messages[j], HumanMessage):
                user_responses.append(messages[j].content.strip())
                break
            if isinstance(messages[j], AIMessage):
                break

        auth_ask_count += 1
        if auth_ask_count >= len(STEPS):
            break

    if len(user_responses) >= 3:
        tc_last4 = user_responses[0]
        dob = user_responses[1]
        father = user_responses[2]

        if language == "en":
            msg = (f"Let me confirm: last four digits {tc_last4}, "
                   f"date of birth {dob}, "
                   f"father's name initial {father}. Is that correct?")
        else:
            msg = (f"Dogrulayayim: son dort hane {tc_last4}, "
                   f"dogum tarihi {dob}, "
                   f"baba adi ilk harf {father}. Dogru mu?")
    else:
        # Fallback — shouldn't happen but be safe
        msg = ("Bilgilerinizi dogrulayamadim. Lutfen tekrar deneyelim. "
               "TC Kimlik numaranizin son dort hanesini soyler misiniz?"
               if language != "en" else
               "I couldn't confirm your information. Let's try again. "
               "Could you please tell me the last four digits of your TC Kimlik number?")

    logger.info(f"Auth collect | confirmation requested | responses={user_responses}")
    return {"messages": [AIMessage(content=msg)]}
