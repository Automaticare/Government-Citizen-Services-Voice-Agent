"""
LangGraph state schema for the citizen services agent.

Defines the typed state that flows through all graph nodes.
Uses TypedDict with reducers for message handling.
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


Intent = Literal[
    "status_check",
    "appointment_book",
    "document_request",
    "faq",
    "fee_inquiry",
    "complaint",
    "escalate",
    "auth_collect",
    "unknown",
]

AuthStatus = Literal["unauthenticated", "authenticated"]

ApplicationStatus = Literal[
    "pending",
    "in_review",
    "approved",
    "rejected",
    "additional_docs_needed",
]


class CitizenProfile(TypedDict, total=False):
    """Safe citizen profile — no raw PII."""
    citizen_id: int
    first_name: str
    last_name_initial: str
    application_ref: str
    application_status: ApplicationStatus
    language_preference: str


class AgentState(TypedDict):
    """Root state for the LangGraph agent.

    Flows through all nodes. Each node reads what it needs
    and returns only the keys it updates.
    """

    # Conversation
    messages: Annotated[list[AnyMessage], add_messages]

    # Authentication
    auth_status: AuthStatus
    citizen_profile: CitizenProfile | None

    # Intent routing
    current_intent: Intent
    completed_intents: list[Intent]

    # Metadata
    prompt_version: str
    language: str
