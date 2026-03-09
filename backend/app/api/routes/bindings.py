import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.quota_item import QuotaItem
from app.schemas.quota import (
    BatchBindingRequest,
    BatchReplaceBindingRequest,
    BindingClearOut,
    BindingOut,
    BindingRequest,
    BindingWithQuota,
)
from app.services.audit_service import write_audit_log

router = APIRouter(tags=["bindings"])


@router.post(
    "/boq-items/{boq_item_id}/quota-binding:confirm",
    response_model=BindingOut,
)
def confirm_binding(
    boq_item_id: int,
    payload: BindingRequest,
    db: Session = Depends(get_db),
) -> BindingOut:
    """Bind a single BOQ item to a quota item (idempotent for duplicates)."""
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")
    if not db.query(QuotaItem).filter(QuotaItem.id == payload.quota_item_id).first():
        raise HTTPException(status_code=404, detail="Quota item not found")
    existing = (
        db.query(LineItemQuotaBinding)
        .filter(
            LineItemQuotaBinding.boq_item_id == boq_item_id,
            LineItemQuotaBinding.quota_item_id == payload.quota_item_id,
        )
        .first()
    )
    if existing:
        if existing.coefficient != payload.coefficient:
            existing.coefficient = payload.coefficient
            boq.is_dirty = 1
            db.commit()
            db.refresh(existing)
        return BindingOut(
            id=existing.id,
            boq_item_id=existing.boq_item_id,
            quota_item_id=existing.quota_item_id,
            coefficient=existing.coefficient,
        )

    # Mark BOQ item as dirty so incremental recalc picks it up.
    boq.is_dirty = 1

    binding = LineItemQuotaBinding(
        boq_item_id=boq_item_id,
        quota_item_id=payload.quota_item_id,
        coefficient=payload.coefficient,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)

    write_audit_log(
        db=db,
        project_id=boq.project_id,
        action="confirm_quota_binding",
        resource_type="quota_binding",
        resource_id=binding.id,
        after_json=json.dumps(
            {
                "boq_item_id": binding.boq_item_id,
                "quota_item_id": binding.quota_item_id,
                "coefficient": binding.coefficient,
            },
            ensure_ascii=False,
        ),
    )
    return BindingOut(
        id=binding.id,
        boq_item_id=binding.boq_item_id,
        quota_item_id=binding.quota_item_id,
        coefficient=binding.coefficient,
    )


@router.post(
    "/boq-items/quota-binding:batch-confirm",
    response_model=list[BindingOut],
)
def batch_confirm_bindings(
    payload: BatchBindingRequest,
    db: Session = Depends(get_db),
) -> list[BindingOut]:
    """Batch bind multiple BOQ items to quota items with duplicate protection."""
    if not payload.bindings:
        return []

    boq_ids = {entry.boq_item_id for entry in payload.bindings}
    quota_ids = {entry.quota_item_id for entry in payload.bindings}

    boq_rows = db.query(BoqItem).filter(BoqItem.id.in_(boq_ids)).all()
    boq_map = {b.id: b for b in boq_rows}
    quota_id_set = {q.id for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()}

    existing_pairs = {
        (b.boq_item_id, b.quota_item_id): b
        for b in db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
        .all()
    }
    results: list[BindingOut] = []
    for entry in payload.bindings:
        boq_id = entry.boq_item_id
        quota_id = entry.quota_item_id
        boq = boq_map.get(boq_id)
        if boq is None or quota_id not in quota_id_set:
            continue

        # Mark dirty
        boq.is_dirty = 1

        existing = existing_pairs.get((boq_id, quota_id))
        if existing:
            if existing.coefficient != entry.coefficient:
                existing.coefficient = entry.coefficient
            results.append(
                BindingOut(
                    id=existing.id,
                    boq_item_id=existing.boq_item_id,
                    quota_item_id=existing.quota_item_id,
                    coefficient=existing.coefficient,
                )
            )
            continue
        binding = LineItemQuotaBinding(
            boq_item_id=boq_id,
            quota_item_id=quota_id,
            coefficient=entry.coefficient,
        )
        db.add(binding)
        db.flush()
        existing_pairs[(boq_id, quota_id)] = binding
        results.append(
            BindingOut(
                id=binding.id,
                boq_item_id=binding.boq_item_id,
                quota_item_id=binding.quota_item_id,
                coefficient=binding.coefficient,
            )
        )
    db.commit()
    return results


