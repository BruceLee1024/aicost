"""EnterpriseQuotaItem — 企业自有定额库.

Independent table that mirrors public ``QuotaItem`` fields plus enterprise
metadata (status workflow, source provenance, usage stats). Enterprise quotas
take priority over public quotas when AI matches BOQ items.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Status state machine
STATUS_DRAFT = "draft"
STATUS_IN_REVIEW = "in_review"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_ARCHIVED = "archived"

ALL_STATUSES = (
    STATUS_DRAFT, STATUS_IN_REVIEW, STATUS_APPROVED, STATUS_REJECTED, STATUS_ARCHIVED,
)

# Source types
SOURCE_MANUAL = "manual"
SOURCE_PRECIPITATED = "precipitated"
SOURCE_IMPORTED = "imported"


class EnterpriseQuotaItem(Base):
    __tablename__ = "enterprise_quota_items"
    __table_args__ = (
        Index("ix_eqi_status", "status"),
        Index("ix_eqi_source_status", "source_type", "status"),
        Index("ix_eqi_chapter", "chapter"),
        Index("ix_eqi_profession", "profession"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quota_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)

    # Quantity components (consumption per unit)
    labor_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    material_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    machine_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Fee components (already-priced)
    labor_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    material_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    machine_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    base_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Knowledge fields
    work_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    applicable_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")
    chapter: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="房建")
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="v1.0")

    # Enterprise-specific extras
    coefficient_default: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    # Workflow
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=STATUS_DRAFT)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default=SOURCE_MANUAL)
    source_ref_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    # Audit metadata
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    reviewed_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)
    review_comment: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Stats
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
