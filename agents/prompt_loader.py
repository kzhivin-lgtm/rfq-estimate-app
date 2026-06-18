from __future__ import annotations

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DETECTION_PROMPT_PATH = PROMPTS_DIR / "detection_agent_prompt.md"


def load_detection_agent_prompt() -> str:
    if not DETECTION_PROMPT_PATH.exists():
        raise FileNotFoundError(
            f"Detection prompt not found: {DETECTION_PROMPT_PATH}"
        )

    prompt = DETECTION_PROMPT_PATH.read_text(encoding="utf-8").strip()

    if not prompt:
        raise ValueError(f"Detection prompt is empty: {DETECTION_PROMPT_PATH}")

    return prompt
