from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.quota_item import QuotaItem
from app.services.quota_import_2024 import import_quota_excel, seed_quota_items

router = APIRouter(tags=["quota-items"])


def _quota_out(it: QuotaItem, detailed: bool = False) -> dict:
    base = {
        "id": it.id,
        "quota_code": it.quota_code,
        "name": it.name,
        "unit": it.unit,
        "chapter": it.chapter,
        "labor_qty": it.labor_qty,
        "material_qty": it.material_qty,
        "machine_qty": it.machine_qty,
        "labor_fee": it.labor_fee,
        "material_fee": it.material_fee,
        "machine_fee": it.machine_fee,
        "base_price": it.base_price,
        "version": it.version,
        "profession": it.profession,
        "region": it.region,
        "pricing_standard_id": it.pricing_standard_id,
    }
    if detailed:
        base["work_content"] = it.work_content
        base["applicable_scope"] = it.applicable_scope
        base["conversion_rules_json"] = it.conversion_rules_json
        base["unit_constraint_json"] = it.unit_constraint_json
    return base


@router.get("/quota-items")
def list_quota_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    chapter: str | None = None,
    keyword: str | None = None,
    profession: str | None = None,
    standard_code: str | None = None,
    detailed: bool = Query(False),
    db: Session = Depends(get_db),
):
    q = db.query(QuotaItem)
    if chapter:
        q = q.filter(QuotaItem.chapter == chapter)
    if keyword:
        q = q.filter(QuotaItem.name.contains(keyword))
    if profession:
        q = q.filter(QuotaItem.profession == profession)
    if standard_code:
        from app.models.pricing_standard import PricingStandard
        std = db.query(PricingStandard).filter(PricingStandard.code == standard_code).first()
        if std:
            q = q.filter(QuotaItem.pricing_standard_id == std.id)
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return {
        "total": total,
        "items": [_quota_out(it, detailed) for it in items],
    }


@router.get("/quota-items/stats")
def quota_stats(db: Session = Depends(get_db)):
    total = db.query(QuotaItem).count()
    chapters = (
        db.query(QuotaItem.chapter, func.count())
        .group_by(QuotaItem.chapter)
        .order_by(func.count().desc())
        .all()
    )
    return {
        "total": total,
        "chapters": [{"chapter": ch, "count": n} for ch, n in chapters],
    }


@router.get("/quota-items/{quota_id}")
def get_quota_item(quota_id: int, db: Session = Depends(get_db)):
    it = db.query(QuotaItem).filter(QuotaItem.id == quota_id).first()
    if not it:
        raise HTTPException(status_code=404, detail="定额子目不存在")
    return _quota_out(it, detailed=True)


@router.post("/quota-items/import-2024")
async def import_quota_2024(
    file: UploadFile = File(...),
    standard_code: str = Query("GBT50500-2024"),
    profession: str = Query("房建"),
    region: str = Query("全国"),
    upsert: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Upload a 2024 housing-construction quota Excel (.xlsx) file."""
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")
    content = await file.read()
    result = import_quota_excel(
        file_bytes=content,
        db=db,
        standard_code=standard_code,
        profession=profession,
        region=region,
        upsert=upsert,
    )
    return {
        "imported": result.imported,
        "updated": result.updated,
        "skipped": result.skipped,
        "errors": result.errors,
    }
