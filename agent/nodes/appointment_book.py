"""
Appointment booking node.

Validates availability and books appointment via API.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def appointment_book(state: AgentState) -> dict:
    """Book an appointment for the citizen.

    TODO: Full implementation with API calls in commit 2.
    """
    intent = state.get("current_intent", "appointment_book")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Randevu oluşturuyorum...")],
        "completed_intents": completed,
    }
