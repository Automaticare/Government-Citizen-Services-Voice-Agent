"""
Status check node.

Queries the application status API and chains results:
- If "additional_docs_needed" → auto RAG query for required documents
- If "rejected" + < 30 days → offer appeal guidance
- Otherwise → return status directly
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def status_check(state: AgentState) -> dict:
    """Check application status with deterministic tool chaining.

    TODO: Full implementation with API calls + chaining in commit 2.
    """
    intent = state.get("current_intent", "status_check")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Başvurunuzun durumunu kontrol ediyorum...")],
        "completed_intents": completed,
    }
