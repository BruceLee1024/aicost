"""Schemas for AI insight and chat endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class AIAnalyzeRequest(BaseModel):
    context_type: str = Field(
        ...,
        description="One of: scan, match, calc, validation, provenance, dashboard",
    )
    context_data: dict[str, Any] = Field(default_factory=dict)


class AIAnalyzeResponse(BaseModel):
    insight: str | None = Field(
        None,
        description="AI-generated insight text, or null if AI unavailable",
    )
    ai_available: bool = Field(default=False)


class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str | None = Field(
        None,
        description="AI-generated reply, or null if AI unavailable",
    )
    ai_available: bool = Field(default=False)
