"""Pydantic schemas for the enterprise quota library."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ─── EnterpriseQuotaItem ────────────────────────────────────────────


class EnterpriseQuotaCreate(BaseModel):
    quota_code: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    unit: str = Field(..., min_length=1, max_length=50)
    labor_qty: float = 0.0
    material_qty: float = 0.0
    machine_qty: float = 0.0
    labor_fee: float = 0.0
    material_fee: float = 0.0
    machine_fee: float = 0.0
    base_price: float = 0.0
    work_content: str = ""
    applicable_scope: str = ""
    chapter: str = ""
    profession: str = "房建"
    region: str = ""
    version: str = "v1.0"
    coefficient_default: float = 1.0
    tags: list[str] = Field(default_factory=list)
    source_type: str | None = None  # defaults to "manual"
    source_ref: dict[str, Any] | None = None
    created_by: str = ""


class EnterpriseQuotaUpdate(BaseModel):
    name: str | None = None
    unit: str | None = None
    labor_qty: float | None = None
    material_qty: float | None = None
    machine_qty: float | None = None
    labor_fee: float | None = None
    material_fee: float | None = None
    machine_fee: float | None = None
    base_price: float | None = None
    work_content: str | None = None
    applicable_scope: str | None = None
    chapter: str | None = None
    profession: str | None = None
    region: str | None = None
    version: str | None = None
    coefficient_default: float | None = None
    tags: list[str] | None = None


class EnterpriseQuotaOut(BaseModel):
    id: int
    quota_code: str
    name: str
    unit: str
    labor_qty: float
    material_qty: float
    machine_qty: float
    labor_fee: float
    material_fee: float
    machine_fee: float
    base_price: float
    work_content: str
    applicable_scope: str
    chapter: str
    profession: str
    region: str
    version: str
    coefficient_default: float
    tags: list[str]
    status: str
    source_type: str
    source_ref: dict[str, Any]
    created_by: str
    created_at: datetime | None
    submitted_at: datetime | None
    reviewed_by: str
    reviewed_at: datetime | None
    review_comment: str
    usage_count: int


class EnterpriseQuotaListResponse(BaseModel):
    total: int
    items: list[EnterpriseQuotaOut]


class EnterpriseQuotaStats(BaseModel):
    total: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    pending_review: int
    pending_candidates: int
    recent_created: int  # within last 30 days


# ─── State machine actions ──────────────────────────────────────────


class SubmitForReview(BaseModel):
    actor: str = ""


class ReviewAction(BaseModel):
    actor: str = ""
    comment: str = ""


# ─── EnterpriseQuotaCandidate ───────────────────────────────────────


class CandidateOut(BaseModel):
    id: int
    boq_code_pattern: str
    name_canonical: str
    unit: str
    suggested_labor_qty: float
    suggested_material_qty: float
    suggested_machine_qty: float
    suggested_unit_price: float
    suggested_coefficient: float
    sample_count: int
    confidence: float
    source_quota_ids: list[int]
    source_project_ids: list[int]
    evidence: dict[str, Any]
    status: str
    promoted_to_id: int | None
    dismiss_reason: str
    created_at: datetime | None
    last_analyzed_at: datetime | None


class CandidateListResponse(BaseModel):
    total: int
    items: list[CandidateOut]


class AnalyzeResult(BaseModel):
    snapshots_scanned: int
    bindings_scanned: int
    candidates_created: int
    candidates_updated: int


class PromoteCandidateRequest(BaseModel):
    actor: str = ""
    quota_code_override: str | None = None  # if user wants a custom code


class DismissCandidateRequest(BaseModel):
    reason: str = ""
    actor: str = ""
