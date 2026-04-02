"""
FAQ answer node.

Retrieves answers from RAG knowledge base (Pinecone).
Handles general questions and fee inquiries.
"""

from langchain_core.messages import AIMessage
from agent.state import AgentState


def faq_answer(state: AgentState) -> dict:
    """Answer a general question using RAG pipeline.

    TODO: Full RAG implementation with Pinecone in ISSUE-10.
    """
    intent = state.get("current_intent", "faq")
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)

    return {
        "messages": [AIMessage(content="Sorunuzu araştırıyorum...")],
        "completed_intents": completed,
    }
