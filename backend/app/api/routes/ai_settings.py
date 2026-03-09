"""AI settings management routes (read + update multi-provider config)."""

from __future__ import annotations

import os
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.config import (
    AISettings,
    AI_SUPPORTED_PROVIDERS,
    AI_VALID_PROVIDERS,
    _DEFAULT_BASE_URLS,
    _DEFAULT_MODELS,
    get_ai_settings_payload,
)
from app.ai.providers.openai_compat import OpenAICompatProvider
from app.db.session import get_db
from app.models.system_setting import SystemSetting
from app.schemas.ai_settings import AISettingsPayload

router = APIRouter(tags=["ai-settings"])


@router.get("/ai/settings", response_model=AISettingsPayload)
def get_settings() -> AISettingsPayload:
    return AISettingsPayload.model_validate(get_ai_settings_payload())


@router.put("/ai/settings", response_model=AISettingsPayload)
def update_settings(
    payload: AISettingsPayload,
    db: Session = Depends(get_db),
) -> AISettingsPayload:
    provider = payload.provider.strip().lower()
    if provider not in AI_VALID_PROVIDERS:
        raise HTTPException(status_code=400, detail="unsupported provider")

    values = _flatten_payload(payload)
    _upsert_settings(db, values)

    # Mirror into process env for immediate effect in current worker.
    for key, value in values.items():
        os.environ[key] = value

    return AISettingsPayload.model_validate(get_ai_settings_payload())


class AITestConnectionRequest(BaseModel):
    provider: str = Field(..., description="Provider key, e.g. deepseek/qwen/kimi/glm/openai")
    api_key: str = ""
    base_url: str = ""
    model: str = ""
    timeout_seconds: float | None = None


class AITestConnectionResponse(BaseModel):
    success: bool = False
    latency_ms: int = 0
    reply: str = ""
    error: str = ""


@router.post("/ai/test-connection", response_model=AITestConnectionResponse)
def test_ai_connection(payload: AITestConnectionRequest) -> AITestConnectionResponse:
    """Test connectivity/auth for a specific provider config (without saving)."""
    provider_key = payload.provider.strip().lower()
    if provider_key not in AI_SUPPORTED_PROVIDERS:
        raise HTTPException(status_code=400, detail="unsupported provider")

    api_key = payload.api_key.strip()
    if not api_key:
        return AITestConnectionResponse(success=False, error="API Key 为空")

    base_url = payload.base_url.strip() or _DEFAULT_BASE_URLS.get(provider_key, "")
    if not base_url:
        return AITestConnectionResponse(success=False, error="Base URL 为空")

    model = payload.model.strip() or _DEFAULT_MODELS.get(provider_key, "")
    if not model:
        return AITestConnectionResponse(success=False, error="模型名称为空")

    timeout = float(payload.timeout_seconds) if payload.timeout_seconds else 10.0

    settings = AISettings(
        provider=provider_key,
        api_key=api_key,
        base_url=base_url,
        model=model,
        timeout_seconds=timeout,
    )
    provider = OpenAICompatProvider(settings=settings)

    started = perf_counter()
    try:
        reply = provider.generate_text(
            task="test_connection",
            messages=[
                {"role": "system", "content": "You are a connectivity test."},
                {"role": "user", "content": "请回复“连接成功”即可。"},
            ],
        )
        latency_ms = int((perf_counter() - started) * 1000)
        return AITestConnectionResponse(
            success=True,
            latency_ms=latency_ms,
            reply=(reply or "")[:200],
        )
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        err = str(exc) or exc.__class__.__name__
        # Defensive: avoid leaking key in error text
        if api_key and api_key in err:
            err = err.replace(api_key, "***")
        return AITestConnectionResponse(
            success=False,
            latency_ms=latency_ms,
            error=err[:300],
        )


def _flatten_payload(payload: AISettingsPayload) -> dict[str, str]:
    values: dict[str, str] = {
        "AI_PROVIDER": payload.provider.strip().lower(),
        "AI_TIMEOUT_SECONDS": str(payload.timeout_seconds),
        "AI_ENABLE_AUDIT_LOGS": "true" if payload.enable_audit_logs else "false",
    }
    for provider in AI_SUPPORTED_PROVIDERS:
        cfg = getattr(payload.providers, provider)
        upper = provider.upper()
        values[f"AI_{upper}_API_KEY"] = cfg.api_key.strip()
        values[f"AI_{upper}_BASE_URL"] = cfg.base_url.strip()
        values[f"AI_{upper}_MODEL"] = cfg.model.strip()
    return values


def _upsert_settings(db: Session, values: dict[str, str]) -> None:
    existing = {
        row.key: row
        for row in db.query(SystemSetting).filter(SystemSetting.key.in_(list(values.keys()))).all()
    }
    for key, value in values.items():
        row = existing.get(key)
        if row is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            row.value = value
    db.commit()
