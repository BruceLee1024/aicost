"""HTTP API for the enterprise quota library + precipitation candidates."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.enterprise_quota import (
    AnalyzeResult,
    CandidateListResponse,
    CandidateOut,
    DismissCandidateRequest,
    EnterpriseQuotaCreate,
    EnterpriseQuotaListResponse,
    EnterpriseQuotaOut,
    EnterpriseQuotaStats,
    EnterpriseQuotaUpdate,
    PromoteCandidateRequest,
    ReviewAction,
    SubmitForReview,
)
from app.services import enterprise_quota_precipitation_service as precip
from app.services import enterprise_quota_service as svc

router = APIRouter(prefix="/enterprise-quota", tags=["enterprise-quota"])


# ─── List / stats ────────────────────────────────────────────────────


@router.get("/stats", response_model=EnterpriseQuotaStats)
def get_stats(db: Session = Depends(get_db)) -> EnterpriseQuotaStats:
    return EnterpriseQuotaStats(**svc.stats(db))


@router.get("", response_model=EnterpriseQuotaListResponse)
def list_items(
    status: str | None = None,
    source_type: str | None = None,
    keyword: str | None = None,
    profession: str | None = None,
    chapter: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaListResponse:
    total, rows = svc.list_items(
        db,
        status=status, source_type=source_type, keyword=keyword,
        profession=profession, chapter=chapter,
        skip=skip, limit=limit,
    )
    return EnterpriseQuotaListResponse(
        total=total,
        items=[EnterpriseQuotaOut(**svc.to_out_dict(it)) for it in rows],
    )


@router.post("", response_model=EnterpriseQuotaOut)
def create_item(
    payload: EnterpriseQuotaCreate,
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.create_item(db, data=payload.model_dump())
    except svc.DuplicateQuotaCodeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except svc.EnterpriseQuotaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.get("/{item_id}", response_model=EnterpriseQuotaOut)
def get_one(item_id: int, db: Session = Depends(get_db)) -> EnterpriseQuotaOut:
    try:
        item = svc.get_item(db, item_id=item_id)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.put("/{item_id}", response_model=EnterpriseQuotaOut)
def update_item(
    item_id: int,
    payload: EnterpriseQuotaUpdate,
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.update_item(
            db, item_id=item_id, data=payload.model_dump(exclude_unset=True),
        )
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    try:
        svc.delete_item(db, item_id=item_id)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return {"deleted": True}


# ─── Workflow transitions ────────────────────────────────────────────


@router.post("/{item_id}/submit", response_model=EnterpriseQuotaOut)
def submit_for_review(
    item_id: int,
    payload: SubmitForReview = Body(default=SubmitForReview()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.submit_for_review(db, item_id=item_id, actor=payload.actor)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.post("/{item_id}/approve", response_model=EnterpriseQuotaOut)
def approve(
    item_id: int,
    payload: ReviewAction = Body(default=ReviewAction()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.approve(db, item_id=item_id, actor=payload.actor, comment=payload.comment)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.post("/{item_id}/reject", response_model=EnterpriseQuotaOut)
def reject(
    item_id: int,
    payload: ReviewAction = Body(default=ReviewAction()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.reject(db, item_id=item_id, actor=payload.actor, comment=payload.comment)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.post("/{item_id}/archive", response_model=EnterpriseQuotaOut)
def archive(
    item_id: int,
    payload: ReviewAction = Body(default=ReviewAction()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.archive(db, item_id=item_id, actor=payload.actor)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.post("/{item_id}/restore", response_model=EnterpriseQuotaOut)
def restore_to_draft(
    item_id: int,
    payload: ReviewAction = Body(default=ReviewAction()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = svc.restore_to_draft(db, item_id=item_id, actor=payload.actor)
    except svc.NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except svc.InvalidStateTransition as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


# ─── Excel import / template ─────────────────────────────────────────


@router.post("/import")
async def import_excel(
    file: UploadFile = File(...),
    created_by: str = Query(""),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx / .xls 文件")
    content = await file.read()
    result = svc.import_from_excel(content, db, created_by=created_by)
    return {
        "imported": result.imported,
        "skipped": result.skipped,
        "errors": result.errors,
    }


@router.get("/template/download")
def download_template() -> StreamingResponse:
    data = svc.build_template_xlsx()
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="enterprise_quota_template.xlsx"',
        },
    )


# ─── Candidates (precipitation) ──────────────────────────────────────


@router.get("/candidates/list", response_model=CandidateListResponse)
def list_candidates(
    status: str = Query("pending"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    keyword: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> CandidateListResponse:
    total, rows = precip.list_candidates(
        db, status=status, min_confidence=min_confidence,
        keyword=keyword, skip=skip, limit=limit,
    )
    return CandidateListResponse(
        total=total,
        items=[CandidateOut(**precip.candidate_to_dict(c)) for c in rows],
    )


@router.post("/candidates/analyze", response_model=AnalyzeResult)
def analyze(db: Session = Depends(get_db)) -> AnalyzeResult:
    """Run a full precipitation analysis (synchronous)."""
    result = precip.analyze_all(db)
    return AnalyzeResult(**result)


@router.post("/candidates/{candidate_id}/promote", response_model=EnterpriseQuotaOut)
def promote_candidate(
    candidate_id: int,
    payload: PromoteCandidateRequest = Body(default=PromoteCandidateRequest()),
    db: Session = Depends(get_db),
) -> EnterpriseQuotaOut:
    try:
        item = precip.promote_candidate(
            db,
            candidate_id=candidate_id,
            actor=payload.actor,
            quota_code_override=payload.quota_code_override,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return EnterpriseQuotaOut(**svc.to_out_dict(item))


@router.post("/candidates/{candidate_id}/dismiss", response_model=CandidateOut)
def dismiss_candidate(
    candidate_id: int,
    payload: DismissCandidateRequest = Body(default=DismissCandidateRequest()),
    db: Session = Depends(get_db),
) -> CandidateOut:
    try:
        c = precip.dismiss_candidate(
            db, candidate_id=candidate_id, reason=payload.reason, actor=payload.actor,
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return CandidateOut(**precip.candidate_to_dict(c))
