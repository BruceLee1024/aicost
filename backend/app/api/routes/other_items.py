"""OtherItem CRUD API + 规费明细计算.

Endpoints
---------
GET    /projects/{project_id}/other-items            — list all other items
POST   /projects/{project_id}/other-items            — create
PUT    /projects/{project_id}/other-items/{item_id}  — update
DELETE /projects/{project_id}/other-items/{item_id}  — delete
GET    /projects/{project_id}/other-items/summary    — category totals
GET    /projects/{project_id}/regulatory-fees        — 规费明细 breakdown
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.other_item import OtherItem
from app.services.labor_cost_service import calc_project_labor
from app.services.pricing_engine_v2 import FeeStructureConfig, DEFAULT_FEE_CONFIG_2013

router = APIRouter(prefix="/projects", tags=["other-items"])

# ─── Constants ───────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"provisional_sum", "provisional_price", "daywork", "gc_service"}

CATEGORY_ZH = {
    "provisional_sum": "暂列金额",
    "provisional_price": "暂估价",
    "daywork": "计日工",
    "gc_service": "总承包服务费",
}


# ─── Schemas ─────────────────────────────────────────────────────────────────

class OtherItemCreate(BaseModel):
    category: str
    sub_category: str = ""
    name: str
    unit: str = "项"
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0
    is_fixed: int = 0
    tax_mode: str = "tax"
    note: str = ""
    sort_order: int = 0


class OtherItemUpdate(BaseModel):
    category: str | None = None
    sub_category: str | None = None
    name: str | None = None
    unit: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None
    is_fixed: int | None = None
    tax_mode: str | None = None
    note: str | None = None
    sort_order: int | None = None


class OtherItemOut(BaseModel):
    id: int
    project_id: int
    category: str
    category_zh: str
    sub_category: str
    name: str
    unit: str
    quantity: float
    unit_price: float
    amount: float
    is_fixed: int
    tax_mode: str
    note: str
    sort_order: int


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _compute_amount(item: OtherItem) -> float:
    if item.is_fixed:
        return item.amount
    return round(item.quantity * item.unit_price, 2)


def _to_out(r: OtherItem) -> OtherItemOut:
    return OtherItemOut(
        id=r.id,
        project_id=r.project_id,
        category=r.category,
        category_zh=CATEGORY_ZH.get(r.category, r.category),
        sub_category=r.sub_category or "",
        name=r.name,
        unit=r.unit or "项",
        quantity=r.quantity,
        unit_price=r.unit_price,
        amount=_compute_amount(r),
        is_fixed=r.is_fixed or 0,
        tax_mode=r.tax_mode or "tax",
        note=r.note or "",
        sort_order=r.sort_order or 0,
    )


def _get_or_404(db: Session, project_id: int, item_id: int) -> OtherItem:
    row = (
        db.query(OtherItem)
        .filter(OtherItem.project_id == project_id, OtherItem.id == item_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="其他项目费条目不存在")
    return row


# ─── CRUD ────────────────────────────────────────────────────────────────────

@router.get("/{project_id}/other-items/summary")
def get_other_items_summary(project_id: int, db: Session = Depends(get_db)) -> dict:
    """Return per-category totals and grand total for 其他项目费."""
    rows = db.query(OtherItem).filter(OtherItem.project_id == project_id).all()
    totals: dict[str, float] = {cat: 0.0 for cat in VALID_CATEGORIES}
    counts: dict[str, int] = {cat: 0 for cat in VALID_CATEGORIES}
    for r in rows:
        if r.category in totals:
            totals[r.category] += _compute_amount(r)
            counts[r.category] += 1

    grand = sum(totals.values())
    return {
        "project_id": project_id,
        "grand_total": round(grand, 2),
        "categories": [
            {
                "category": cat,
                "category_zh": CATEGORY_ZH[cat],
                "total": round(totals[cat], 2),
                "count": counts[cat],
            }
            for cat in VALID_CATEGORIES
        ],
    }


@router.get("/{project_id}/other-items", response_model=list[OtherItemOut])
def list_other_items(
    project_id: int,
    category: str | None = None,
    db: Session = Depends(get_db),
) -> list[OtherItemOut]:
    q = db.query(OtherItem).filter(OtherItem.project_id == project_id)
    if category:
        q = q.filter(OtherItem.category == category)
    rows = q.order_by(OtherItem.sort_order, OtherItem.id).all()
    return [_to_out(r) for r in rows]


@router.post("/{project_id}/other-items", response_model=OtherItemOut)
def create_other_item(
    project_id: int,
    payload: OtherItemCreate,
    db: Session = Depends(get_db),
) -> OtherItemOut:
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=422,
            detail=f"无效类别 '{payload.category}'，有效值: {sorted(VALID_CATEGORIES)}",
        )
    computed = payload.amount if payload.is_fixed else round(payload.quantity * payload.unit_price, 2)
    item = OtherItem(
        project_id=project_id,
        category=payload.category,
        sub_category=payload.sub_category,
        name=payload.name,
        unit=payload.unit,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        amount=computed,
        is_fixed=payload.is_fixed,
        tax_mode=payload.tax_mode,
        note=payload.note,
        sort_order=payload.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _to_out(item)


@router.put("/{project_id}/other-items/{item_id}", response_model=OtherItemOut)
def update_other_item(
    project_id: int,
    item_id: int,
    payload: OtherItemUpdate,
    db: Session = Depends(get_db),
) -> OtherItemOut:
    row = _get_or_404(db, project_id, item_id)
    if payload.category is not None:
        if payload.category not in VALID_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"无效类别 '{payload.category}'")
        row.category = payload.category
    if payload.sub_category is not None:
        row.sub_category = payload.sub_category
    if payload.name is not None:
        row.name = payload.name
    if payload.unit is not None:
        row.unit = payload.unit
    if payload.quantity is not None:
        row.quantity = payload.quantity
    if payload.unit_price is not None:
        row.unit_price = payload.unit_price
    if payload.amount is not None:
        row.amount = payload.amount
    if payload.is_fixed is not None:
        row.is_fixed = payload.is_fixed
    if payload.tax_mode is not None:
        row.tax_mode = payload.tax_mode
    if payload.note is not None:
        row.note = payload.note
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    # Recompute amount if not fixed
    if not row.is_fixed:
        row.amount = round(row.quantity * row.unit_price, 2)
    db.commit()
    db.refresh(row)
    return _to_out(row)


@router.delete("/{project_id}/other-items/{item_id}")
def delete_other_item(
    project_id: int,
    item_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = _get_or_404(db, project_id, item_id)
    db.delete(row)
    db.commit()
    return {"deleted": True, "id": item_id}


# ─── 规费明细 breakdown ──────────────────────────────────────────────────────

@router.get("/{project_id}/regulatory-fees")
def get_regulatory_fees(
    project_id: int,
    social_insurance_rate: float = Query(0.285, description="社会保险费费率（on 人工费）"),
    housing_fund_rate: float = Query(0.08, description="住房公积金费率（on 人工费）"),
    db: Session = Depends(get_db),
) -> dict:
    """Calculate 规费 breakdown from project's BOQ labor costs.

    规费 base = 分部分项工程量清单中的人工费合计。
    For 2024 standard, the dynamic-adjusted labor fee should be applied first
    (caller should pass the adjusted base if needed).
    """
    total_labor = calc_project_labor(db, project_id)
    si = round(total_labor * social_insurance_rate, 2)
    hf = round(total_labor * housing_fund_rate, 2)
    total = round(si + hf, 2)

    return {
        "project_id": project_id,
        "labor_base": total_labor,
        "social_insurance_rate": social_insurance_rate,
        "housing_fund_rate": housing_fund_rate,
        "social_insurance_fee": si,
        "housing_fund_fee": hf,
        "regulatory_fee_total": total,
        "breakdown": [
            {"name": "社会保险费", "rate": social_insurance_rate, "base": total_labor, "amount": si},
            {"name": "住房公积金", "rate": housing_fund_rate, "base": total_labor, "amount": hf},
        ],
        "provenance": {
            "formula": "规费 = 社会保险费 + 住房公积金 = 人工费合计 × (社保费率 + 公积金费率)",
            "standard": "GB50500-2013/GBT50500-2024",
        },
    }
