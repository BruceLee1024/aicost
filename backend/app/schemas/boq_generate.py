from pydantic import BaseModel


class GenerateRequest(BaseModel):
    description: str


class BoqSuggestionOut(BaseModel):
    code: str
    name: str
    characteristics: str = ""
    unit: str
    quantity: float
    division: str
    reason: str


class GenerateResponse(BaseModel):
    description: str
    floors_detected: int
    total_items: int
    suggestions: list[BoqSuggestionOut]
