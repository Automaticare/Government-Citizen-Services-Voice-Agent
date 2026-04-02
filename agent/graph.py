"""
LangGraph agent workflow for citizen services.

Graph structure:
  START → intent_classify → service_router → [service nodes] → END
                                                    ↓
                                          (back to intent_classify
                                           if pending intents remain)

ElevenLabs handles: voice (STT/TTS), language detection, auth gating.
LangGraph handles: intent routing, tool orchestration, RAG, business logic.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.state import AgentState, Intent
from agent.nodes.intent_classify import intent_classify
from agent.nodes.service_router import service_router
from agent.nodes.status_check import status_check
from agent.nodes.appointment_book import appointment_book
from agent.nodes.document_request import document_request
from agent.nodes.faq_answer import faq_answer
from agent.nodes.complaint import complaint
from agent.nodes.escalate import escalate


def route_by_intent(state: AgentState) -> str:
    """Conditional edge: route to service node based on classified intent."""
    intent = state.get("current_intent", "unknown")

    routing = {
        "status_check": "status_check",
        "appointment_book": "appointment_book",
        "document_request": "document_request",
        "faq": "faq_answer",
        "fee_inquiry": "faq_answer",  # Fee inquiries handled via RAG
        "complaint": "complaint",
        "escalate": "escalate",
        "unknown": "faq_answer",  # Fallback: try to answer from knowledge base
    }

    return routing.get(intent, "faq_answer")


def check_pending_intents(state: AgentState) -> Literal["intent_classify", "__end__"]:
    """After a service node completes, check if there are more intents to handle."""
    completed = set(state.get("completed_intents", []))
    current = state.get("current_intent")

    # If current intent was just completed and there might be more,
    # route back to intent_classify. The LLM will check conversation
    # context for any remaining requests.
    # For now, always end — multi-intent re-routing happens when
    # the LLM detects another intent in the next turn.
    return "__end__"


def build_graph() -> StateGraph:
    """Build and return the compiled LangGraph agent."""

    builder = StateGraph(AgentState)

    # --- Add nodes ---
    builder.add_node("intent_classify", intent_classify)
    builder.add_node("service_router", service_router)
    builder.add_node("status_check", status_check)
    builder.add_node("appointment_book", appointment_book)
    builder.add_node("document_request", document_request)
    builder.add_node("faq_answer", faq_answer)
    builder.add_node("complaint", complaint)
    builder.add_node("escalate", escalate)

    # --- Add edges ---
    # Entry: always start with intent classification
    builder.add_edge(START, "intent_classify")

    # Intent classify → service router
    builder.add_edge("intent_classify", "service_router")

    # Service router → conditional routing based on intent
    builder.add_conditional_edges("service_router", route_by_intent)

    # Each service node → check if more intents pending
    for node in ["status_check", "appointment_book", "document_request",
                 "faq_answer", "complaint", "escalate"]:
        builder.add_conditional_edges(node, check_pending_intents)

    return builder.compile()


# Singleton compiled graph
graph = build_graph()
