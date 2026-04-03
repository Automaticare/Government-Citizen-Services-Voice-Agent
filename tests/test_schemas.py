"""
Tests for tool schemas and input validation.
"""

import pytest
from agent.tools.schemas import (
    StatusCheckInput,
    AppointmentBookInput,
    DocumentRequestInput,
    ComplaintInput,
    KnowledgeBaseSearchInput,
    get_all_tool_schemas,
    get_system_tool_configs,
    TOOL_SCHEMAS,
    SYSTEM_TOOL_SCHEMAS,
)


class TestStatusCheckInput:

    def test_valid_app_ref(self):
        inp = StatusCheckInput(application_ref="2024-TR-0001")
        assert inp.application_ref == "2024-TR-0001"

    def test_normalizes_lowercase(self):
        inp = StatusCheckInput(application_ref="2024-tr-0001")
        assert inp.application_ref == "2024-TR-0001"

    def test_strips_whitespace(self):
        inp = StatusCheckInput(application_ref="  2024-TR-0001  ")
        assert inp.application_ref == "2024-TR-0001"

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="YYYY-XX-NNNN"):
            StatusCheckInput(application_ref="INVALID")

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            StatusCheckInput(application_ref="2024-TR")


class TestAppointmentBookInput:

    def test_valid_service(self):
        inp = AppointmentBookInput(service_type="passport")
        assert inp.service_type == "passport"

    def test_normalizes_case(self):
        inp = AppointmentBookInput(service_type="PASSPORT")
        assert inp.service_type == "passport"

    def test_optional_date(self):
        inp = AppointmentBookInput(service_type="id_card")
        assert inp.preferred_date is None

    def test_with_date(self):
        inp = AppointmentBookInput(service_type="id_card", preferred_date="2026-04-10")
        assert inp.preferred_date == "2026-04-10"

    def test_invalid_service_raises(self):
        with pytest.raises(ValueError, match="Service type"):
            AppointmentBookInput(service_type="invalid_service")


class TestDocumentRequestInput:

    def test_valid_type(self):
        inp = DocumentRequestInput(document_type="birth_certificate")
        assert inp.document_type == "birth_certificate"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError, match="Document type"):
            DocumentRequestInput(document_type="fake_doc")


class TestComplaintInput:

    def test_valid_complaint(self):
        inp = ComplaintInput(description="I waited 2 hours")
        assert inp.description == "I waited 2 hours"

    def test_too_short_raises(self):
        with pytest.raises(ValueError):
            ComplaintInput(description="ab")


class TestKnowledgeBaseSearchInput:

    def test_valid_query(self):
        inp = KnowledgeBaseSearchInput(query="passport requirements")
        assert inp.language == "tr"  # default

    def test_english_language(self):
        inp = KnowledgeBaseSearchInput(query="fees", language="en")
        assert inp.language == "en"

    def test_invalid_language_raises(self):
        with pytest.raises(ValueError, match="tr.*en"):
            KnowledgeBaseSearchInput(query="test", language="fr")


class TestToolSchemaRegistry:

    def test_all_business_tools_present(self):
        schemas = get_all_tool_schemas()
        names = {s["function"]["name"] for s in schemas}
        assert names == {
            "check_application_status",
            "book_appointment",
            "request_document",
            "file_complaint",
            "search_knowledge_base",
        }

    def test_schemas_are_openai_format(self):
        for schema in get_all_tool_schemas():
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "parameters" in schema["function"]
            assert schema["function"]["parameters"]["type"] == "object"

    def test_deployable_system_tools(self):
        """Only tools without _deploy=False are returned."""
        tools = get_system_tool_configs()
        names = {t["name"] for t in tools}
        assert "language_detection" in names
        assert "end_call" in names
        # transfer_to_number excluded until Twilio configured
        assert "transfer_to_number" not in names

    def test_all_system_tools_in_registry(self):
        """All 3 system tools exist in the registry."""
        assert len(SYSTEM_TOOL_SCHEMAS) == 3
        assert "transfer_to_number" in SYSTEM_TOOL_SCHEMAS

    def test_system_tools_format(self):
        for tool in get_system_tool_configs():
            assert tool["type"] == "system"
            assert "name" in tool
            assert "params" in tool
