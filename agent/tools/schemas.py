"""
System tool schemas for ElevenLabs agent deployment.

System tools (end_call, language_detection, transfer_to_number) are
registered on ElevenLabs and returned as function calls from Custom LLM.
"""

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


def get_system_tool_configs() -> list[dict]:
    """Return deployable system tool configs for ElevenLabs.

    Excludes tools marked with _deploy=False (e.g. transfer_to_number
    until Twilio is configured).
    """
    return [t for t in SYSTEM_TOOL_SCHEMAS.values() if t.get("_deploy", True)]
