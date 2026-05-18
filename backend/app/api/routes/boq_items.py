import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.schemas.boq_import import BoqItemCreate, BoqItemOut, BoqItemUpdate
from app.services.audit_service import write_audit_log
from app.services.code_parser import (
    segments_to_json,
    feature_text_to_json,
    build_feature_json,
)

router = APIRouter(prefix="/projects", tags=["boq-items"])


def _to_out(r: BoqItem) -> BoqItemOut:
    return BoqItemOut(
        id=r.id, project_id=r.project_id,
        code=r.code, name=r.name,
        characteristics=r.characteristics or "",
        unit=r.unit,
        quantity=r.quantity, division=r.division or "",
        sort_order=r.sort_order,
        item_ref=r.item_ref or "",
        trade_section=r.trade_section or "",
        description_en=r.description_en or "",
        rate=r.rate,
        amount=r.amount,
        remark=r.remark or "",
        code_segments_json=r.code_segments_json or "{}",
        feature_json=r.feature_json or "[]",
        calc_rule=r.calc_rule or "",
        work_content=r.work_content or "",
        is_provisional=r.is_provisional or 0,
        pricing_standard_id=r.pricing_standard_id,
    )


@router.get("/{project_id}/boq-items", response_model=list[BoqItemOut])
def list_boq_items(project_id: int, db: Session = Depends(get_db)) -> list[BoqItemOut]:
    rows = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id)
        .order_by(BoqItem.sort_order, BoqItem.id)
        .all()
    )
    return [_to_out(r) for r in rows]


@router.get("/{project_id}/boq-items/{item_id}", response_model=BoqItemOut)
def get_boq_item(project_id: int, item_id: int, db: Session = Depends(get_db)) -> BoqItemOut:
    row = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id, BoqItem.id == item_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="BOQ item not found")
    return _to_out(row)


