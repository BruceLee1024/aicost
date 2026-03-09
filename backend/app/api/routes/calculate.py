from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.calc_result import CalcResult
from app.models.project import Project
from app.schemas.calc_result import LineCalcResultOut, ProjectCalcSummary
from app.schemas.calculate import CalculateRequest, CalculateResponse
from app.services.pricing_engine import calculate_line_item_total
from app.services.project_calc_service import run_project_calculation

router = APIRouter(tags=["calculate"])


# --- Lightweight read-only cached summary ----------------------------------

@router.get("/projects/{project_id}/calc-summary", response_model=ProjectCalcSummary)
def get_calc_summary(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectCalcSummary:
    """Return cached calculation totals without re-running the calculation."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    rows = (
        db.query(CalcResult, BoqItem)
        .join(BoqItem, CalcResult.boq_item_id == BoqItem.id)
        .filter(BoqItem.project_id == project_id)
        .all()
    )

    grand_total = sum(r.CalcResult.total_cost for r in rows)

    line_results = [
        LineCalcResultOut(
            boq_item_id=r.CalcResult.boq_item_id,
            boq_code=r.BoqItem.code,
            boq_name=r.BoqItem.name,
            labor_cost=0, material_cost=0, machine_cost=0,
            direct_cost=r.CalcResult.total_cost,
            management_fee=0, profit=0, regulatory_fee=0,
            pre_tax_total=r.CalcResult.total_cost,
            tax=0, total=r.CalcResult.total_cost,
        )
        for r in rows
    ]

    return ProjectCalcSummary(
        total_direct=0, total_management=0, total_profit=0,
        total_regulatory=0, total_pre_tax=0, total_tax=0,
        total_measures=0, grand_total=grand_total,
        line_results=line_results,
    )


# --- Legacy simple endpoint (kept for quick testing) -----------------------

@router.post("/calculate/run", response_model=CalculateResponse)
def run_calculate(payload: CalculateRequest) -> CalculateResponse:
    total = calculate_line_item_total(
        labor_qty=payload.labor_qty,
        labor_price=payload.labor_price,
        material_qty=payload.material_qty,
        material_price=payload.material_price,
        machine_qty=payload.machine_qty,
        machine_price=payload.machine_price,
    )
    return CalculateResponse(total=total, currency="CNY")


# --- Real project calculation ----------------------------------------------

@router.post("/projects/{project_id}/calculate", response_model=ProjectCalcSummary)
def calculate_project(
    project_id: int,
    db: Session = Depends(get_db),
) -> ProjectCalcSummary:
    """Run full calculation for all bound BOQ items in a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    summary, line_results = run_project_calculation(project_id=project_id, db=db)

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

    return ProjectCalcSummary(
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
