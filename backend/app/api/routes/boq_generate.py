"""AI-powered BOQ item generation endpoint with multi-standard support."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.agents.boq_agent import generate_boq_items_with_agent
from app.db.session import get_db
from app.models.project import Project
from app.schemas.boq_generate import (
    BoqSuggestionOut,
    GenerateRequest,
    GenerateResponse,
)
from app.services.boq_generate_service import _detect_floors

router = APIRouter(tags=["boq-generate"])


@router.post(
    "/projects/{project_id}/ai-generate-boq",
    response_model=GenerateResponse,
)
def ai_generate_boq(
    project_id: int,
    payload: GenerateRequest,
    db: Session = Depends(get_db),
) -> GenerateResponse:
    """Generate BOQ item suggestions from a natural language description.

    Supports both GB50500 and HKSMM4 standards based on project configuration.
    The suggestions are returned for user review; they are NOT
    automatically inserted into the project.
    """
    # Determine standard type from project
    project = db.query(Project).filter(Project.id == project_id).first()
    standard_type = project.standard_type if project else "GB50500"

    suggestions = generate_boq_items_with_agent(payload.description, standard_type)
    return GenerateResponse(
        description=payload.description,
        floors_detected=_detect_floors(payload.description),
        total_items=len(suggestions),
        suggestions=[
            BoqSuggestionOut(
                code=s.code,
                name=s.name,
                characteristics=s.characteristics,
                unit=s.unit,
                quantity=s.quantity,
                division=s.division,
                reason=s.reason,
            )
            for s in suggestions
        ],
    )
