from app.ai.agents.boq_agent import generate_boq_items_with_agent
from app.ai.agents.query_agent import normalize_query_for_router
from app.ai.agents.quota_match_agent import rerank_quota_candidates_with_agent
from app.ai.providers.base import AIProviderError
from app.ai.schemas.query import AIQueryIntentOutput
from app.ai.schemas.quota_match import AIQuotaRankItem, AIQuotaRerankOutput
from app.services.boq_generate_service import generate_boq_items


class _FailingProvider:
    def is_enabled(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return True

    def generate_structured(self, **kwargs):
        raise AIProviderError("mock failure")


class _QueryIntentProvider:
    def is_enabled(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return True

    def generate_structured(self, **kwargs):
        return AIQueryIntentOutput(intent="dirty", keyword=None)


class _QuotaRerankProvider:
    def is_enabled(self) -> bool:
        return True

    def is_configured(self) -> bool:
        return True

    def generate_structured(self, **kwargs):
        return AIQuotaRerankOutput(
            candidates=[
                AIQuotaRankItem(
                    quota_item_id=2,
                    confidence=0.95,
                    reasons=["名称和单位更匹配"],
                )
            ]
        )


def test_boq_agent_fallback_on_provider_error(monkeypatch):
    description = "3层办公楼，含基础和主体结构"
    expected = generate_boq_items(description)

    monkeypatch.setattr(
        "app.ai.agents.boq_agent.get_ai_provider",
        lambda: _FailingProvider(),
    )
    actual = generate_boq_items_with_agent(description)

    assert [(x.code, x.name, x.quantity) for x in actual] == [
        (x.code, x.name, x.quantity) for x in expected
    ]


def test_query_agent_fallback_on_provider_error(monkeypatch):
    monkeypatch.setattr(
        "app.ai.agents.query_agent.get_ai_provider",
        lambda: _FailingProvider(),
    )
    assert normalize_query_for_router("查一下未绑定") == "查一下未绑定"


def test_query_agent_maps_intent_to_canonical_query(monkeypatch):
    monkeypatch.setattr(
        "app.ai.agents.query_agent.get_ai_provider",
        lambda: _QueryIntentProvider(),
    )
    assert normalize_query_for_router("哪些要重算") == "待重算"


def test_quota_rerank_agent_reorders_candidates(monkeypatch):
    monkeypatch.setattr(
        "app.ai.agents.quota_match_agent.get_ai_provider",
        lambda: _QuotaRerankProvider(),
    )

    candidates = [
        {
            "quota_item_id": 1,
            "quota_code": "A-01",
            "quota_name": "钢筋制作",
            "unit": "t",
            "confidence": 0.66,
            "reasons": ["原始排序第一"],
        },
        {
            "quota_item_id": 2,
            "quota_code": "A-02",
            "quota_name": "钢筋制作安装",
            "unit": "t",
            "confidence": 0.64,
            "reasons": ["原始排序第二"],
        },
    ]

    reranked = rerank_quota_candidates_with_agent(
        boq_code="020104",
        boq_name="主体结构钢筋",
        boq_unit="t",
        candidates=candidates,
        top_n=2,
    )

    assert reranked[0]["quota_item_id"] == 2
    assert reranked[0]["confidence"] == 0.95
    assert len(reranked) == 2
