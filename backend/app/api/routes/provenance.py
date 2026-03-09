from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.agents.insight_agent import generate_insight
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.calc_result import CalcResult
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.models.quota_item import QuotaItem
from app.schemas.provenance import (
    BindingRef,
    CalcBreakdown,
    CalcProvenance,
    PriceSnapshot,
    QuotaRef,
)
from app.services.pricing_engine import _r2, calculate_line_item
from app.services.project_calc_service import (
    _compose_quota_quantities,
    _lookup_price,
    _resolve_fee_config,
)

router = APIRouter(tags=["provenance"])


@router.get(
    "/calc-results/{boq_item_id}/provenance",
    response_model=CalcProvenance,
)
def get_provenance(
    boq_item_id: int,
    db: Session = Depends(get_db),
) -> CalcProvenance:
    """Return full provenance for a BOQ item's calculation result."""
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    bindings = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq_item_id)
        .all()
    )
    project = db.query(Project).filter(Project.id == boq.project_id).first()
    project_region = project.region if project else ""
    fee_config = _resolve_fee_config(project_id=boq.project_id, db=db)
    labor_price = _lookup_price(db, category="人工费", region=project_region)
    material_price = _lookup_price(db, category="材料费", region=project_region)
    machine_price = _lookup_price(db, category="机械费", region=project_region)

    quota_ids = {b.quota_item_id for b in bindings}
    quota_by_id = {
        q.id: q for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()
    } if quota_ids else {}

    binding_refs: list[BindingRef] = []
    for b in bindings:
        q = quota_by_id.get(b.quota_item_id)
        if q:
            binding_direct_cost = _r2(
                (
                    q.labor_qty * labor_price
                    + q.material_qty * material_price
                    + q.machine_qty * machine_price
                )
                * boq.quantity
                * b.coefficient
            )
            binding_refs.append(
                BindingRef(
                    binding_id=b.id,
                    coefficient=b.coefficient,
                    direct_cost=binding_direct_cost,
                    quota=QuotaRef(
                        quota_code=q.quota_code,
                        quota_name=q.name,
                        unit=q.unit,
                        labor_qty=q.labor_qty,
                        material_qty=q.material_qty,
                        machine_qty=q.machine_qty,
                    ),
                )
            )

    composed_result = None
    if bindings:
        labor_qty, material_qty, machine_qty = _compose_quota_quantities(bindings, quota_by_id)
        if labor_qty or material_qty or machine_qty:
            composed_result = calculate_line_item(
                labor_qty=labor_qty,
                labor_price=labor_price,
                material_qty=material_qty,
                material_price=material_price,
                machine_qty=machine_qty,
                machine_price=machine_price,
                quantity=boq.quantity,
                fee_config=fee_config,
            )

    calc = db.query(CalcResult).filter(CalcResult.boq_item_id == boq_item_id).first()
    calc_total = calc.total_cost if calc else (composed_result.total if composed_result else None)
    unit_price = _r2(calc_total / boq.quantity) if calc_total is not None and boq.quantity > 0 else None

    explanation_parts = [
        f"清单项 [{boq.code}] {boq.name}，数量 {boq.quantity} {boq.unit}。",
    ]
    if binding_refs:
        explanation_parts.append(
            f"共绑定 {len(binding_refs)} 条定额，按系数组合计算。"
        )
    else:
        explanation_parts.append("⚠ 尚未绑定定额。")

    if calc_total is not None:
        explanation_parts.append(f"计算结果合计：{calc_total} 元。")
    else:
        explanation_parts.append("⚠ 尚未执行计算。")

    # Try AI-enhanced explanation
    static_explanation = " ".join(explanation_parts)
    ai_explanation = generate_insight(
        context_type="provenance",
        context_data={
            "boq_code": boq.code,
            "boq_name": boq.name,
            "boq_unit": boq.unit,
            "boq_quantity": boq.quantity,
            "bindings": [
                {
                    "quota_code": br.quota.quota_code,
                    "quota_name": br.quota.quota_name,
                    "coefficient": br.coefficient,
                    "labor_qty": br.quota.labor_qty,
                    "material_qty": br.quota.material_qty,
                    "machine_qty": br.quota.machine_qty,
                }
                for br in binding_refs
            ],
            "calc_total": calc_total,
            "unit_price": unit_price,
        },
    )

    return CalcProvenance(
        boq_item_id=boq.id,
        boq_code=boq.code,
        boq_name=boq.name,
        boq_unit=boq.unit,
        boq_quantity=boq.quantity,
        bindings=binding_refs,
        price_snapshot=PriceSnapshot(
            labor_price=labor_price,
            material_price=material_price,
            machine_price=machine_price,
        ),
        calc_breakdown=(
            CalcBreakdown(
                direct_cost=composed_result.direct_cost,
                management_fee=composed_result.management_fee,
                profit=composed_result.profit,
                regulatory_fee=composed_result.regulatory_fee,
                pre_tax_total=composed_result.pre_tax_total,
                tax=composed_result.tax,
                total=composed_result.total,
            )
            if composed_result
            else None
        ),
        unit_price=unit_price,
        calc_total=calc_total,
        fee_config_snapshot=asdict(fee_config),
        explanation=ai_explanation or static_explanation,
    )
