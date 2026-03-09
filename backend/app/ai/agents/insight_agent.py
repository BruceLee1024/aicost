"""Universal AI insight agent for contextual analysis."""

from __future__ import annotations

import json
from typing import Any

from app.ai.prompts import load_prompt
from app.ai.providers import AIProviderError, get_ai_provider

_DEFAULT_SYSTEM_PROMPT = (
    "你是工程计价 AI 分析助手。根据给定的项目数据，提供简洁专业的中文分析。"
)

VALID_CONTEXT_TYPES = {"scan", "match", "calc", "validation", "provenance", "dashboard"}


def generate_insight(
    *,
    context_type: str,
    context_data: dict[str, Any],
) -> str | None:
    """Generate AI insight text for the given context.

    Returns None if AI is not available (caller should use static fallback).
    """
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return None

    try:
        system_prompt = load_prompt("insight_analyze.txt")
    except OSError:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    user_content = json.dumps(
        {"context_type": context_type, "data": context_data},
        ensure_ascii=False,
    )

    try:
        return provider.generate_text(
            task=f"insight_{context_type}",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
    except AIProviderError:
        return None
