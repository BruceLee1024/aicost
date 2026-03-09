"""Quota resource detail: individual labor/material/machine items within a quota.

Each QuotaItem can have multiple resource details representing the specific
resources consumed (e.g. "HRB400钢筋 0.05t", "C30混凝土 1.05m³", "人工 2.5工日").
This enables precise pricing using actual material market prices instead of
aggregate category totals.
"""

from sqlalchemy import Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuotaResourceDetail(Base):
    __tablename__ = "quota_resource_details"
    __table_args__ = (
        Index("ix_qrd_quota_item_id", "quota_item_id"),
        Index("ix_qrd_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quota_item_id: Mapped[int] = mapped_column(ForeignKey("quota_items.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # "人工" | "材料" | "机械"
    resource_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # 资源编码
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False)  # 资源名称
    spec: Mapped[str] = mapped_column(String(255), nullable=False, default="")  # 规格型号
    unit: Mapped[str] = mapped_column(String(50), nullable=False)  # 计量单位
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 消耗量
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 定额内单价（基价）
    is_main_material: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 1=主材（可能需要信息价替换）
