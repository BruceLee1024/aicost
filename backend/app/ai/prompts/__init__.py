"""Prompt templates for AI workflows."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    path = Path(__file__).with_name(name)
    return path.read_text(encoding="utf-8")

