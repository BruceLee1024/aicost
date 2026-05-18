"""Shared labor cost calculation service.

Replaces the N+1+M query loop (boq → bindings → quota) that was duplicated
in both the OtherItem API route and the compliance agent tools.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem


def calc_project_labor(db: Session, project_id: int) -> float:
    """Return total adjusted labor fee for a project's BOQ-quota bindings.

    Uses a single JOIN query instead of nested per-row queries.
    Falls back to ``labor_qty × 80`` (人工工日单价) for 2013-style records
    that have no ``labor_fee`` set.
    """
    rows = (
        db.query(
            BoqItem.quantity,
            LineItemQuotaBinding.coefficient,
            QuotaItem.labor_fee,
            QuotaItem.labor_qty,
        )
        .join(LineItemQuotaBinding, LineItemQuotaBinding.boq_item_id == BoqItem.id)
        .join(QuotaItem, QuotaItem.id == LineItemQuotaBinding.quota_item_id)
        .filter(BoqItem.project_id == project_id)
        .all()
    )

    total = 0.0
    for qty, coef, labor_fee, labor_qty in rows:
        coef = coef or 1.0
        per_unit = (labor_fee * coef) if labor_fee else ((labor_qty or 0.0) * 80.0 * coef)
        total += per_unit * (qty or 0.0)

    return round(total, 2)
