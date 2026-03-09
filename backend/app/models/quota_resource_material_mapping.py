"""Mapping between quota resource details and material price records.

When a quota resource detail (e.g. "C30商品混凝土") is marked as a main material,
this mapping links it to a specific MaterialPrice record so the calculation engine
can use actual market prices (信息价) instead of the quota's built-in base price.
"""

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuotaResourceMaterialMapping(Base):
    __tablename__ = "quota_resource_material_mappings"
    __table_args__ = (
        Index("ix_qrmm_resource_detail_id", "resource_detail_id"),
        Index("ix_qrmm_material_price_id", "material_price_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resource_detail_id: Mapped[int] = mapped_column(
        ForeignKey("quota_resource_details.id"), nullable=False,
    )
    material_price_id: Mapped[int] = mapped_column(
        ForeignKey("material_prices.id"), nullable=False,
    )
    match_method: Mapped[str] = mapped_column(
        String(50), nullable=False, default="manual",
    )  # "manual" | "auto_name" | "auto_code" — how the mapping was established
