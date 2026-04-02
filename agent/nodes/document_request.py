"""
Document request node.

Initiates document preparation via API.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def document_request(state: AgentState) -> dict:
    """Initiate a document request for the citizen.

    TODO: Full implementation with API calls in commit 2.
    """
    intent = state.get("current_intent", "document_request")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Belge talebinizi oluşturuyorum...")],
        "completed_intents": completed,
    }
