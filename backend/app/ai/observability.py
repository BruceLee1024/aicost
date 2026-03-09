"""Logging helpers for AI model calls."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("app.ai")


def log_ai_call(
    *,
    task: str,
    provider: str,
    model: str | None,
    success: bool,
    duration_ms: int,
    error: str | None = None,
    input_size: int | None = None,
    output_size: int | None = None,
) -> None:
    payload: dict[str, Any] = {
        "task": task,
        "provider": provider,
        "model": model,
        "success": success,
        "duration_ms": duration_ms,
    }
    if error:
        payload["error"] = error
    if input_size is not None:
        payload["input_size"] = input_size
    if output_size is not None:
        payload["output_size"] = output_size
    logger.info("ai_call %s", json.dumps(payload, ensure_ascii=False))