@router.get(
    "/boq-items/{boq_item_id}/quota-bindings",
    response_model=list[BindingOut],
)
def list_bindings(boq_item_id: int, db: Session = Depends(get_db)) -> list[BindingOut]:
    rows = db.query(LineItemQuotaBinding).filter(LineItemQuotaBinding.boq_item_id == boq_item_id).all()
    return [
        BindingOut(
            id=r.id,
            boq_item_id=r.boq_item_id,
            quota_item_id=r.quota_item_id,
            coefficient=r.coefficient,
        )
        for r in rows
    ]


@router.get(
    "/projects/{project_id}/bindings-with-quota",
    response_model=list[BindingWithQuota],
)
def list_project_bindings_with_quota(
    project_id: int, db: Session = Depends(get_db)
) -> list[BindingWithQuota]:
    """Return all bindings for a project joined with quota item details."""
    rows = (
        db.query(LineItemQuotaBinding, QuotaItem)
        .join(BoqItem, LineItemQuotaBinding.boq_item_id == BoqItem.id)
        .join(QuotaItem, LineItemQuotaBinding.quota_item_id == QuotaItem.id)
        .filter(BoqItem.project_id == project_id)
        .all()
    )
    return [
        BindingWithQuota(
            binding_id=b.id,
            boq_item_id=b.boq_item_id,
            quota_item_id=b.quota_item_id,
            coefficient=b.coefficient,
            quota_code=q.quota_code,
            quota_name=q.name,
            quota_unit=q.unit,
            labor_qty=q.labor_qty,
            material_qty=q.material_qty,
            machine_qty=q.machine_qty,
        )
        for b, q in rows
    ]


@router.delete(
    "/boq-items/{boq_item_id}/quota-bindings/{binding_id}",
    response_model=BindingClearOut,
)
def delete_binding(
    boq_item_id: int,
    binding_id: int,
    db: Session = Depends(get_db),
) -> BindingClearOut:
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    row = (
        db.query(LineItemQuotaBinding)
        .filter(
            LineItemQuotaBinding.id == binding_id,
            LineItemQuotaBinding.boq_item_id == boq_item_id,
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Binding not found")

    before = {
        "boq_item_id": row.boq_item_id,
        "quota_item_id": row.quota_item_id,
        "coefficient": row.coefficient,
    }
    boq.is_dirty = 1
    db.delete(row)
    db.commit()

    write_audit_log(
        db=db,
        project_id=boq.project_id,
        action="delete_quota_binding",
        resource_type="quota_binding",
        resource_id=binding_id,
        before_json=json.dumps(before, ensure_ascii=False),
    )
    return BindingClearOut(boq_item_id=boq_item_id, removed=1)


@router.delete(
    "/boq-items/{boq_item_id}/quota-bindings:clear",
    response_model=BindingClearOut,
)
def clear_bindings(
    boq_item_id: int,
    db: Session = Depends(get_db),
) -> BindingClearOut:
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    rows = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq_item_id)
        .all()
    )
    if not rows:
        return BindingClearOut(boq_item_id=boq_item_id, removed=0)

    before = [
        {"binding_id": r.id, "quota_item_id": r.quota_item_id, "coefficient": r.coefficient}
        for r in rows
    ]
    removed = len(rows)
    boq.is_dirty = 1
    for r in rows:
        db.delete(r)
    db.commit()

    write_audit_log(
        db=db,
        project_id=boq.project_id,
        action="clear_quota_bindings",
        resource_type="quota_binding",
        resource_id=boq_item_id,
        before_json=json.dumps(before, ensure_ascii=False),
    )
    return BindingClearOut(boq_item_id=boq_item_id, removed=removed)


@router.post(
    "/boq-items/{boq_item_id}/quota-binding:replace",
    response_model=BindingOut,
)
def replace_binding(
    boq_item_id: int,
    payload: BindingRequest,
    db: Session = Depends(get_db),
) -> BindingOut:
    """Replace all existing bindings for one BOQ item with one target quota."""
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")
    if not db.query(QuotaItem).filter(QuotaItem.id == payload.quota_item_id).first():
        raise HTTPException(status_code=404, detail="Quota item not found")

    existing_rows = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id == boq_item_id)
        .all()
    )
    before = [
        {"binding_id": r.id, "quota_item_id": r.quota_item_id, "coefficient": r.coefficient}
        for r in existing_rows
    ]
    for r in existing_rows:
        db.delete(r)

    boq.is_dirty = 1
    binding = LineItemQuotaBinding(
        boq_item_id=boq_item_id,
        quota_item_id=payload.quota_item_id,
        coefficient=payload.coefficient,
    )
    db.add(binding)
    db.commit()
    db.refresh(binding)

    write_audit_log(
        db=db,
        project_id=boq.project_id,
        action="replace_quota_binding",
        resource_type="quota_binding",
        resource_id=binding.id,
        before_json=json.dumps(before, ensure_ascii=False),
        after_json=json.dumps(
            {
                "boq_item_id": boq_item_id,
                "quota_item_id": payload.quota_item_id,
                "coefficient": payload.coefficient,
            },
            ensure_ascii=False,
        ),
    )
    return BindingOut(
        id=binding.id,
        boq_item_id=binding.boq_item_id,
        quota_item_id=binding.quota_item_id,
        coefficient=binding.coefficient,
    )


@router.post(
    "/boq-items/quota-binding:batch-replace",
    response_model=list[BindingOut],
)
def batch_replace_bindings(
    payload: BatchReplaceBindingRequest,
    db: Session = Depends(get_db),
) -> list[BindingOut]:
    """Replace bindings in batch; each BOQ item keeps only one target quota."""
    if not payload.bindings:
        return []

    # If same BOQ item appears multiple times, keep the last instruction.
    final_target_by_boq: dict[int, tuple[int, float]] = {}
    for entry in payload.bindings:
        final_target_by_boq[entry.boq_item_id] = (entry.quota_item_id, entry.coefficient)

    boq_ids = set(final_target_by_boq.keys())
    quota_ids = {quota_id for quota_id, _ in final_target_by_boq.values()}

    boq_rows = db.query(BoqItem).filter(BoqItem.id.in_(boq_ids)).all()
    boq_map = {b.id: b for b in boq_rows}
    valid_quota_ids = {q.id for q in db.query(QuotaItem).filter(QuotaItem.id.in_(quota_ids)).all()}

    existing_rows = (
        db.query(LineItemQuotaBinding)
        .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
        .all()
    )
    existing_by_boq: dict[int, list[LineItemQuotaBinding]] = {}
    for row in existing_rows:
        existing_by_boq.setdefault(row.boq_item_id, []).append(row)

    out: list[BindingOut] = []
    for boq_id, (quota_id, coefficient) in final_target_by_boq.items():
        boq = boq_map.get(boq_id)
        if boq is None or quota_id not in valid_quota_ids:
            continue

        rows = existing_by_boq.get(boq_id, [])
        before = [
            {"binding_id": r.id, "quota_item_id": r.quota_item_id, "coefficient": r.coefficient}
            for r in rows
        ]
        for row in rows:
            db.delete(row)

        boq.is_dirty = 1
        new_binding = LineItemQuotaBinding(
            boq_item_id=boq_id,
            quota_item_id=quota_id,
            coefficient=coefficient,
        )
        db.add(new_binding)
        db.flush()
        out.append(
            BindingOut(
                id=new_binding.id,
                boq_item_id=new_binding.boq_item_id,
                quota_item_id=new_binding.quota_item_id,
                coefficient=new_binding.coefficient,
            )
        )

        write_audit_log(
            db=db,
            project_id=boq.project_id,
            action="replace_quota_binding",
            resource_type="quota_binding",
            resource_id=new_binding.id,
            before_json=json.dumps(before, ensure_ascii=False),
            after_json=json.dumps(
                {"boq_item_id": boq_id, "quota_item_id": quota_id, "coefficient": coefficient},
                ensure_ascii=False,
            ),
        )

    db.commit()
    return out
