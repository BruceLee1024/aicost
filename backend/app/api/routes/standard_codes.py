"""Standard BOQ code lookup API (GB50500 knowledge base)."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_standard_code import BoqStandardCode

router = APIRouter(prefix="/standard-codes", tags=["standard-codes"])


class StandardCodeOut(BaseModel):
    id: int
    standard_code: str
    name: str
    standard_unit: str
    division: str
    chapter: Optional[str] = None
    measurement_rule: Optional[str] = None
    common_characteristics: Optional[str] = None

    class Config:
        from_attributes = True


class StandardCodeListResponse(BaseModel):
    total: int
    items: list[StandardCodeOut]


@router.get("", response_model=StandardCodeListResponse)
def list_standard_codes(
    q: Optional[str] = Query(None, description="Search by code or name"),
    division: Optional[str] = Query(None, description="Filter by division (分部)"),
    chapter: Optional[str] = Query(None, description="Filter by chapter"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> StandardCodeListResponse:
    """List / search standard BOQ codes."""
    query = db.query(BoqStandardCode)
    if q:
        like = f"%{q}%"
        query = query.filter(
            BoqStandardCode.standard_code.contains(q)
            | BoqStandardCode.name.contains(q)
        )
    if division:
        query = query.filter(BoqStandardCode.division == division)
    if chapter:
        query = query.filter(BoqStandardCode.chapter == chapter)

    total = query.count()
    items = query.order_by(BoqStandardCode.standard_code).offset(offset).limit(limit).all()
    return StandardCodeListResponse(
        total=total,
        items=[StandardCodeOut.model_validate(i) for i in items],
    )


@router.get("/{code}", response_model=StandardCodeOut)
def get_standard_code(
    code: str,
    db: Session = Depends(get_db),
) -> StandardCodeOut:
    """Get a single standard code by its code value."""
    row = db.query(BoqStandardCode).filter(BoqStandardCode.standard_code == code).first()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Standard code '{code}' not found")
    return StandardCodeOut.model_validate(row)
