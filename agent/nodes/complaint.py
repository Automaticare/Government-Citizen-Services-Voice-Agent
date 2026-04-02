"""
Complaint recording node.

Records citizen complaint via API.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def complaint(state: AgentState) -> dict:
    """Record a citizen complaint.

    TODO: Full implementation with API calls in commit 2.
    """
    intent = state.get("current_intent", "complaint")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Şikayetinizi kayıt altına alıyorum...")],
        "completed_intents": completed,
    }
