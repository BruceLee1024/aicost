"""Natural language query navigation with optional AI intent routing."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.ai.agents.query_agent import normalize_query_for_router

from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.schemas.query import QueryHit, QueryRequest, QueryResponse
from app.services.validation_service import validate_project

router = APIRouter(tags=["query"])


@router.post("/projects/{project_id}/query", response_model=QueryResponse)
def query_navigation(
    project_id: int,
    payload: QueryRequest,
    db: Session = Depends(get_db),
) -> QueryResponse:
    raw_q = payload.q.strip()
    q = normalize_query_for_router(raw_q)
    boq_items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
    boq_ids = [b.id for b in boq_items]

    hits: list[QueryHit] = []

    # --- Intent: unbound items ---
    if any(kw in q for kw in ["未绑定", "没绑定", "无绑定", "unbound"]):
        bound_ids: set[int] = set()
        if boq_ids:
            bound_ids = {
                row.boq_item_id
                for row in db.query(LineItemQuotaBinding)
                .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
                .all()
            }
        for boq in boq_items:
            if boq.id not in bound_ids:
                hits.append(_hit(boq, "未绑定定额"))

    # --- Intent: items with issues ---
    elif any(kw in q for kw in ["异常", "问题", "校验", "错误", "warning", "error"]):
        issues = validate_project(project_id=project_id, db=db)
        issue_ids = {i.boq_item_id for i in issues if i.boq_item_id is not None}
        for boq in boq_items:
            if boq.id in issue_ids:
                reasons = [i.message for i in issues if i.boq_item_id == boq.id]
                hits.append(_hit(boq, "; ".join(reasons[:2])))

    # --- Intent: dirty / needs recalc ---
    elif any(kw in q for kw in ["待重算", "dirty", "重算", "未计算"]):
        for boq in boq_items:
            if boq.is_dirty:
                hits.append(_hit(boq, "需要重新计算"))

    # --- Fallback: keyword search on name/code ---
    else:
        for boq in boq_items:
            if q in boq.name or q in boq.code:
                hits.append(_hit(boq, f"名称/编码匹配 \"{q}\""))

    return QueryResponse(query=raw_q, total_hits=len(hits), hits=hits)


def _hit(boq: BoqItem, reason: str) -> QueryHit:
    return QueryHit(
        boq_item_id=boq.id,
        code=boq.code,
        name=boq.name,
        unit=boq.unit,
        quantity=boq.quantity,
        reason=reason,
    )
