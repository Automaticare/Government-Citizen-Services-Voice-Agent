"""
Deploy agent configuration to ElevenLabs platform via API.

Configures a single multilingual agent with language presets (TR + EN),
automatic language detection, and Custom LLM endpoint (our LangGraph
proxy). When Custom LLM is unreachable, ElevenLabs falls back to its
default LLM (Level 2 graceful degradation via backup_llm_config).

Usage:
    python -m agent.deploy                  # Deploy multilingual agent
    python -m agent.deploy --version v1.0   # Deploy specific prompt version
    python -m agent.deploy --dry-run        # Preview without deploying
"""

import argparse
import sys

from elevenlabs.client import ElevenLabs
from elevenlabs.types import (
    AgentConfig as ELAgentConfig,
    ConversationalConfig,
    TtsConversationalConfigOutput,
)

from agent.config import AgentConfig
from agent.logging_config import get_logger
from agent.prompts.loader import load_system_prompt, get_latest_version, list_versions

logger = get_logger(__name__)

# First messages per language
FIRST_MESSAGES = {
    "tr": "Merhaba, Vatandas Hizmetleri'ne hos geldiniz. Ben Umut, size nasil yardimci olabilirim?",
    "en": "Hello, welcome to Citizen Services. I'm Umut, how can I help you today?",
}


def build_agent_config(version: str, custom_llm_url: str | None = None) -> dict:
    """Build the ElevenLabs multilingual agent update payload.

    Primary language is Turkish. English is added as a language preset.
    Language detection system tool enables automatic switching.

    Args:
        version: Prompt version (e.g., "v1.0")
        custom_llm_url: Public URL for our Custom LLM proxy (e.g. ngrok URL).
                        If set, ElevenLabs sends requests to our LangGraph server
                        instead of using its native LLM.

    Returns:
        Dict with conversation_config and name for the update call.
    """
    system_prompt_tr = load_system_prompt(language="tr", version=version)

    # Language detection system tool — auto-switches based on caller's language
    language_detection_tool = {
        "type": "system",
        "name": "language_detection",
        "description": "Detect the caller's language and switch to it. Trigger when the user speaks a different language than the current conversation language.",
        "params": {"system_tool_type": "language_detection"},
    }

    # Prompt config — common fields
    prompt_config = {
        "prompt": system_prompt_tr,
        "llm": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1024,
        "tools": [language_detection_tool],
    }

    # Custom LLM: route all LLM calls to our LangGraph proxy
    if custom_llm_url:
        # ElevenLabs requires llm="custom-llm" when custom_llm is set
        prompt_config["llm"] = "custom-llm"

        # ElevenLabs auto-appends /v1/chat/completions — only pass base URL
        url = custom_llm_url.rstrip("/")
        url = url.removesuffix("/v1/chat/completions").removesuffix("/v1")

        prompt_config["custom_llm"] = {
            "url": url,
            # ngrok free plan shows an HTML interstitial page on first request.
            # This header bypasses it so ElevenLabs gets JSON, not HTML.
            "request_headers": {
                "ngrok-skip-browser-warning": "true",
            },
        }
        # Level 2 graceful degradation: if Custom LLM is unreachable,
        # ElevenLabs falls back to its default native LLM
        prompt_config["backup_llm_config"] = {
            "preference": "default",
        }

    # Primary config: Turkish
    conversation_config = ConversationalConfig(
        agent=ELAgentConfig(
            prompt=prompt_config,
            first_message=FIRST_MESSAGES["tr"],
            language="tr",
        ),
        tts=TtsConversationalConfigOutput(
            model_id="eleven_flash_v2_5",
        ),
        # English language preset — dict format to avoid Input/Output type mismatch
        language_presets={
            "en": {
                "overrides": {
                    "agent": {
                        "first_message": FIRST_MESSAGES["en"],
                    },
                },
            },
        },
    )

    return {
        "conversation_config": conversation_config,
        "name": f"Umut - Citizen Services (Multilingual, {version})",
    }


def deploy(version: str | None = None, dry_run: bool = False) -> None:
    """Deploy multilingual agent configuration to ElevenLabs.

    Args:
        version: Prompt version. Uses latest if not specified.
        dry_run: If True, preview config without deploying.
    """
    if version is None:
        version = get_latest_version()

    config = AgentConfig()
    errors = config.validate()
    if errors:
        logger.error(f"Config validation failed: {', '.join(errors)}")
        sys.exit(1)

    custom_llm_url = config.custom_llm_url or None
    payload = build_agent_config(version=version, custom_llm_url=custom_llm_url)

    logger.info(f"Agent: {payload['name']}")
    logger.info(f"Prompt version: {version}")
    logger.info(f"Primary language: TR | Additional: EN")
    logger.info(f"Language detection: enabled")
    if custom_llm_url:
        logger.info(f"Custom LLM: {custom_llm_url}")
        logger.info(f"Backup LLM: default (Level 2 fallback)")
    else:
        logger.info(f"Custom LLM: not configured (using ElevenLabs native LLM)")

    if dry_run:
        logger.info("[DRY RUN] Would deploy the above config. No changes made.")
        return

    client = ElevenLabs(api_key=config.api_key)

    agent = client.conversational_ai.agents.update(
        agent_id=config.agent_id,
        name=payload["name"],
        conversation_config=payload["conversation_config"],
    )

    logger.info(f"Deployed successfully. Agent ID: {agent.agent_id}")


def main():
    parser = argparse.ArgumentParser(description="Deploy multilingual agent to ElevenLabs")
    parser.add_argument("--version", default=None, help=f"Prompt version. Available: {list_versions()}")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    args = parser.parse_args()

    deploy(version=args.version, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
