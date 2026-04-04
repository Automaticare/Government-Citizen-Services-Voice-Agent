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

    # System tools — platform-native, executed by ElevenLabs (not LangGraph)
    from agent.tools.schemas import get_system_tool_configs
    system_tools = get_system_tool_configs()

    # Prompt config — common fields
    prompt_config = {
        "prompt": system_prompt_tr,
        "llm": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1024,
        "tools": system_tools,
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

    # Timeout message when max duration is reached
    MAX_DURATION_MSG_TR = ("Gorusme suresi doldu. Baska bir konuda yardima ihtiyaciniz olursa "
                           "lutfen tekrar arayin. Iyi gunler dilerim.")

    # Primary config: Turkish
    conversation_config = ConversationalConfig(
        agent=ELAgentConfig(
            prompt=prompt_config,
            first_message=FIRST_MESSAGES["tr"],
            language="tr",
            max_conversation_duration_message=MAX_DURATION_MSG_TR,
        ),
        tts=TtsConversationalConfigOutput(
            model_id="eleven_flash_v2_5",
        ),
        # Turn and silence settings for natural phone conversation
        turn={
            "turn_timeout": 15.0,              # Wait 15s for user to speak before prompting
            "silence_end_call_timeout": 30.0,   # End call after 30s silence
            "turn_eagerness": "patient",        # Don't interrupt — government service, be patient
        },
        # Max conversation duration: 10 minutes (600s)
        conversation={
            "max_duration_seconds": 600,
        },
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


def build_auth_workflow(custom_llm_url: str | None = None, gov_api_url: str = "http://localhost:8081") -> dict:
    """Build ElevenLabs Workflow for deterministic auth gating.

    Architecture (from ElevenLabs auth blog):
      Subagent 1 (unauthenticated) → Dispatch tool (verify) →
        Success → Subagent 2 (authenticated, Custom LLM)
        Failure → Subagent 3 (retry/transfer)

    Auth is NOT left to LLM inference — dispatch tool returns boolean,
    workflow edges route deterministically.
    """
    system_prompt_auth = (
        "Sen Umut, Vatandas Hizmetleri sesli asistanisin. "
        "Vatandasin kimligini dogrulamak icin TC Kimlik numarasini ve dogum tarihini topla. "
        "Her bilgiyi TEK TEK sor, hepsini ayni anda isteme. "
        "Oncelikle TC Kimlik numarasini sor, sonra dogum tarihini sor. "
        "ASLA TC Kimlik numarasini geri tekrar etme. "
        "Yanıtların sesli okunacak — rakam kullanma, sayi yazıyla yaz."
    )

    system_prompt_authenticated = (
        "Vatandas kimlik dogrulamasi yapildi. "
        "Artik basvuru durumu sorgulama, randevu alma, belge talebi ve diger hizmetleri sunabilirsin. "
        "Vatandasa ismiyle hitap et."
    )

    system_prompt_retry = (
        "Kimlik dogrulama basarisiz oldu. "
        "Vatandasa kibarca bilgilerini kontrol etmesini ve tekrar denemesini soyle. "
        "Dilerseniz farkli bir dogrulama yontemi (basvuru numarasi + soyad) onerebilirsin. "
        "Eger vatandas artik denemek istemiyorsa, onu bir operatore bagla."
    )

    auth_webhook_url = f"{gov_api_url}/auth/verify/webhook"

    workflow = {
        "nodes": {
            # Start node (required)
            "start_node": {
                "type": "start",
                "position": {"x": 0.0, "y": 0.0},
                "edge_order": ["edge_start_to_collect"],
            },
            # Subagent 1: Collect TC Kimlik + DOB (unauthenticated, no tools)
            "collect_info_node": {
                "type": "override_agent",
                "additional_prompt": system_prompt_auth,
                "additional_knowledge_base": [],
                "additional_tool_ids": [],
                "position": {"x": 0.0, "y": 150.0},
                "edge_order": ["edge_collect_to_auth"],
                "label": "Collect Identity",
            },
            # Dispatch tool: verify identity via webhook
            "auth_tool_node": {
                "type": "tool",
                "position": {"x": 0.0, "y": 300.0},
                "edge_order": ["edge_auth_success", "edge_auth_failure"],
                "tools": [],  # Tool configured separately — webhook called by ElevenLabs
            },
            # Subagent 2: Authenticated — full service access via Custom LLM
            "authenticated_node": {
                "type": "override_agent",
                "additional_prompt": system_prompt_authenticated,
                "additional_knowledge_base": [],
                "additional_tool_ids": [],
                "position": {"x": -200.0, "y": 450.0},
                "edge_order": ["edge_success_to_end"],
                "label": "Authenticated Service",
            },
            # Subagent 3: Auth failed — retry or transfer
            "retry_node": {
                "type": "override_agent",
                "additional_prompt": system_prompt_retry,
                "additional_knowledge_base": [],
                "additional_tool_ids": [],
                "position": {"x": 200.0, "y": 450.0},
                "edge_order": ["edge_retry_to_collect"],
                "label": "Auth Retry",
            },
            # End nodes
            "success_end_node": {
                "type": "end",
                "position": {"x": -200.0, "y": 600.0},
                "edge_order": [],
            },
        },
        "edges": {
            # Start → Collect info (unconditional)
            "edge_start_to_collect": {
                "source": "start_node",
                "target": "collect_info_node",
                "forward_condition": {
                    "type": "unconditional",
                },
            },
            # Collect info → Auth tool (LLM decides when credentials collected)
            "edge_collect_to_auth": {
                "source": "collect_info_node",
                "target": "auth_tool_node",
                "forward_condition": {
                    "type": "llm",
                    "label": "Credentials collected",
                    "condition": "User has provided both their TC Kimlik number and date of birth",
                },
            },
            # Auth success → Authenticated service
            "edge_auth_success": {
                "source": "auth_tool_node",
                "target": "authenticated_node",
                "forward_condition": {
                    "type": "result",
                    "label": "Success",
                    "successful": True,
                },
            },
            # Auth failure → Retry
            "edge_auth_failure": {
                "source": "auth_tool_node",
                "target": "retry_node",
                "forward_condition": {
                    "type": "result",
                    "label": "Failure",
                    "successful": False,
                },
            },
            # Authenticated → End
            "edge_success_to_end": {
                "source": "authenticated_node",
                "target": "success_end_node",
                "forward_condition": {
                    "type": "llm",
                    "label": "Conversation complete",
                    "condition": "User has no more questions and conversation should end",
                },
            },
            # Retry → back to collect (backward edge)
            "edge_retry_to_collect": {
                "source": "retry_node",
                "target": "collect_info_node",
                "backward_condition": {
                    "type": "llm",
                    "label": "Retry with new credentials",
                    "condition": "User wants to try again with different credentials",
                },
            },
        },
        "prevent_subagent_loops": False,
    }

    return workflow


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

    # Build workflow for deterministic auth gating
    gov_api_url = f"http://localhost:8081"  # Government API
    workflow = build_auth_workflow(
        custom_llm_url=custom_llm_url,
        gov_api_url=gov_api_url,
    )

    logger.info(f"Workflow: {len(workflow['nodes'])} nodes, {len(workflow['edges'])} edges")

    agent = client.conversational_ai.agents.update(
        agent_id=config.agent_id,
        name=payload["name"],
        conversation_config=payload["conversation_config"],
        workflow=workflow,
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