@router.post("/{project_id}/boq-items", response_model=BoqItemOut)
def create_boq_item(
    project_id: int,
    payload: BoqItemCreate,
    db: Session = Depends(get_db),
) -> BoqItemOut:
    amount = payload.rate * payload.quantity if payload.rate else 0
    # Auto-derive structured fields from code and characteristics
    code_segs_json = segments_to_json(payload.code)
    feat_json = payload.feature_json
    if not feat_json and payload.characteristics:
        feat_json = feature_text_to_json(payload.characteristics)
    item = BoqItem(
        project_id=project_id,
        code=payload.code,
        name=payload.name,
        characteristics=payload.characteristics,
        unit=payload.unit,
        quantity=payload.quantity,
        division=payload.division,
        is_dirty=1,
        sort_order=payload.sort_order,
        item_ref=payload.item_ref,
        trade_section=payload.trade_section,
        description_en=payload.description_en,
        rate=payload.rate,
        amount=amount,
        remark=payload.remark,
        code_segments_json=code_segs_json,
        feature_json=feat_json or "[]",
        work_content=payload.work_content,
        is_provisional=payload.is_provisional,
        pricing_standard_id=payload.pricing_standard_id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    write_audit_log(
        db=db, project_id=project_id,
        action="create_boq_item", resource_type="boq_item", resource_id=item.id,
        after_json=json.dumps({"code": item.code, "name": item.name, "quantity": item.quantity}, ensure_ascii=False),
    )
    return _to_out(item)


@router.put("/{project_id}/boq-items/{item_id}", response_model=BoqItemOut)
def update_boq_item(
    project_id: int,
    item_id: int,
    payload: BoqItemUpdate,
    db: Session = Depends(get_db),
) -> BoqItemOut:
    row = db.query(BoqItem).filter(BoqItem.project_id == project_id, BoqItem.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    before = {"name": row.name, "characteristics": row.characteristics, "unit": row.unit, "quantity": row.quantity, "division": row.division}

    if payload.name is not None:
        row.name = payload.name
    if payload.characteristics is not None:
        row.characteristics = payload.characteristics
    if payload.unit is not None:
        row.unit = payload.unit
    if payload.quantity is not None:
        row.quantity = payload.quantity
    if payload.division is not None:
        row.division = payload.division
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.item_ref is not None:
        row.item_ref = payload.item_ref
    if payload.trade_section is not None:
        row.trade_section = payload.trade_section
    if payload.description_en is not None:
        row.description_en = payload.description_en
    if payload.rate is not None:
        row.rate = payload.rate
    if payload.remark is not None:
        row.remark = payload.remark
    if payload.code is not None:
        row.code = payload.code
        row.code_segments_json = segments_to_json(payload.code)
    if payload.feature_json is not None:
        row.feature_json = payload.feature_json
    elif payload.characteristics is not None:
        row.feature_json = feature_text_to_json(payload.characteristics)
    if payload.work_content is not None:
        row.work_content = payload.work_content
    if payload.is_provisional is not None:
        row.is_provisional = payload.is_provisional
    if payload.pricing_standard_id is not None:
        row.pricing_standard_id = payload.pricing_standard_id
    # Recompute amount for HK rate-based pricing
    row.amount = row.rate * row.quantity
    row.is_dirty = 1

    db.commit()
    db.refresh(row)

    after = {"name": row.name, "characteristics": row.characteristics, "unit": row.unit, "quantity": row.quantity, "division": row.division}
    write_audit_log(
        db=db, project_id=project_id,
        action="update_boq_item", resource_type="boq_item", resource_id=row.id,
        before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(after, ensure_ascii=False),
    )
    return _to_out(row)


@router.delete("/{project_id}/boq-items/{item_id}")
def delete_boq_item(
    project_id: int,
    item_id: int,
    db: Session = Depends(get_db),
):
    row = db.query(BoqItem).filter(BoqItem.project_id == project_id, BoqItem.id == item_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    before = json.dumps({"code": row.code, "name": row.name}, ensure_ascii=False)

    # Delete bindings first
    db.query(LineItemQuotaBinding).filter(LineItemQuotaBinding.boq_item_id == item_id).delete()
    db.delete(row)
    db.commit()

    write_audit_log(
        db=db, project_id=project_id,
        action="delete_boq_item", resource_type="boq_item", resource_id=item_id,
        before_json=before,
    )
    return {"ok": True}


# ── Reorder ──────────────────────────────────────────────────────

class ReorderItem(BaseModel):
    id: int
    sort_order: int

class ReorderRequest(BaseModel):
    items: list[ReorderItem]


@router.post("/{project_id}/boq-items:reorder")
def reorder_boq_items(
    project_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
):
    """Batch-update sort_order for BOQ items."""
    id_to_order = {item.id: item.sort_order for item in payload.items}
    rows = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id, BoqItem.id.in_(id_to_order.keys()))
        .all()
    )
    for row in rows:
        row.sort_order = id_to_order[row.id]
    db.commit()
    return {"ok": True, "updated": len(rows)}


# ── Batch Update ─────────────────────────────────────────────────

class BatchUpdatePayload(BaseModel):
    ids: list[int]
    division: str | None = None
    trade_section: str | None = None
    remark: str | None = None


@router.patch("/{project_id}/boq-items:batch-update")
def batch_update_boq_items(
    project_id: int,
    payload: BatchUpdatePayload,
    db: Session = Depends(get_db),
):
    """Batch-update shared fields for multiple BOQ items."""
    if not payload.ids:
        return {"ok": True, "updated": 0}
    rows = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id, BoqItem.id.in_(payload.ids))
        .all()
    )
    for row in rows:
        if payload.division is not None:
            row.division = payload.division
        if payload.trade_section is not None:
            row.trade_section = payload.trade_section
        if payload.remark is not None:
            row.remark = payload.remark
    db.commit()
    return {"ok": True, "updated": len(rows)}


# ── Batch Delete ─────────────────────────────────────────────────

class BatchDeletePayload(BaseModel):
    ids: list[int]


@router.post("/{project_id}/boq-items:batch-delete")
def batch_delete_boq_items(
    project_id: int,
    payload: BatchDeletePayload,
    db: Session = Depends(get_db),
):
    """Delete multiple BOQ items at once."""
    if not payload.ids:
        return {"ok": True, "deleted": 0}
    rows = (
        db.query(BoqItem)
        .filter(BoqItem.project_id == project_id, BoqItem.id.in_(payload.ids))
        .all()
    )
    deleted = 0
    for row in rows:
        db.query(LineItemQuotaBinding).filter(LineItemQuotaBinding.boq_item_id == row.id).delete()
        db.delete(row)
        deleted += 1
    db.commit()
    write_audit_log(
        db=db, project_id=project_id,
        action="batch_delete_boq_items", resource_type="boq_item", resource_id=None,
        after_json=json.dumps({"deleted_ids": payload.ids}, ensure_ascii=False),
    )
    return {"ok": True, "deleted": deleted}
