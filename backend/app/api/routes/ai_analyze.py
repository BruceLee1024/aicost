"""AI insight analysis endpoint."""

from fastapi import APIRouter, HTTPException

from app.ai.agents.insight_agent import VALID_CONTEXT_TYPES, generate_insight
from app.schemas.ai_insight import AIAnalyzeRequest, AIAnalyzeResponse

router = APIRouter(tags=["ai"])


@router.post(
    "/projects/{project_id}/ai-analyze",
    response_model=AIAnalyzeResponse,
)
def ai_analyze(
    project_id: int,
    payload: AIAnalyzeRequest,
) -> AIAnalyzeResponse:
    """Generate AI insight for the given project context."""
    if payload.context_type not in VALID_CONTEXT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid context_type. Must be one of: {', '.join(sorted(VALID_CONTEXT_TYPES))}",
        )

    # Inject project_id into context data
    data = {**payload.context_data, "project_id": project_id}
    try:
        insight = generate_insight(context_type=payload.context_type, context_data=data)
    except Exception:
        return AIAnalyzeResponse(insight=None, ai_available=False)

    return AIAnalyzeResponse(
        insight=insight,
        ai_available=insight is not None,
    )
