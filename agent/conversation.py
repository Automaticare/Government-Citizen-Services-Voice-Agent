"""
ElevenLabs Conversation session manager.

Wraps the ElevenLabs Conversation class with project-specific
configuration and callback handling.
"""

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from agent.config import AgentConfig
from agent.logging_config import get_logger

logger = get_logger(__name__)


def create_conversation(config: AgentConfig | None = None) -> Conversation:
    """Create and return an ElevenLabs Conversation instance.

    Args:
        config: Agent configuration. Uses defaults from env if not provided.

    Returns:
        Configured Conversation ready to start.

    Raises:
        ValueError: If required config fields are missing.
    """
    if config is None:
        config = AgentConfig()

    errors = config.validate()
    if errors:
        raise ValueError(f"Invalid config: {', '.join(errors)}")

    client = ElevenLabs(api_key=config.api_key)
    audio_interface = DefaultAudioInterface()

    conversation = Conversation(
        client=client,
        agent_id=config.agent_id,
        requires_auth=config.requires_auth,
        audio_interface=audio_interface,
        callback_agent_response=lambda response: logger.info(f"Agent: {response}"),
        callback_user_transcript=lambda transcript: logger.info(f"User: {transcript}"),
    )

    return conversation


def run_conversation(config: AgentConfig | None = None) -> None:
    """Start a blocking conversation session.

    Creates a conversation and runs it until the user ends the call
    or an interrupt signal is received.
    """
    conversation = create_conversation(config)

    logger.info("Starting conversation session...")
    conversation.start_session()

    try:
        conversation.wait_for_session_end()
    except KeyboardInterrupt:
        logger.info("Session interrupted by user.")
    finally:
        conversation.end_session()
        logger.info("Session ended.")
