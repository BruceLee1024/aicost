"""EnterpriseQuotaCandidate — 系统从历史项目沉淀的候选企业定额.

The precipitation analyzer scans Snapshots + LineItemQuotaBindings, clusters
similar BOQ codes, and writes aggregated suggestions here. Users can then
"promote" a candidate into a draft EnterpriseQuotaItem awaiting review.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


CANDIDATE_PENDING = "pending"
CANDIDATE_PROMOTED = "promoted"
CANDIDATE_DISMISSED = "dismissed"


class EnterpriseQuotaCandidate(Base):
    __tablename__ = "enterprise_quota_candidates"
    __table_args__ = (
        UniqueConstraint("boq_code_pattern", "name_canonical", "unit",
                         name="uq_eqc_pattern_name_unit"),
        Index("ix_eqc_status", "status"),
        Index("ix_eqc_confidence", "confidence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Cluster key (used for upsert on re-analysis)
    boq_code_pattern: Mapped[str] = mapped_column(String(50), nullable=False)
    name_canonical: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Aggregated suggestions (weighted means)
    suggested_labor_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    suggested_material_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    suggested_machine_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    suggested_unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    suggested_coefficient: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Scoring
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Provenance (stored as JSON text)
    source_quota_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source_project_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=CANDIDATE_PENDING)
    promoted_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    dismiss_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
