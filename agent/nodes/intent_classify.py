"""
Intent classification node.

Analyzes the latest user message and classifies it into one of
the supported intents. Uses LLM for natural language understanding.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def intent_classify(state: AgentState) -> dict:
    """Classify the caller's intent from conversation context.

    TODO: Full LLM-based classification in commit 2.
    """
    return {
        "current_intent": "unknown",
    }
