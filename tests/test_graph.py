"""
Tests for LangGraph agent workflow.

Tests each node in isolation and the full graph flow.
Covers intent classification, tool chaining, multi-intent,
and Custom LLM proxy SSE output.
"""

import json
import os

import pytest
from dotenv import load_dotenv
load_dotenv()

from langchain_core.messages import HumanMessage, AIMessage
from agent.state import AgentState


# --- Helpers ---

def make_state(**overrides) -> AgentState:
    """Create a minimal valid AgentState with overrides."""
    defaults = {
        "messages": [HumanMessage(content="test")],
        "auth_status": "unauthenticated",
        "citizen_profile": None,
        "current_intent": "unknown",
        "completed_intents": [],
        "prompt_version": "v1.0",
        "language": "tr",
    }
    defaults.update(overrides)
    return defaults


AUTHENTICATED_PROFILE = {
    "first_name": "Ahmet",
    "last_name_initial": "Y***",
    "application_ref": "2024-TR-0001",
    "application_status": "in_review",
    "language_preference": "tr",
}


# --- Node isolation tests ---

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
class TestIntentClassify:
    """Test intent classification node in isolation."""

    def test_status_check_intent(self):
        from agent.nodes.intent_classify import intent_classify
        state = make_state(messages=[HumanMessage(content="Basvurumun durumunu ogrenmek istiyorum")])
        result = intent_classify(state)
        assert result["current_intent"] == "status_check"

    def test_appointment_intent(self):
        from agent.nodes.intent_classify import intent_classify
        state = make_state(messages=[HumanMessage(content="Randevu almak istiyorum")])
        result = intent_classify(state)
        assert result["current_intent"] == "appointment_book"

    def test_escalate_intent(self):
        from agent.nodes.intent_classify import intent_classify
        state = make_state(messages=[HumanMessage(content="Operator ile gorusmek istiyorum")])
        result = intent_classify(state)
        assert result["current_intent"] == "escalate"

    def test_complaint_intent(self):
        from agent.nodes.intent_classify import intent_classify
        state = make_state(messages=[HumanMessage(content="Sikayet etmek istiyorum, 2 saat bekledim")])
        result = intent_classify(state)
        assert result["current_intent"] == "complaint"

    def test_faq_intent(self):
        from agent.nodes.intent_classify import intent_classify
        state = make_state(messages=[HumanMessage(content="Calisma saatleri nedir?")])
        result = intent_classify(state)
        assert result["current_intent"] == "faq"


class TestStatusCheck:
    """Test status check node with deterministic tool chaining."""

    def test_additional_docs_chains_to_docs_info(self):
        from agent.nodes.status_check import status_check
        state = make_state(
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "additional_docs_needed"},
        )
        result = status_check(state)
        last_msg = result["messages"][-1].content.lower()
        assert "belge" in last_msg or "nufus" in last_msg
        assert "status_check" in result["completed_intents"]

    def test_rejected_offers_appeal_guidance(self):
        from agent.nodes.status_check import status_check
        state = make_state(
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "rejected"},
        )
        result = status_check(state)
        last_msg = result["messages"][-1].content.lower()
        assert "itiraz" in last_msg or "appeal" in last_msg

    def test_approved_status(self):
        from agent.nodes.status_check import status_check
        state = make_state(
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "approved"},
        )
        result = status_check(state)
        last_msg = result["messages"][-1].content.lower()
        assert "onay" in last_msg or "approved" in last_msg

    def test_in_review_status(self):
        from agent.nodes.status_check import status_check
        state = make_state(
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "in_review"},
        )
        result = status_check(state)
        last_msg = result["messages"][-1].content.lower()
        assert "inceleme" in last_msg or "review" in last_msg

    def test_unauthenticated_asks_for_auth(self):
        from agent.nodes.status_check import status_check
        state = make_state(auth_status="unauthenticated", citizen_profile=None)
        result = status_check(state)
        last_msg = result["messages"][-1].content.lower()
        assert "kimlik" in last_msg or "verify" in last_msg


class TestAppointmentBook:
    """Test appointment booking node."""

    def test_authenticated_books_slot(self):
        from agent.nodes.appointment_book import appointment_book
        state = make_state(
            auth_status="authenticated",
            citizen_profile=AUTHENTICATED_PROFILE,
        )
        result = appointment_book(state)
        last_msg = result["messages"][-1].content.lower()
        assert "randevu" in last_msg or "appointment" in last_msg
        assert "appointment_book" in result["completed_intents"]

    def test_unauthenticated_asks_for_auth(self):
        from agent.nodes.appointment_book import appointment_book
        state = make_state(auth_status="unauthenticated", citizen_profile=None)
        result = appointment_book(state)
        last_msg = result["messages"][-1].content.lower()
        assert "kimlik" in last_msg or "verify" in last_msg


