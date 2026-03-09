from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.boq_import import BoqImportResult, BoqItemOut
from app.schemas.quota import QuotaImportResult, QuotaItemOut
from app.services.boq_import_service import parse_and_import
from app.services.quota_import_service import parse_and_import_quota, parse_and_import_resource_details

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/boq", response_model=BoqImportResult)
async def import_boq(
    project_id: int = Query(..., description="Target project ID"),
    file: UploadFile = File(..., description="Excel (.xlsx) BOQ file"),
    db: Session = Depends(get_db),
) -> BoqImportResult:
    """Import a Bill of Quantities from an Excel file."""
    contents = await file.read()
    stats = parse_and_import(file_bytes=contents, project_id=project_id, db=db)
    items_out = [
        BoqItemOut(
            id=item.id,
            project_id=item.project_id,
            code=item.code,
            name=item.name,
            unit=item.unit,
            quantity=item.quantity,
        )
        for item in stats.items
    ]
    return BoqImportResult(imported=stats.imported, skipped=stats.skipped, items=items_out)


@router.post("/quota", response_model=QuotaImportResult)
async def import_quota(
    file: UploadFile = File(..., description="Excel (.xlsx) quota file"),
    db: Session = Depends(get_db),
) -> QuotaImportResult:
    """Import quota items from an Excel file."""
    contents = await file.read()
    stats = parse_and_import_quota(file_bytes=contents, db=db)
    items_out = [
        QuotaItemOut(
            id=item.id,
            quota_code=item.quota_code,
            name=item.name,
            unit=item.unit,
            labor_qty=item.labor_qty,
            material_qty=item.material_qty,
            machine_qty=item.machine_qty,
        )
        for item in stats.items
    ]
    return QuotaImportResult(imported=stats.imported, skipped=stats.skipped, items=items_out)


@router.post("/quota-resource-details")
async def import_quota_resource_details(
    file: UploadFile = File(..., description="Excel (.xlsx) quota resource detail file"),
    db: Session = Depends(get_db),
):
    """Import quota resource details (人材机明细) from an Excel file."""
    contents = await file.read()
    stats = parse_and_import_resource_details(file_bytes=contents, db=db)
    return {
        "imported": stats.imported,
        "skipped": stats.skipped,
        "quotas_updated": stats.quotas_updated,
    }
