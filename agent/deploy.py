"""
Deploy agent configuration to ElevenLabs platform via API.

Usage:
    python -m agent.deploy                  # Deploy with defaults (TR, v1.0)
    python -m agent.deploy --language en    # Deploy English prompt
    python -m agent.deploy --version v1.0   # Deploy specific version
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

# Agent first messages per language
FIRST_MESSAGES = {
    "tr": "Merhaba, Vatandaş Hizmetleri'ne hoş geldiniz. Ben Umut, size nasıl yardımcı olabilirim?",
    "en": "Hello, welcome to Citizen Services. I'm Umut, how can I help you today?",
}


def build_agent_config(language: str, version: str) -> dict:
    """Build the ElevenLabs agent update payload.

    Args:
        language: "tr" or "en"
        version: Prompt version (e.g., "v1.0")

    Returns:
        Dict with conversation_config and name for the update call.
    """
    system_prompt = load_system_prompt(language=language, version=version)
    first_message = FIRST_MESSAGES.get(language, FIRST_MESSAGES["tr"])

    # English requires turbo/flash v2; multilingual v2 supports Turkish
    tts_model = "eleven_flash_v2" if language == "en" else "eleven_flash_v2_5"

    conversation_config = ConversationalConfig(
        agent=ELAgentConfig(
            prompt={
                "prompt": system_prompt,
                "llm": "gpt-4o",
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            first_message=first_message,
            language=language,
        ),
        tts=TtsConversationalConfigOutput(
            model_id=tts_model,
        ),
    )

    return {
        "conversation_config": conversation_config,
        "name": f"Umut - Citizen Services ({language.upper()}, {version})",
    }


def deploy(language: str = "tr", version: str | None = None, dry_run: bool = False) -> None:
    """Deploy agent configuration to ElevenLabs.

    Args:
        language: Target language ("tr" or "en")
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

    payload = build_agent_config(language=language, version=version)

    logger.info(f"Agent: {payload['name']}")
    logger.info(f"Prompt version: {version}")
    logger.info(f"Language: {language}")

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
    parser = argparse.ArgumentParser(description="Deploy agent config to ElevenLabs")
    parser.add_argument("--language", choices=["tr", "en"], default="tr")
    parser.add_argument("--version", default=None, help=f"Prompt version. Available: {list_versions()}")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deploying")
    args = parser.parse_args()

    deploy(language=args.language, version=args.version, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
