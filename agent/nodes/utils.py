"""
Shared utilities for graph nodes.
"""

import time


def mark_completed(state: dict, intent: str) -> list:
    """Add intent to completed list if not already there."""
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed


def timer():
    """Simple timer. Call once to start, call returned function to get elapsed ms."""
    start = time.time()
    return lambda: int((time.time() - start) * 1000)
