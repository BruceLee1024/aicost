from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProjectValuationConfig(Base):
    __tablename__ = "project_valuation_configs"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_valuation_config_project_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    standard_code: Mapped[str] = mapped_column(
        String(100), nullable=False, default="GB/T50500-2024"
    )
    standard_name: Mapped[str] = mapped_column(
        String(255), nullable=False, default="建设工程工程量清单计价标准"
    )
    effective_date: Mapped[str] = mapped_column(String(20), nullable=False, default="2025-09-01")
    locked_at: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    updated_at: Mapped[str] = mapped_column(
        String(50), nullable=False, default=lambda: datetime.now(timezone.utc).isoformat()
    )

