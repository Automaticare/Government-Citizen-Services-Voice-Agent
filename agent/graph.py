"""
LangGraph agent workflow for citizen services.

Graph structure:
  START → entry_router → [service nodes] → END
                 ↓
         (workflow_node set → direct to node)
         (workflow_node not set → intent_classify → service_router → node)

ElevenLabs Workflow handles: routing between conversation phases (auth, service selection).
LangGraph handles: node-level intelligence (tool chaining, RAG, API orchestration).
"""

from typing import Literal

from dotenv import load_dotenv
load_dotenv()

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
from agent.nodes.appointment_list import appointment_list
from agent.nodes.appointment_cancel import appointment_cancel
from agent.nodes.document_status import document_status


# --- Valid workflow node names (from ElevenLabs [NODE:xxx] markers) ---
WORKFLOW_NODES = {
    "service_router",
    "status_check",
    "appointment_book",
    "appointment_list",
    "appointment_cancel",
    "document_request",
    "document_status",
    "faq_answer",
    "complaint",
    "escalate",
}


def entry_router(state: AgentState) -> str:
    """First routing decision: use workflow node if set, otherwise intent_classify.

    When ElevenLabs workflow sets [NODE:xxx] in system prompt, we skip
    intent classification and route directly to the target node.
    This lets ElevenLabs handle high-level routing while LangGraph
    handles node-level intelligence.

    Special case: service_router means "figure out what the user wants"
    — route to intent_classify so LLM can determine from conversation history.
    """
    workflow_node = state.get("workflow_node")
    if workflow_node and workflow_node in WORKFLOW_NODES and workflow_node != "service_router":
        return workflow_node
    return "intent_classify"


def route_by_intent(state: AgentState) -> str:
    """Conditional edge: route to service node based on classified intent.

    Only used when workflow_node is not set (fallback / direct API calls).
    """
    intent = state.get("current_intent", "unknown")

    routing = {
        "status_check": "status_check",
        "appointment_book": "appointment_book",
        "appointment_list": "appointment_list",
        "appointment_cancel": "appointment_cancel",
        "document_request": "document_request",
        "document_status": "document_status",
        "faq": "faq_answer",
        "fee_inquiry": "faq_answer",
        "complaint": "complaint",
        "escalate": "escalate",
        "unknown": "faq_answer",
    }

    return routing.get(intent, "faq_answer")


def build_graph(checkpointer=None):
    """Build and return the compiled LangGraph agent.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                      Pass MemorySaver() for demo, PostgresSaver for production.
    """
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
    builder.add_node("appointment_list", appointment_list)
    builder.add_node("appointment_cancel", appointment_cancel)
    builder.add_node("document_status", document_status)

    # --- Entry point: workflow node or intent classify ---
    builder.add_conditional_edges(START, entry_router)

    # --- Intent classify fallback path ---
    builder.add_edge("intent_classify", "service_router")
    builder.add_conditional_edges("service_router", route_by_intent)

    # --- All service nodes end after completing ---
    for node in ["status_check", "appointment_book", "appointment_list",
                 "appointment_cancel", "document_request", "document_status",
                 "faq_answer", "complaint", "escalate"]:
        builder.add_edge(node, END)

    return builder.compile(checkpointer=checkpointer)


# Default graph without checkpointer (for testing / direct invocation)
graph = build_graph()
