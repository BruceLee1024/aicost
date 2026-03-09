from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BoqItem(Base):
    __tablename__ = "boq_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    characteristics: Mapped[str] = mapped_column(String(500), nullable=False, default="")  # 项目特征
    division: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # 分部名称
    is_dirty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1=needs recalc
    # ── Ordering & HK-style fields ──
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    item_ref: Mapped[str] = mapped_column(String(50), nullable=False, default="")  # HKSMM ref e.g. "A/1"
    trade_section: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # HKSMM trade
    description_en: Mapped[str] = mapped_column(Text, nullable=False, default="")  # English description
    rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # HK rate-based pricing
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)  # rate × quantity
    remark: Mapped[str] = mapped_column(String(500), nullable=False, default="")
