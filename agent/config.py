"""
ElevenLabs Conversational AI agent configuration.

Agent is created via ElevenLabs dashboard. This module provides
the configuration interface for connecting to and managing the agent.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    """Configuration for the ElevenLabs Conversational AI agent."""

    # ElevenLabs
    api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    agent_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_AGENT_ID", ""))

    # OpenAI (for LangGraph agent / embeddings)
    openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))

    # Pinecone (for RAG)
    pinecone_api_key: str = field(default_factory=lambda: os.getenv("PINECONE_API_KEY", ""))
    pinecone_index_name: str = field(
        default_factory=lambda: os.getenv("PINECONE_INDEX_NAME", "gov-citizen-services")
    )

    # Agent behavior
    default_language: str = field(
        default_factory=lambda: os.getenv("DEFAULT_LANGUAGE", "tr")
    )
    max_auth_attempts: int = 3
    requires_auth: bool = True

    def validate(self) -> list[str]:
        """Return list of missing required config fields."""
        errors = []
        if not self.api_key:
            errors.append("ELEVENLABS_API_KEY is not set")
        if not self.agent_id:
            errors.append("ELEVENLABS_AGENT_ID is not set")
        return errors
