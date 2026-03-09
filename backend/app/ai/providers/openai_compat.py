"""OpenAI-compatible provider (works with DeepSeek-compatible endpoints)."""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, Sequence

from pydantic import BaseModel, ValidationError

from app.ai.config import AISettings
from app.ai.observability import log_ai_call
from app.ai.providers.base import (
    AIProviderError,
    AIProviderNotAvailableError,
    AIProviderNotConfiguredError,
    BaseAIProvider,
    StructuredMessage,
    TModel,
    ToolCallRequest,
    ToolsResponse,
)


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise AIProviderError("Empty model output")

    if stripped.startswith("```"):
        stripped = stripped.strip("`").strip()
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()

    try:
        data = json.loads(stripped)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AIProviderError("Model output is not valid JSON object")

    candidate = stripped[start : end + 1]
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AIProviderError("Model output JSON parse failed") from exc

    if not isinstance(data, dict):
        raise AIProviderError("Model output JSON root must be object")
    return data


class OpenAICompatProvider(BaseAIProvider):
    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._client: Any | None = None

    def is_enabled(self) -> bool:
        return self._settings.is_enabled()

    def is_configured(self) -> bool:
        return self._settings.is_configured()

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - runtime dependency
            raise AIProviderNotAvailableError("openai package is not installed") from exc

        self._client = OpenAI(
            api_key=self._settings.api_key,
            base_url=self._settings.base_url,
            timeout=self._settings.timeout_seconds,
        )
        return self._client

    def generate_structured(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
        schema_model: type[TModel],
    ) -> TModel:
        if not self.is_enabled():
            raise AIProviderNotConfiguredError("AI provider is disabled or misconfigured")

        started = perf_counter()
        input_size = sum(len(m["content"]) for m in messages)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                temperature=0,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content or ""
            payload = _extract_json_object(content)
            parsed = schema_model.model_validate(payload)

            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=True,
                duration_ms=int((perf_counter() - started) * 1000),
                input_size=input_size,
                output_size=len(content),
            )
            return parsed
        except AIProviderError as exc:
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error=str(exc),
                input_size=input_size,
            )
            raise
        except ValidationError as exc:
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error=f"schema_validation_error: {exc.errors()}",
                input_size=input_size,
            )
            raise AIProviderError("Model output failed schema validation") from exc
        except Exception as exc:  # pragma: no cover - network/runtime failures
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error=exc.__class__.__name__,
                input_size=input_size,
            )
            raise AIProviderError(f"Provider call failed: {exc.__class__.__name__}") from exc

    def generate_text(
        self,
        *,
        task: str,
        messages: Sequence[StructuredMessage],
    ) -> str:
        """Run model completion and return plain text."""
        if not self.is_enabled():
            raise AIProviderNotConfiguredError("AI provider is disabled or misconfigured")

        started = perf_counter()
        input_size = sum(len(m["content"]) for m in messages)

        try:
            client = self._get_client()
            response = client.chat.completions.create(
                model=self._settings.model,
                messages=[{"role": m["role"], "content": m["content"]} for m in messages],
                temperature=0.3,
            )
            content = response.choices[0].message.content or ""
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=True,
                duration_ms=int((perf_counter() - started) * 1000),
                input_size=input_size,
                output_size=len(content),
            )
            return content.strip()
        except AIProviderError:
            raise
        except Exception as exc:  # pragma: no cover
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error=exc.__class__.__name__,
                input_size=input_size,
            )
            raise AIProviderError(f"Provider call failed: {exc.__class__.__name__}") from exc

    def generate_with_tools(
        self,
        *,
        task: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ToolsResponse:
        """Run model completion with OpenAI function calling."""
        if not self.is_enabled():
            raise AIProviderNotConfiguredError("AI provider is disabled or misconfigured")

        started = perf_counter()
        input_size = sum(len(str(m.get("content", ""))) for m in messages)

        try:
            client = self._get_client()
            kwargs: dict[str, Any] = {
                "model": self._settings.model,
                "messages": messages,
                "temperature": 0,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            msg = choice.message

            tool_calls: list[ToolCallRequest] = []
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}
                    tool_calls.append(ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    ))

            content = msg.content or ""
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=True,
                duration_ms=int((perf_counter() - started) * 1000),
                input_size=input_size,
                output_size=len(content) + sum(len(str(tc["arguments"])) for tc in tool_calls),
            )
            return ToolsResponse(content=content or None, tool_calls=tool_calls)
        except AIProviderError:
            raise
        except Exception as exc:
            log_ai_call(
                task=task,
                provider=self._settings.provider,
                model=self._settings.model,
                success=False,
                duration_ms=int((perf_counter() - started) * 1000),
                error=exc.__class__.__name__,
                input_size=input_size,
            )
            raise AIProviderError(f"Tool call failed: {exc.__class__.__name__}") from exc

