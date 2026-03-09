"""Structured schema for BOQ generation outputs."""

from pydantic import BaseModel, ConfigDict, Field


class AIBoqSuggestion(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    characteristics: str = Field(default="", max_length=1000)
    unit: str = Field(min_length=1, max_length=50)
    quantity: float = Field(gt=0, le=1_000_000)
    division: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class AIBoqGenerateOutput(BaseModel):
    suggestions: list[AIBoqSuggestion] = Field(default_factory=list, max_length=50)

    model_config = ConfigDict(extra="forbid")

