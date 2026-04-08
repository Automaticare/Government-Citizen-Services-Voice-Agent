"""
Shared utilities for graph nodes.
"""


def mark_completed(state: dict, intent: str) -> list:
    """Add intent to completed list if not already there."""
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed
