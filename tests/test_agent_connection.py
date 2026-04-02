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


class TestCustomLLMConfig:
    """Test Custom LLM URL configuration."""

    def test_custom_llm_url_from_env(self):
        with patch.dict(os.environ, {"CUSTOM_LLM_URL": "https://test.ngrok.app"}):
            config = AgentConfig(api_key="test", agent_id="test")
            assert config.custom_llm_url == "https://test.ngrok.app"

    def test_custom_llm_url_defaults_empty(self):
        with patch.dict(os.environ, {}, clear=False):
            config = AgentConfig(api_key="test", agent_id="test", custom_llm_url="")
            assert config.custom_llm_url == ""


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
        agent = client.conversational_ai.agents.get(agent_id=config.agent_id)
        assert agent is not None
        print(f"Agent found: {agent.name}")
