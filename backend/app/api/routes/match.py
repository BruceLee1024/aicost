from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.schemas.match import MatchCandidateOut
from app.services.quota_match_service import find_candidates

router = APIRouter(tags=["match"])


@router.post(
    "/boq-items/{boq_item_id}/quota-candidates",
    response_model=list[MatchCandidateOut],
)
def get_quota_candidates(
    boq_item_id: int,
    top_n: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> list[MatchCandidateOut]:
    """AI-powered quota matching: return top-N candidates with confidence and reasons."""
    boq = db.query(BoqItem).filter(BoqItem.id == boq_item_id).first()
    if not boq:
        raise HTTPException(status_code=404, detail="BOQ item not found")

    candidates = find_candidates(boq_item_id=boq_item_id, db=db, top_n=top_n)
    return [
        MatchCandidateOut(
            quota_item_id=c.quota_item_id,
            quota_code=c.quota_code,
            quota_name=c.quota_name,
            unit=c.unit,
            confidence=c.confidence,
            reasons=c.reasons,
        )
        for c in candidates
    ]
