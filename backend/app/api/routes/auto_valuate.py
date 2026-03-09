"""One-click auto quota matching + binding + calculation endpoint.

Performs all matching in-memory to avoid SQLite lock contention,
then writes bindings in a single short transaction.
"""

import json
import logging
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.schemas.calc_result import LineCalcResultOut, ProjectCalcSummary
from app.services.project_calc_service import run_project_calculation
from app.services.quota_match_service import _name_similarity, _units_compatible
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)

router = APIRouter(tags=["auto-valuate"])


class MatchDetail(BaseModel):
    boq_item_id: int
    boq_code: str
    boq_name: str
    quota_item_id: int | None = None
    quota_code: str = ""
    quota_name: str = ""
    confidence: float = 0.0
    status: str = "matched"  # matched | skipped


class AutoValuateResponse(BaseModel):
    total_items: int
    already_bound: int
    newly_matched: int
    skipped: int
    match_details: list[MatchDetail]
    calc_summary: ProjectCalcSummary | None = None


@dataclass
class _QuotaRow:
    id: int
    quota_code: str
    name: str
    unit: str


def _match_in_memory(
    boq_name: str,
    boq_unit: str,
    boq_code: str,
    quotas: list[_QuotaRow],
) -> tuple[_QuotaRow | None, float]:
    """Find best quota match entirely in memory. Returns (best_quota, confidence)."""
    best: _QuotaRow | None = None
    best_score = 0.0

    for q in quotas:
        score = 0.0
        name_sim = _name_similarity(boq_name, q.name)
        score += name_sim * 0.55
        if _units_compatible(boq_unit, q.unit):
            score += 0.30
        score = min(score, 1.0)
        if score > best_score:
            best_score = score
            best = q

    return best, round(best_score, 3)


@router.post(
    "/projects/{project_id}/auto-valuate",
    response_model=AutoValuateResponse,
)
def auto_valuate(
    project_id: int,
    db: Session = Depends(get_db),
) -> AutoValuateResponse:
    """AI auto quota-match + bind + calculate in one call.

    Phase 1: Load all data into memory, match in-memory (no DB writes).
    Phase 2: Write bindings in a single short transaction.
    Phase 3: Run calculation.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # ── Read phase (single read transaction) ──
    boq_items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
    boq_ids = [b.id for b in boq_items]

    existing_bindings: set[int] = set()
    if boq_ids:
        existing_bindings = {
            row.boq_item_id
            for row in db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
            .all()
        }

    quota_rows = [
        _QuotaRow(id=q.id, quota_code=q.quota_code, name=q.name, unit=q.unit)
        for q in db.query(QuotaItem).all()
    ]

    unbound_items = [b for b in boq_items if b.id not in existing_bindings]

    # ── Match phase (pure in-memory, no DB access) ──
    match_details: list[MatchDetail] = []
    bindings_to_create: list[tuple[int, int]] = []  # (boq_id, quota_id)
    newly_matched = 0
    skipped = 0

    for boq in unbound_items:
        best, confidence = _match_in_memory(
            boq_name=boq.name,
            boq_unit=boq.unit,
            boq_code=boq.code,
            quotas=quota_rows,
        )
        if best and confidence >= 0.3:
            bindings_to_create.append((boq.id, best.id))
            newly_matched += 1
            match_details.append(MatchDetail(
                boq_item_id=boq.id,
                boq_code=boq.code,
                boq_name=boq.name,
                quota_item_id=best.id,
                quota_code=best.quota_code,
                quota_name=best.name,
                confidence=confidence,
                status="matched",
            ))
        else:
            skipped += 1
            match_details.append(MatchDetail(
                boq_item_id=boq.id,
                boq_code=boq.code,
                boq_name=boq.name,
                status="skipped",
            ))

    # ── Write phase (single short transaction) ──
    try:
        for boq_id, quota_id in bindings_to_create:
            db.add(LineItemQuotaBinding(boq_item_id=boq_id, quota_item_id=quota_id))
        # Mark all matched BOQ items as dirty
        matched_boq_ids = {bid for bid, _ in bindings_to_create}
        for boq in boq_items:
            if boq.id in matched_boq_ids:
                boq.is_dirty = 1
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("auto_valuate write phase failed: %s", e)
        raise HTTPException(status_code=500, detail=f"绑定写入失败: {e}")

    # Audit log
    try:
        write_audit_log(
            db=db,
            project_id=project_id,
            action="auto_valuate",
            resource_type="project",
            resource_id=project_id,
            after_json=json.dumps(
                {"newly_matched": newly_matched, "skipped": skipped},
                ensure_ascii=False,
            ),
        )
    except Exception:
        pass

    # ── Calculation phase ──
    calc_summary_out: ProjectCalcSummary | None = None
    try:
        summary, line_results = run_project_calculation(
            project_id=project_id, db=db
        )
        lines_out = [
            LineCalcResultOut(
                boq_item_id=boq.id,
                boq_code=boq.code,
                boq_name=boq.name,
                labor_cost=result.labor_cost,
                material_cost=result.material_cost,
                machine_cost=result.machine_cost,
                direct_cost=result.direct_cost,
                management_fee=result.management_fee,
                profit=result.profit,
                regulatory_fee=result.regulatory_fee,
                pre_tax_total=result.pre_tax_total,
                tax=result.tax,
                total=result.total,
            )
            for boq, result in line_results
        ]
        calc_summary_out = ProjectCalcSummary(
            total_direct=summary.total_direct,
            total_management=summary.total_management,
            total_profit=summary.total_profit,
            total_regulatory=summary.total_regulatory,
            total_pre_tax=summary.total_pre_tax,
            total_tax=summary.total_tax,
            total_measures=summary.total_measures,
            grand_total=summary.grand_total,
            line_results=lines_out,
        )
    except Exception as e:
        logger.error("auto_valuate calc phase failed: %s", e)

    return AutoValuateResponse(
        total_items=len(boq_items),
        already_bound=len(existing_bindings),
        newly_matched=newly_matched,
        skipped=skipped,
        match_details=match_details,
        calc_summary=calc_summary_out,
    )
