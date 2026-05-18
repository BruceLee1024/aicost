from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    project_type: Mapped[str] = mapped_column(String(50), nullable=False, default="住宅")  # 住宅|商业|工业|公共建筑|市政
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|ongoing|completed|archived
    budget: Mapped[float | None] = mapped_column(Float, nullable=True, default=None)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True, default=None)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    rule_package_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rule_packages.id"), nullable=True, default=None,
    )
    # ── Multi-standard support ──
    standard_type: Mapped[str] = mapped_column(String(50), nullable=False, default="GB50500")  # GB50500 | HKSMM4
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh")  # zh | en | bilingual
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")  # CNY | HKD
    # ── M1 双轨重构：精确指向计价标准版本 (e.g. GBT50500-2024 / GB50500-2013) ──
    pricing_standard_id: Mapped[int | None] = mapped_column(
        ForeignKey("pricing_standards.id"), nullable=True, default=None,
    )
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="房建")
    tax_method: Mapped[str] = mapped_column(String(20), nullable=False, default="general")  # "general" | "simple"
    labor_index_period: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    # ── Timestamps ──
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
