"""Natural language query intent agent with fallback to original query."""

from __future__ import annotations

import json

from app.ai.prompts import load_prompt
from app.ai.providers import AIProviderError, get_ai_provider
from app.ai.schemas.query import AIQueryIntentOutput

_INTENT_QUERY_MAP = {
    "unbound": "未绑定",
    "issues": "异常",
    "dirty": "待重算",
}

_DEFAULT_SYSTEM_PROMPT = (
    "你是查询路由助手，把 query 分类为 unbound/issues/dirty/keyword，并输出 JSON。"
)


def normalize_query_for_router(query: str) -> str:
    """Convert arbitrary NL query to the route's canonical query tokens."""
    q = query.strip()
    if not q:
        return q

    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return q

    try:
        system_prompt = load_prompt("query_intent.txt")
    except OSError:
        system_prompt = _DEFAULT_SYSTEM_PROMPT

    try:
        result = provider.generate_structured(
            task="query_intent",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps({"query": q}, ensure_ascii=False)},
            ],
            schema_model=AIQueryIntentOutput,
        )
    except AIProviderError:
        return q

    if result.intent == "keyword":
        keyword = (result.keyword or q).strip()
        return keyword or q

    return _INTENT_QUERY_MAP.get(result.intent, q)

