"""
FAQ answer node.

Uses LLM to answer general questions. In ISSUE-10, this will be
backed by a Pinecone RAG pipeline. For now, uses LLM with context
from the system prompt.
"""

from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from agent.state import AgentState
from agent.prompts.loader import load_system_prompt, get_latest_version
from agent.logging_config import get_logger
from agent.nodes.utils import mark_completed

logger = get_logger(__name__)

_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)


def faq_answer(state: AgentState) -> dict:
    """Answer a general question using LLM + system prompt context."""
    language = state.get("language", "tr")
    version = state.get("prompt_version", get_latest_version())
    messages = state.get("messages", [])

    system_prompt = load_system_prompt(language=language, version=version)

    response = _llm.invoke([
        SystemMessage(content=system_prompt),
        *messages,
    ])

    logger.info(f"FAQ answered | language={language} | prompt_version={version}")

    return {
        "messages": [response],
        "completed_intents": mark_completed(state, state.get("current_intent", "faq")),
    }
