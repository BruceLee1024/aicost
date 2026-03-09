"""Quota candidate reranking agent with deterministic fallback."""

from __future__ import annotations

import json
from typing import Any

from app.ai.prompts import load_prompt
from app.ai.providers import AIProviderError, get_ai_provider
from app.ai.schemas.quota_match import AIQuotaRerankOutput

_DEFAULT_SYSTEM_PROMPT = (
    "你是定额匹配重排助手。请对候选定额按相关性重排并输出 JSON。"
)


def rerank_quota_candidates_with_agent(
    *,
    boq_code: str,
    boq_name: str,
    boq_unit: str,
    candidates: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    """Rerank quota candidates using model when enabled, otherwise return original order."""
    if not candidates:
        return []

    fallback = candidates[:top_n]
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return fallback

    try:
        system_prompt = load_prompt("quota_rerank.txt")
    except OSError:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    limited_candidates = candidates[:20]
    payload = {
        "boq_item": {
            "code": boq_code,
            "name": boq_name,
            "unit": boq_unit,
        },
        "candidates": limited_candidates,
        "top_n": top_n,
    }

    try:
        result = provider.generate_structured(
            task="quota_rerank",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            schema_model=AIQuotaRerankOutput,
        )
    except AIProviderError:
        return fallback

    by_id = {int(c["quota_item_id"]): c for c in limited_candidates}
    ordered: list[dict[str, Any]] = []
    used_ids: set[int] = set()

    for ranked in result.candidates:
        rid = int(ranked.quota_item_id)
        if rid in used_ids:
            continue
        src = by_id.get(rid)
        if src is None:
            continue
        item = dict(src)
        item["confidence"] = round(float(ranked.confidence), 3)
        if ranked.reasons:
            item["reasons"] = ranked.reasons
        ordered.append(item)
        used_ids.add(rid)
        if len(ordered) >= top_n:
            break

    for src in limited_candidates:
        rid = int(src["quota_item_id"])
        if rid in used_ids:
            continue
        ordered.append(dict(src))
        if len(ordered) >= top_n:
            break

    return ordered
