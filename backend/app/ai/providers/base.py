"""Base interfaces for pluggable AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Literal, Sequence, TypeVar, TypedDict

from pydantic import BaseModel

TModel = TypeVar("TModel", bound=BaseModel)


class StructuredMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class ToolCallRequest(TypedDict):
    """A tool call returned by the model."""
    id: str
    name: str
    arguments: dict[str, Any]


class ToolResult(TypedDict):
    """Result of executing a tool, fed back to the model."""
    tool_call_id: str
    content: str


class ToolsResponse(TypedDict):
    """Response from generate_with_tools: either text or tool_calls."""
    content: str | None
    tool_calls: list[ToolCallRequest]


class AIProviderError(RuntimeError):
    """Generic provider execution error."""


class AIProviderNotConfiguredError(AIProviderError):
    """Raised when provider is disabled or missing required config."""


class AIProviderNotAvailableError(AIProviderError):
    """Raised when runtime dependency for provider is unavailable."""


class BaseAIProvider(ABC):
    @abstractmethod
    def is_enabled(self) -> bool:
        """Whether provider should be used for requests."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether provider has complete configuration."""

    @abstractmethod
    def generate_structured(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
        schema_model: type[TModel],
    ) -> TModel:
        """Run model completion and validate response against schema."""

    @abstractmethod
    def generate_text(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
    ) -> str:
        """Run model completion and return plain text (no schema)."""

    def generate_with_tools(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolsResponse:
        """Run model completion with tool definitions. Returns text or tool_calls."""
        raise AIProviderNotConfiguredError("Tool calling not supported")


class DisabledAIProvider(BaseAIProvider):
    def is_enabled(self) -> bool:
        return False

    def is_configured(self) -> bool:
        return False

    def generate_structured(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
        schema_model: type[TModel],
    ) -> TModel:
        raise AIProviderNotConfiguredError("AI provider is disabled")

    def generate_text(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
    ) -> str:
        raise AIProviderNotConfiguredError("AI provider is disabled")

    def generate_with_tools(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolsResponse:
        raise AIProviderNotConfiguredError("AI provider is disabled")

