from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuotaItem(Base):
    __tablename__ = "quota_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quota_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    labor_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    material_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    machine_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # ── Extended business knowledge fields ──
    work_content: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 工作内容描述
    applicable_scope: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 适用范围与条件
    chapter: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # 所属章节/分部
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="")  # 定额版本（如"2018全国统一"）
    base_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # 定额基价（元）
    has_resource_details: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 1=有明细
