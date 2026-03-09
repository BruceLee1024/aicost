"""Rate Suggestion Agent — suggests rates for HKSMM4 BOQ items.

Given a BOQ item's trade section, description, and project context,
suggests a reasonable rate range and recommended rate.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.ai.providers import AIProviderError, get_ai_provider
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.project import Project

logger = logging.getLogger(__name__)


@dataclass
class RateSuggestion:
    boq_item_id: int
    suggested_rate: float
    rate_low: float
    rate_high: float
    currency: str
    reasoning: str
    confidence: float


# Fallback rate ranges by trade section (HKD per unit)
_HK_RATE_RANGES: dict[str, tuple[float, float]] = {
    "Preliminaries": (0, 0),
    "Demolition": (50, 500),
    "Earthworks": (80, 600),
    "Piling": (500, 5000),
    "Concrete Work": (800, 4000),
    "Masonry": (200, 1200),
    "Structural Steelwork": (5000, 25000),
    "Waterproofing": (100, 800),
    "Roofing": (200, 1500),
    "Carpentry": (300, 2000),
    "Joinery": (500, 5000),
    "Ironmongery": (50, 2000),
    "Structural Glazing": (800, 5000),
    "Plastering": (100, 600),
    "Tiling": (200, 1200),
    "Painting": (30, 200),
    "Plumbing": (200, 3000),
    "Drainage": (300, 2000),
    "Electrical": (200, 5000),
    "Fire Services": (300, 3000),
    "HVAC": (500, 8000),
    "Lift & Escalator": (50000, 500000),
    "External Works": (100, 2000),
}


def suggest_rate(*, boq_item_id: int) -> RateSuggestion:
    """Suggest a rate for an HKSMM4 BOQ item."""
    db: Session = next(get_db())
    try:
        return _suggest(db, boq_item_id)
    finally:
        db.close()


def _suggest(db: Session, boq_item_id: int) -> RateSuggestion:
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        return RateSuggestion(
            boq_item_id=boq_item_id, suggested_rate=0, rate_low=0, rate_high=0,
            currency="HKD", reasoning="BOQ item not found", confidence=0,
        )

    project = db.query(Project).filter(Project.id == boq.project_id).first()
    currency = project.currency if project else "HKD"
    trade = boq.trade_section or ""

    # Collect historical rates from same project for context
    similar_items = (
        db.query(BoqItem)
        .filter(
            BoqItem.project_id == boq.project_id,
            BoqItem.trade_section == trade,
            BoqItem.rate > 0,
            BoqItem.id != boq.id,
        )
        .all()
    )
    hist_rates = [i.rate for i in similar_items if i.rate > 0]

    # Try AI suggestion
    ai_result = _ai_suggest(boq, trade, currency, hist_rates)
    if ai_result:
        return ai_result

    # Fallback: use trade section range
    rate_range = _HK_RATE_RANGES.get(trade, (100, 2000))
    mid = (rate_range[0] + rate_range[1]) / 2

    # Adjust with historical data if available
    if hist_rates:
        avg_hist = sum(hist_rates) / len(hist_rates)
        mid = avg_hist  # Prefer historical average
        rate_range = (min(hist_rates) * 0.8, max(hist_rates) * 1.2)

    return RateSuggestion(
        boq_item_id=boq_item_id,
        suggested_rate=round(mid, 2),
        rate_low=round(rate_range[0], 2),
        rate_high=round(rate_range[1], 2),
        currency=currency,
        reasoning=f"Based on {trade} trade section typical range"
        + (f" and {len(hist_rates)} similar items in project" if hist_rates else ""),
        confidence=0.5 if not hist_rates else 0.7,
    )


def _ai_suggest(
    boq: BoqItem, trade: str, currency: str, hist_rates: list[float],
) -> RateSuggestion | None:
    """Try AI-based rate suggestion."""
    provider = get_ai_provider()
    if not provider.is_enabled() or not provider.is_configured():
        return None

    context = {
        "trade_section": trade,
        "description": boq.description_en or boq.name,
        "unit": boq.unit,
        "quantity": boq.quantity,
        "currency": currency,
        "historical_rates": hist_rates[:10],
    }

    prompt = (
        "You are an expert Hong Kong quantity surveyor. "
        f"Suggest a unit rate for the following HKSMM4 BOQ item:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
        "Reply in JSON format:\n"
        '{"suggested_rate": <number>, "rate_low": <number>, "rate_high": <number>, '
        '"reasoning": "<brief explanation>", "confidence": <0.0-1.0>}'
    )

    try:
        text = provider.generate_text(
            task="rate_suggestion",
            messages=[
                {"role": "system", "content": "You are a Hong Kong QS rate estimation expert. Reply only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
        )

        # Parse JSON from response
        import re
        json_match = re.search(r"\{[^{}]+\}", text)
        if not json_match:
            return None
        data = json.loads(json_match.group())

        return RateSuggestion(
            boq_item_id=boq.id,
            suggested_rate=float(data.get("suggested_rate", 0)),
            rate_low=float(data.get("rate_low", 0)),
            rate_high=float(data.get("rate_high", 0)),
            currency=currency,
            reasoning=data.get("reasoning", "AI suggestion"),
            confidence=float(data.get("confidence", 0.6)),
        )
    except (AIProviderError, json.JSONDecodeError, Exception) as exc:
        logger.warning("AI rate suggestion failed: %s", exc)
        return None
