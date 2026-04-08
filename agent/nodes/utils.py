"""
Shared utilities for graph nodes.
"""


def get_honorific(profile: dict, language: str = "en") -> str:
    """Build honorific name from citizen profile.

    Returns "Mr. John" / "Ms. Sarah" for English,
    "Ahmet Bey" / "Fatma Hanim" for Turkish.
    """
    first_name = profile.get("first_name", "")
    gender = profile.get("gender", "M")

    if language == "en":
        title = "Mr." if gender == "M" else "Ms."
        return f"{title} {first_name}"
    else:
        suffix = "Bey" if gender == "M" else "Hanim"
        return f"{first_name} {suffix}"


def mark_completed(state: dict, intent: str) -> list:
    """Add intent to completed list if not already there."""
    completed = list(state.get("completed_intents", []))
    if intent not in completed:
        completed.append(intent)
    return completed
