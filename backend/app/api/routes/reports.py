"""Report API — JSON report data + PDF export.

Existing Excel export lives in exports.py; this module adds:
- GET  /projects/{id}/report          → structured JSON report
- GET  /projects/{id}/report/export   → PDF download
"""

from __future__ import annotations

import io
import json
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.calc_result import CalcResult
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.models.quota_item import QuotaItem

router = APIRouter(tags=["reports"])


# ── Schemas ──


class DivisionRow(BaseModel):
    division: str
    item_count: int
    bound_count: int
    total_cost: float
    percentage: str


class LineItemRow(BaseModel):
    boq_item_id: int
    code: str
    name: str
    unit: str
    quantity: float
    division: str
    unit_price: float | None
    total_cost: float | None
    is_bound: bool
    quota_count: int


class CostSummary(BaseModel):
    total_direct: float = 0
    total_management: float = 0
    total_profit: float = 0
    total_regulatory: float = 0
    total_tax: float = 0
    total_measures: float = 0
    grand_total: float = 0


class ProjectInfo(BaseModel):
    id: int
    name: str
    region: str
    project_type: str
    standard_type: str
    currency: str


class ReportResponse(BaseModel):
    project: ProjectInfo
    statistics: dict
    cost_summary: CostSummary
    divisions: list[DivisionRow]
    line_items: list[LineItemRow]
    generated_at: str


# ── JSON report endpoint ──


@router.get("/projects/{project_id}/report", response_model=ReportResponse)
def get_report(
    project_id: int,
    division: str | None = Query(None, description="按分部筛选"),
    search: str | None = Query(None, description="按名称/编码搜索"),
    db: Session = Depends(get_db),
) -> ReportResponse:
    """Return a structured valuation report as JSON."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    items = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id)
        .order_by(BoqItem.sort_order)
        .all()
    )
    boq_ids = [i.id for i in items]

    # Bindings
    all_bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
        .all()
    ) if boq_ids else []
    binding_count_map: dict[int, int] = defaultdict(int)
    for b in all_bindings:
        binding_count_map[b.boq_item_id] += 1

    # Calc results
    calc_map = {}
    if boq_ids:
        for c in db.query(CalcResult).filter(CalcResult.boq_item_id.in_(boq_ids)).all():
            calc_map[c.boq_item_id] = c

    # Cost summary
    cost_summary = CostSummary()
    try:
        from app.services.project_calc_service import run_project_calculation
        summary, _ = run_project_calculation(project_id=project_id, db=db)
        cost_summary = CostSummary(
            total_direct=summary.total_direct,
            total_management=summary.total_management,
            total_profit=summary.total_profit,
            total_regulatory=summary.total_regulatory,
            total_tax=summary.total_tax,
            total_measures=summary.total_measures,
            grand_total=summary.grand_total,
        )
    except Exception:
        cost_summary.grand_total = sum(c.total_cost or 0 for c in calc_map.values())

    # Line items — with optional division/search filtering
    line_items = []
    for item in items:
        item_div = item.division or "未分类"
        if division and item_div != division:
            continue
        if search:
            kw = search.lower()
            if kw not in item.name.lower() and kw not in item.code.lower():
                continue
        c = calc_map.get(item.id)
        bc = binding_count_map.get(item.id, 0)
        total = round(c.total_cost, 2) if c else None
        up = round(c.total_cost / item.quantity, 2) if c and item.quantity else None
        line_items.append(LineItemRow(
            boq_item_id=item.id,
            code=item.code,
            name=item.name,
            unit=item.unit,
            quantity=item.quantity,
            division=item_div,
            unit_price=up,
            total_cost=total,
            is_bound=bc > 0,
            quota_count=bc,
        ))

    # Division breakdown
    div_data: dict[str, dict] = defaultdict(lambda: {"count": 0, "bound": 0, "total": 0.0})
    for li in line_items:
        d = div_data[li.division]
        d["count"] += 1
        if li.is_bound:
            d["bound"] += 1
        d["total"] += li.total_cost or 0

    grand = cost_summary.grand_total or 1
    divisions = [
        DivisionRow(
            division=k,
            item_count=v["count"],
            bound_count=v["bound"],
            total_cost=round(v["total"], 2),
            percentage=f"{round(v['total'] / grand * 100, 1)}%",
        )
        for k, v in sorted(div_data.items(), key=lambda x: -x[1]["total"])
    ]

    bound_count = sum(1 for li in line_items if li.is_bound)
    return ReportResponse(
        project=ProjectInfo(
            id=project.id,
            name=project.name,
            region=project.region,
            project_type=project.project_type,
            standard_type=project.standard_type,
            currency=project.currency,
        ),
        statistics={
            "total_items": len(items),
            "bound_count": bound_count,
            "unbound_count": len(items) - bound_count,
            "binding_rate": f"{bound_count / len(items) * 100:.1f}%" if items else "0%",
            "calculated_items": len(calc_map),
        },
        cost_summary=cost_summary,
        divisions=divisions,
        line_items=line_items,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ── PDF export ──


@router.get("/projects/{project_id}/report/export")
def export_report(
    project_id: int,
    format: str = Query("pdf", description="Export format: pdf | excel | docx"),
    narrative: bool = Query(
        False,
        description="Sprint 9 Phase 4: include AI-generated executive narrative (docx only)",
    ),
    db: Session = Depends(get_db),
):
    """Export a valuation report as PDF, Excel, or Word."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    fmt = (format or "pdf").lower()

    if fmt == "excel":
        from app.services.export_service import export_valuation_report
        file_bytes = export_valuation_report(project_id=project_id, db=db)
        filename = f"valuation_report_{project.name}_{project_id}.xlsx"
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if fmt == "pdf":
        from app.services.report_export_service import export_valuation_pdf
        file_bytes = export_valuation_pdf(project_id=project_id, db=db)
        filename = f"valuation_report_{project.name}_{project_id}.pdf"
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    if fmt in ("docx", "word"):
        from app.services.report_docx_service import export_valuation_docx

        narrative_text: str | None = None
        if narrative:
            try:
                from app.services.report_narrative_service import generate_narrative

                narrative_text = generate_narrative(project_id, db)
            except Exception:  # pragma: no cover — defensive
                narrative_text = None

        file_bytes = export_valuation_docx(
            project_id=project_id, db=db, narrative=narrative_text
        )
        filename = f"valuation_report_{project.name}_{project_id}.docx"
        return StreamingResponse(
            io.BytesIO(file_bytes),
            media_type=(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
