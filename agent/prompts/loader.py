"""
Prompt loader with version management.

Loads system prompts from versioned directories and tracks
which version is active per conversation.
"""

from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
DEFAULT_VERSION = "v1.0"


def load_system_prompt(language: str = "tr", version: str = DEFAULT_VERSION) -> str:
    """Load a system prompt by language and version.

    Args:
        language: "tr" or "en"
        version: Prompt version directory name (e.g., "v1.0")

    Returns:
        System prompt content as string.

    Raises:
        FileNotFoundError: If the prompt file doesn't exist.
    """
    prompt_file = PROMPTS_DIR / version / f"system_prompt_{language}.md"

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"Prompt not found: {prompt_file}. "
            f"Available versions: {list_versions()}"
        )

    return prompt_file.read_text(encoding="utf-8")


def list_versions() -> list[str]:
    """List all available prompt versions."""
    return sorted(
        d.name for d in PROMPTS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("v")
    )


def get_latest_version() -> str:
    """Return the latest prompt version."""
    versions = list_versions()
    return versions[-1] if versions else DEFAULT_VERSION
