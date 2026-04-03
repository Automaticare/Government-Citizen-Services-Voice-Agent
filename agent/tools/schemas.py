"""
Tool schemas and input validation for LangGraph agent.

Business tools (status_check, appointment_book, etc.) are executed by
LangGraph nodes, NOT registered as ElevenLabs server tools. This avoids
double tool calling between ElevenLabs and LangGraph.

System tools (end_call, language_detection, transfer_to_number) are
registered on ElevenLabs and returned as function calls from Custom LLM.

This module provides:
- Pydantic validation models for tool inputs
- OpenAI-format schema registry for documentation/testing
- Validation helpers used by LangGraph nodes before API calls
"""

from pydantic import BaseModel, Field, field_validator


# --- Input validation models (used by LangGraph nodes) ---

class StatusCheckInput(BaseModel):
    """Input for application status check."""
    application_ref: str = Field(description="Application reference number (format: YYYY-XX-NNNN)")

    @field_validator("application_ref")
    @classmethod
    def validate_app_ref(cls, v: str) -> str:
        import re
        cleaned = v.strip().upper()
        if not re.match(r"^\d{4}-[A-Z]{2}-\d{4}$", cleaned):
            raise ValueError("Application ref must be in format YYYY-XX-NNNN")
        return cleaned


class AppointmentBookInput(BaseModel):
    """Input for appointment booking."""
    service_type: str = Field(description="Type of service (passport, id_card, residence, driver_license)")
    preferred_date: str | None = Field(default=None, description="Preferred date (YYYY-MM-DD)")

    @field_validator("service_type")
    @classmethod
    def validate_service_type(cls, v: str) -> str:
        valid_types = {"passport", "id_card", "residence", "driver_license", "general"}
        cleaned = v.strip().lower()
        if cleaned not in valid_types:
            raise ValueError(f"Service type must be one of: {', '.join(valid_types)}")
        return cleaned


class DocumentRequestInput(BaseModel):
    """Input for document request."""
    document_type: str = Field(description="Type of document (birth_certificate, residence_cert, marriage_cert)")

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        valid_types = {"birth_certificate", "residence_cert", "marriage_cert", "criminal_record", "general"}
        cleaned = v.strip().lower()
        if cleaned not in valid_types:
            raise ValueError(f"Document type must be one of: {', '.join(valid_types)}")
        return cleaned


class ComplaintInput(BaseModel):
    """Input for complaint recording."""
    description: str = Field(description="Description of the complaint", min_length=5)
    category: str = Field(default="general", description="Complaint category")


class KnowledgeBaseSearchInput(BaseModel):
    """Input for knowledge base search (RAG)."""
    query: str = Field(description="Search query for the knowledge base", min_length=2)
    language: str = Field(default="tr", description="Language for search results (tr or en)")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("tr", "en"):
            raise ValueError("Language must be 'tr' or 'en'")
        return v


# --- OpenAI-format tool schema registry (for documentation/testing) ---

TOOL_SCHEMAS = {
    "check_application_status": {
        "type": "function",
        "function": {
            "name": "check_application_status",
            "description": "Check the current status of a citizen's application. Requires authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "application_ref": {
                        "type": "string",
                        "description": "Application reference number (format: YYYY-XX-NNNN)",
                    },
                },
                "required": ["application_ref"],
            },
        },
    },
    "book_appointment": {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment for a government service. Requires authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_type": {
                        "type": "string",
                        "enum": ["passport", "id_card", "residence", "driver_license", "general"],
                        "description": "Type of government service",
                    },
                    "preferred_date": {
                        "type": "string",
                        "description": "Preferred appointment date (YYYY-MM-DD)",
                    },
                },
                "required": ["service_type"],
            },
        },
    },
    "request_document": {
        "type": "function",
        "function": {
            "name": "request_document",
            "description": "Request preparation of an official document. Requires authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "document_type": {
                        "type": "string",
                        "enum": ["birth_certificate", "residence_cert", "marriage_cert", "criminal_record", "general"],
                        "description": "Type of official document",
                    },
                },
                "required": ["document_type"],
            },
        },
    },
    "file_complaint": {
        "type": "function",
        "function": {
            "name": "file_complaint",
            "description": "Record a citizen complaint or feedback. Does not require authentication.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Description of the complaint",
                    },
                    "category": {
                        "type": "string",
                        "description": "Complaint category (waiting_time, service_quality, staff, other)",
                    },
                },
                "required": ["description"],
            },
        },
    },
    "search_knowledge_base": {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "Search the government services knowledge base for information about procedures, requirements, fees, and regulations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "language": {
                        "type": "string",
                        "enum": ["tr", "en"],
                        "description": "Language for search results",
                    },
                },
                "required": ["query"],
            },
        },
    },
}

# System tools — registered on ElevenLabs, returned as function calls from Custom LLM
SYSTEM_TOOL_SCHEMAS = {
    "transfer_to_number": {
        "type": "system",
        "name": "transfer_to_number",
        "description": "Transfer the caller to a human operator when the agent cannot resolve the issue or the caller requests it.",
        "params": {
            "system_tool_type": "transfer_to_number",
            "transfers": [],  # Populated when Twilio is configured (ISSUE-15B)
        },
        "_deploy": False,  # Skip deploy until Twilio is set up
    },
    "end_call": {
        "type": "system",
        "name": "end_call",
        "description": "End the call when the conversation is complete and the citizen has no more questions.",
        "params": {"system_tool_type": "end_call"},
    },
    "language_detection": {
        "type": "system",
        "name": "language_detection",
        "description": "Detect the caller's language and switch to it. Trigger when the user speaks a different language than the current conversation language.",
        "params": {"system_tool_type": "language_detection"},
    },
}


def get_all_tool_schemas() -> list[dict]:
    """Return all business tool schemas in OpenAI format."""
    return list(TOOL_SCHEMAS.values())


def get_system_tool_configs() -> list[dict]:
    """Return deployable system tool configs for ElevenLabs.

    Excludes tools marked with _deploy=False (e.g. transfer_to_number
    until Twilio is configured).
    """
    return [t for t in SYSTEM_TOOL_SCHEMAS.values() if t.get("_deploy", True)]
