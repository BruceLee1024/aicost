"""Enhanced AI endpoints: batch review, coefficient suggestion, rate suggestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem
from app.services.validation_service import normalize_unit

router = APIRouter(tags=["ai-enhanced"])


# ── Schemas ───────────────────────────────────────────────────────


class ReviewIssueOut(BaseModel):
    boq_item_id: int
    boq_code: str
    boq_name: str
    severity: str
    issue_type: str
    message: str
    suggestion: str


class BatchReviewResponse(BaseModel):
    project_id: int
    total_items: int
    bound_count: int
    unbound_count: int
    issues: list[ReviewIssueOut]
    ai_summary: str | None = None
    error: str | None = None


class CoeffSuggestion(BaseModel):
    binding_id: int | None = None
    quota_code: str
    quota_name: str
    current_coefficient: float
    suggested_coefficient: float
    reasoning: str


class CoeffSuggestResponse(BaseModel):
    boq_item_id: int
    suggestions: list[CoeffSuggestion]


class RateSuggestionOut(BaseModel):
    boq_item_id: int
    suggested_rate: float
    rate_low: float
    rate_high: float
    currency: str
    reasoning: str
    confidence: float


# ── Batch Review ──────────────────────────────────────────────────


@router.post(
    "/projects/{project_id}/ai-batch-review",
    response_model=BatchReviewResponse,
)
def ai_batch_review(project_id: int) -> BatchReviewResponse:
    """Run AI batch review on all project bindings."""
    from app.ai.agents.batch_review_agent import run_batch_review

    result = run_batch_review(project_id=project_id)
    return BatchReviewResponse(
        project_id=result.project_id,
        total_items=result.total_items,
        bound_count=result.bound_count,
        unbound_count=result.unbound_count,
        issues=[
            ReviewIssueOut(
                boq_item_id=i.boq_item_id,
                boq_code=i.boq_code,
                boq_name=i.boq_name,
                severity=i.severity,
                issue_type=i.issue_type,
                message=i.message,
                suggestion=i.suggestion,
            )
            for i in result.issues
        ],
        ai_summary=result.ai_summary,
        error=result.error,
    )


# ── Coefficient Suggestion ────────────────────────────────────────


@router.post(
    "/boq-items/{boq_item_id}/suggest-coefficients",
    response_model=CoeffSuggestResponse,
)
def suggest_coefficients(
    boq_item_id: int,
    db: Session = Depends(get_db),
) -> CoeffSuggestResponse:
    """Suggest coefficients for bindings based on BOQ characteristics."""
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        return CoeffSuggestResponse(boq_item_id=boq_item_id, suggestions=[])

    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq_item_id)
        .all()
    )
    if not bindings:
        return CoeffSuggestResponse(boq_item_id=boq_item_id, suggestions=[])

    suggestions: list[CoeffSuggestion] = []
    for b in bindings:
        q = db.query(QuotaItem).filter(QuotaItem.id == b.quota_item_id).first()
        if not q:
            continue

        coeff = b.coefficient
        reasoning = ""

        # Rule-based coefficient suggestion
        boq_unit_norm = normalize_unit(boq.unit)
        quota_unit_norm = normalize_unit(q.unit)

        if boq_unit_norm != quota_unit_norm:
            # Unit conversion suggestions
            unit_conversions = {
                ("m", "m2"): ("线性→面积，可能需要乘以宽度", 1.0),
                ("m2", "m3"): ("面积→体积，可能需要乘以厚度", 0.1),
                ("m3", "m2"): ("体积→面积，可能需要乘以厚度系数", 10.0),
                ("t", "kg"): ("吨→千克换算", 1000.0),
                ("kg", "t"): ("千克→吨换算", 0.001),
            }
            key = (boq_unit_norm, quota_unit_norm)
            if key in unit_conversions:
                reasoning, coeff = unit_conversions[key]
            else:
                reasoning = f"单位不一致({boq.unit}→{q.unit}），需确认换算系数"
                coeff = 1.0
        else:
            # Same unit, check characteristics for common adjustments
            chars = (boq.characteristics or "").lower()
            if "高层" in chars or "超高" in chars:
                coeff = 1.15
                reasoning = "高层施工，建议系数 1.15"
            elif "地下" in chars or "深基" in chars:
                coeff = 1.10
                reasoning = "地下施工，建议系数 1.10"
            elif "c50" in chars or "c60" in chars:
                coeff = 1.05
                reasoning = "高强混凝土，建议系数 1.05"
            else:
                coeff = 1.0
                reasoning = "标准工况，系数 1.0"

        suggestions.append(CoeffSuggestion(
            binding_id=b.id,
            quota_code=q.quota_code,
            quota_name=q.name,
            current_coefficient=b.coefficient,
            suggested_coefficient=round(coeff, 4),
            reasoning=reasoning,
        ))

    # Try AI enhancement
    _enhance_with_ai(boq, suggestions)

    return CoeffSuggestResponse(
        boq_item_id=boq_item_id,
        suggestions=suggestions,
    )


def _enhance_with_ai(boq: BoqItem, suggestions: list[CoeffSuggestion]) -> None:
    """Try to enhance suggestions with AI reasoning."""
    from app.ai.providers import AIProviderError, get_ai_provider
    import json

    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return

    context = {
        "boq_name": boq.name,
        "boq_characteristics": boq.characteristics or "",
        "boq_unit": boq.unit,
        "bindings": [
            {"quota_code": s.quota_code, "quota_name": s.quota_name, "current": s.current_coefficient}
            for s in suggestions
        ],
    }

    try:
        text = provider.generate_text(
            task="coeff_suggestion",
            messages=[
                {"role": "system", "content": "你是工程计价系数建议助手。根据清单特征和定额信息，给出系数调整建议。只回复简洁的理由。"},
                {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
            ],
        )
        # Append AI reasoning to the last suggestion
        if suggestions and text:
            suggestions[-1].reasoning += f" | AI: {text[:200]}"
    except AIProviderError:
        pass


# ── Rate Suggestion (HKSMM4) ─────────────────────────────────────


@router.post(
    "/boq-items/{boq_item_id}/suggest-rate",
    response_model=RateSuggestionOut,
)
def suggest_rate_endpoint(boq_item_id: int) -> RateSuggestionOut:
    """Suggest a rate for an HKSMM4 BOQ item."""
    from app.ai.agents.rate_suggestion_agent import suggest_rate

    result = suggest_rate(boq_item_id=boq_item_id)
    return RateSuggestionOut(
        boq_item_id=result.boq_item_id,
        suggested_rate=result.suggested_rate,
        rate_low=result.rate_low,
        rate_high=result.rate_high,
        currency=result.currency,
        reasoning=result.reasoning,
        confidence=result.confidence,
    )
