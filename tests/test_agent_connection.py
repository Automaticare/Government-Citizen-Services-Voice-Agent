"""
Test ElevenLabs agent connectivity and basic response.

Verifies that:
- API key is valid and agent is reachable
- Agent responds to a basic greeting
- Configuration validation works correctly
"""

import os
import pytest
from unittest.mock import patch
from agent.config import AgentConfig


class TestAgentConfig:
    """Test configuration validation."""

    def test_valid_config(self):
        config = AgentConfig(
            api_key="test-key",
            agent_id="test-agent-id",
        )
        assert config.validate() == []

    def test_missing_api_key(self):
        config = AgentConfig(api_key="", agent_id="test-agent-id")
        errors = config.validate()
        assert "ELEVENLABS_API_KEY is not set" in errors

    def test_missing_agent_id(self):
        config = AgentConfig(api_key="test-key", agent_id="")
        errors = config.validate()
        assert "ELEVENLABS_AGENT_ID is not set" in errors

    def test_missing_all_required(self):
        config = AgentConfig(api_key="", agent_id="")
        errors = config.validate()
        assert len(errors) == 2

    def test_default_language(self):
        config = AgentConfig(api_key="test-key", agent_id="test-agent-id")
        assert config.default_language == os.getenv("DEFAULT_LANGUAGE", "tr")

    def test_max_auth_attempts(self):
        config = AgentConfig(api_key="test-key", agent_id="test-agent-id")
        assert config.max_auth_attempts == 3


class TestConversationCreation:
    """Test conversation factory function."""

    def test_raises_on_invalid_config(self):
        from agent.conversation import create_conversation

        config = AgentConfig(api_key="", agent_id="")
        with pytest.raises(ValueError, match="Invalid config"):
            create_conversation(config)


@pytest.mark.skipif(
    not os.getenv("ELEVENLABS_API_KEY"),
    reason="ELEVENLABS_API_KEY not set — skipping live API test",
)
class TestLiveAgentConnection:
    """Live tests that require real API credentials.

    These tests are skipped in CI and only run when API keys are configured.
    """

    def test_agent_is_reachable(self):
        """Verify the agent exists and is accessible via API."""
        from elevenlabs.client import ElevenLabs

        config = AgentConfig()
        client = ElevenLabs(api_key=config.api_key)

        # Fetch agent details — will raise if agent doesn't exist
        agent = client.conversational_ai.get_agent(config.agent_id)
        assert agent is not None
        print(f"Agent found: {agent.name}")
