"""Structured schema for quota candidate reranking outputs."""

from pydantic import BaseModel, ConfigDict, Field


class AIQuotaRankItem(BaseModel):
    quota_item_id: int = Field(ge=1)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list, max_length=5)

    model_config = ConfigDict(extra="forbid")


class AIQuotaRerankOutput(BaseModel):
    candidates: list[AIQuotaRankItem] = Field(default_factory=list, max_length=20)

    model_config = ConfigDict(extra="forbid")