class TestEscalate:
    """Test escalation node."""

    def test_returns_transfer_message_tr(self):
        from agent.nodes.escalate import escalate
        state = make_state(language="tr")
        result = escalate(state)
        last_msg = result["messages"][-1].content.lower()
        assert "operator" in last_msg or "bagliyorum" in last_msg

    def test_returns_transfer_message_en(self):
        from agent.nodes.escalate import escalate
        state = make_state(language="en")
        result = escalate(state)
        last_msg = result["messages"][-1].content.lower()
        assert "transfer" in last_msg or "operator" in last_msg


class TestComplaint:
    """Test complaint node."""

    def test_records_complaint(self):
        from agent.nodes.complaint import complaint
        state = make_state()
        result = complaint(state)
        assert "complaint" in result["completed_intents"]


class TestDocumentRequest:
    """Test document request node."""

    def test_authenticated_creates_request(self):
        from agent.nodes.document_request import document_request
        state = make_state(
            auth_status="authenticated",
            citizen_profile=AUTHENTICATED_PROFILE,
        )
        result = document_request(state)
        last_msg = result["messages"][-1].content.lower()
        assert "belge" in last_msg or "document" in last_msg


# --- Graph routing tests ---

class TestGraphRouting:
    """Test graph conditional edge routing."""

    def test_route_by_intent(self):
        from agent.graph import route_by_intent
        assert route_by_intent({"current_intent": "status_check"}) == "status_check"
        assert route_by_intent({"current_intent": "appointment_book"}) == "appointment_book"
        assert route_by_intent({"current_intent": "escalate"}) == "escalate"
        assert route_by_intent({"current_intent": "faq"}) == "faq_answer"
        assert route_by_intent({"current_intent": "fee_inquiry"}) == "faq_answer"
        assert route_by_intent({"current_intent": "unknown"}) == "faq_answer"

    def test_check_pending_intents(self):
        from agent.graph import check_pending_intents
        state = make_state(completed_intents=["status_check"], current_intent="status_check")
        assert check_pending_intents(state) == "__end__"


# --- Full graph flow tests ---

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
class TestFullGraphFlow:
    """Test end-to-end graph execution."""

    def test_status_check_flow(self):
        from agent.graph import graph
        result = graph.invoke(make_state(
            messages=[HumanMessage(content="Basvuru durumumu ogrenmek istiyorum")],
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "in_review"},
        ))
        assert result["current_intent"] == "status_check"
        assert "status_check" in result["completed_intents"]

    def test_tool_chaining_additional_docs(self):
        from agent.graph import graph
        result = graph.invoke(make_state(
            messages=[HumanMessage(content="Basvuru durumumu ogrenmek istiyorum")],
            auth_status="authenticated",
            citizen_profile={**AUTHENTICATED_PROFILE, "application_status": "additional_docs_needed"},
        ))
        last_msg = result["messages"][-1].content.lower()
        assert "belge" in last_msg or "nufus" in last_msg

    def test_escalation_flow(self):
        from agent.graph import graph
        result = graph.invoke(make_state(
            messages=[HumanMessage(content="I want to speak with a human")],
            language="en",
        ))
        assert result["current_intent"] == "escalate"


# --- Custom LLM proxy SSE tests ---

class TestCustomLLMProxy:
    """Test the SSE proxy endpoint."""

    @pytest.fixture(autouse=True)
    def setup(self):
        from fastapi.testclient import TestClient
        from agent.server import app
        self.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        assert r.json()["status"] == "ok"

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    def test_sse_format(self):
        r = self.client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "Calisma saatleri nedir?"}],
            "stream": True,
            "elevenlabs_extra_body": {"conversation_id": "test-sse-1"},
        })
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]

        lines = [l for l in r.text.split("\n") if l.startswith("data:")]
        assert lines[-1] == "data: [DONE]"

        # First data chunk should have role
        first_data = json.loads(lines[0].replace("data: ", ""))
        assert first_data["choices"][0]["delta"]["role"] == "assistant"

    @pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
    def test_sse_with_auth_context(self):
        r = self.client.post("/v1/chat/completions", json={
            "messages": [{"role": "user", "content": "Basvuru durumumu sor"}],
            "stream": True,
            "elevenlabs_extra_body": {
                "conversation_id": "test-sse-2",
                "auth_status": "authenticated",
                "citizen_profile": {
                    "first_name": "Fatma",
                    "last_name_initial": "K***",
                    "application_ref": "2024-TR-0002",
                    "application_status": "approved",
                    "language_preference": "tr",
                },
            },
        })
        # Extract all content from SSE chunks
        content_parts = []
        for line in r.text.split("\n"):
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            data = json.loads(line.replace("data: ", ""))
            c = data["choices"][0]["delta"].get("content", "")
            if c:
                content_parts.append(c)

        full_response = "".join(content_parts).lower()
        assert "fatma" in full_response or "onay" in full_response or "approved" in full_response
