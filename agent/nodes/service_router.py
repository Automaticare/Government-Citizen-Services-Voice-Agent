"""
Service router node.

When reached via workflow, uses LLM to understand user's request
from conversation history and respond naturally. The actual routing
to specific service nodes is handled by ElevenLabs workflow edges.

LangGraph's role here: understand context and respond.
Workflow's role: route to the correct next node based on LLM conditions.
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.logging_config import get_logger

logger = get_logger(__name__)

_llm = ChatOpenAI(model="gpt-4o", temperature=0.7)

ROUTER_PROMPT = """You are Umut, a government citizen services voice assistant.
The citizen has been authenticated. Respond naturally to their request.
Your response will be READ ALOUD — keep it short, natural, no formatting.

If the citizen has already stated what they need (in conversation history),
acknowledge it and say you're helping with that.
If not, ask how you can help them.

Respond in {language_name}."""


def service_router(state: AgentState) -> dict:
    """Respond to user's request using conversation context."""
    messages = state.get("messages", [])
    language = state.get("language", "tr")
    language_name = "English" if language == "en" else "Turkish"

    conv_messages = [m for m in messages if not isinstance(m, SystemMessage)]

    response = _llm.invoke([
        SystemMessage(content=ROUTER_PROMPT.format(language_name=language_name)),
        *conv_messages,
    ])

    logger.info(f"Service router | response generated from conversation context")

    return {"messages": [response]}
