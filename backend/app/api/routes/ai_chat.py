"""AI chat endpoint with project context injection."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai.agents.chat_agent import chat_with_project_context
from app.db.session import get_db
from app.models.boq_item import BoqItem
from app.models.calc_result import CalcResult
from app.models.line_item_quota_binding import LineItemQuotaBinding
from app.models.project import Project
from app.schemas.ai_insight import AIChatRequest, AIChatResponse
from app.services.validation_service import validate_project

router = APIRouter(tags=["ai"])


def _build_project_summary(project_id: int, db: Session) -> dict:
    """Build a compact project summary for the AI context window."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    boq_items = db.query(BoqItem).filter(BoqItem.project_id == project_id).all()
    boq_ids = [b.id for b in boq_items]

    bound_ids: set[int] = set()
    if boq_ids:
        bound_ids = {
            row.boq_item_id
            for row in db.query(LineItemQuotaBinding)
            .filter(LineItemQuotaBinding.boq_item_id.in_(boq_ids))
            .all()
        }

    calc_results = (
        db.query(CalcResult)
        .filter(CalcResult.boq_item_id.in_(boq_ids))
        .all()
        if boq_ids
        else []
    )
    calc_total = sum(c.total_cost for c in calc_results)

    issues = validate_project(project_id=project_id, db=db)

    divisions = list({b.division for b in boq_items if b.division})

    # Top 5 items by name for context
    top_items = [
        {"code": b.code, "name": b.name, "unit": b.unit, "quantity": b.quantity}
        for b in boq_items[:10]
    ]

    return {
        "project_name": project.name,
        "region": project.region,
        "boq_count": len(boq_items),
        "bound_count": len(bound_ids),
        "unbound_count": len(boq_items) - len(bound_ids),
        "calc_total": round(calc_total, 2),
        "calc_items_count": len(calc_results),
        "validation_errors": sum(1 for i in issues if i.severity.value == "error"),
        "validation_warnings": sum(1 for i in issues if i.severity.value == "warning"),
        "divisions": divisions,
        "sample_items": top_items,
    }


@router.post(
    "/projects/{project_id}/ai-chat",
    response_model=AIChatResponse,
)
def ai_chat(
    project_id: int,
    payload: AIChatRequest,
    db: Session = Depends(get_db),
) -> AIChatResponse:
    """Chat with AI assistant that has project context."""
    try:
        project_summary = _build_project_summary(project_id, db)
    except HTTPException:
        raise
    except Exception:
        # Graceful degradation if summary build fails
        return AIChatResponse(reply=None, ai_available=False)

    history = [{"role": m.role, "content": m.content} for m in payload.history]

    try:
        reply = chat_with_project_context(
            message=payload.message,
            history=history,
            project_summary=project_summary,
            project_id=project_id,
        )
    except Exception:
        return AIChatResponse(reply=None, ai_available=False)

    return AIChatResponse(
        reply=reply,
        ai_available=reply is not None,
    )
