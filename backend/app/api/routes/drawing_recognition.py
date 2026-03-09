"""Drawing recognition API — upload drawing, get structural components + BOQ suggestions."""

from typing import Optional

from fastapi import APIRouter, File, Query, UploadFile
from pydantic import BaseModel

from app.services.drawing_recognition_service import (
    components_to_boq_suggestions,
    recognize_drawing,
)

router = APIRouter(prefix="/drawing-recognition", tags=["drawing-recognition"])


class ComponentOut(BaseModel):
    id: str
    type: str
    count: int
    spec: str
    confidence: float
    material: str = ""
    unit: str = ""
    quantity_estimate: float = 0.0


class BoqSuggestionOut(BaseModel):
    source_component_id: str
    suggested_code: str
    suggested_name: str
    suggested_unit: str
    suggested_quantity: float
    characteristics: str
    confidence: float
    material: str = ""
    component_count: int = 0


class RecognitionResponse(BaseModel):
    drawing_type: str
    summary: str
    components: list[ComponentOut]
    boq_suggestions: list[BoqSuggestionOut]
    error: Optional[str] = None


@router.post("", response_model=RecognitionResponse)
async def recognize(
    file: UploadFile = File(..., description="Drawing image (PNG/JPG/PDF)"),
    project_context: str = Query("", description="Optional project context for better recognition"),
):
    """Upload a drawing and get AI-recognized structural components + BOQ suggestions."""
    image_bytes = await file.read()
    content_type = file.content_type or "image/png"

    result = recognize_drawing(
        image_bytes=image_bytes,
        content_type=content_type,
        project_context=project_context,
    )

    suggestions = components_to_boq_suggestions(result.components) if result.components else []

    return RecognitionResponse(
        drawing_type=result.drawing_type,
        summary=result.summary,
        components=[
            ComponentOut(
                id=c.id,
                type=c.type,
                count=c.count,
                spec=c.spec,
                confidence=c.confidence,
                material=c.material,
                unit=c.unit,
                quantity_estimate=c.quantity_estimate,
            )
            for c in result.components
        ],
        boq_suggestions=[
            BoqSuggestionOut(**s) for s in suggestions
        ],
        error=result.error,
    )
