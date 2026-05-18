"""LaborCostIndex — 人工费动态指数 (2024 版核心机制).

GB/T 50500-2024 配套 2024 版消耗量定额改用「定额人工费 + 人工成本综合指数」
动态调价。各省按月发布指数, 指数 × 定额人工费 = 当期人工费; 价差只计税。
"""

from sqlalchemy import Float, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LaborCostIndex(Base):
    __tablename__ = "labor_cost_indices"
    __table_args__ = (
        UniqueConstraint(
            "region", "profession", "base_year", "period",
            name="uq_lci_region_prof_base_period",
        ),
        Index("ix_lci_lookup", "region", "profession", "period"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="房建")
    base_year: Mapped[str] = mapped_column(String(10), nullable=False, default="2024")
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # "2025-04"
    index_value: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    note: Mapped[str] = mapped_column(String(255), nullable=False, default="")
