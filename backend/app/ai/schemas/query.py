"""Structured schema for natural language query intent routing."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AIQueryIntentOutput(BaseModel):
    intent: Literal["unbound", "issues", "dirty", "keyword"]
    keyword: str | None = Field(default=None, max_length=100)

    model_config = ConfigDict(extra="forbid")

