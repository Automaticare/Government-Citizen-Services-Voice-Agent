"""
Escalation node.

Returns a system tool call (transfer_to_number) in OpenAI format
for ElevenLabs to execute. LangGraph doesn't transfer the call
itself — it tells ElevenLabs to do it.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def escalate(state: AgentState) -> dict:
    """Escalate to human operator via ElevenLabs system tool.

    TODO: Return proper OpenAI function call format in commit 2.
    """
    intent = state.get("current_intent", "escalate")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Sizi bir operatöre bağlıyorum, lütfen bekleyin.")],
        "completed_intents": completed,
    }
