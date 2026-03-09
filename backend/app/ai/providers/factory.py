"""Factory for selecting configured AI provider implementation."""

from __future__ import annotations

from app.ai.config import AI_SUPPORTED_PROVIDERS, get_ai_settings
from app.ai.providers.base import BaseAIProvider, DisabledAIProvider
from app.ai.providers.openai_compat import OpenAICompatProvider

# All supported providers use the OpenAI-compatible protocol.
_OPENAI_COMPAT_PROVIDERS = set(AI_SUPPORTED_PROVIDERS)


def get_ai_provider() -> BaseAIProvider:
    settings = get_ai_settings()
    if not settings.is_enabled():
        return DisabledAIProvider()

    if settings.provider in _OPENAI_COMPAT_PROVIDERS:
        return OpenAICompatProvider(settings=settings)

    return DisabledAIProvider()

