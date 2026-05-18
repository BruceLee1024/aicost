"""OtherItem — GB50500 「其他项目费」 (4.4 节强制要求独立列示).

Four categories per the standard:
- 暂列金额 (provisional_sum):  业主预留, 整笔金额, 由发包人控制使用
- 暂估价 (provisional_price):  暂估材料/设备/专业工程价 (后期明确)
- 计日工 (daywork):            零星用工 / 临时材料, 按 qty × unit_price
- 总承包服务费 (gc_service):   总包对分包/甲供材的协调配合费
"""

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OtherItem(Base):
    __tablename__ = "other_items"
    __table_args__ = (
        Index("ix_other_item_project", "project_id"),
        Index("ix_other_item_category", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    # "provisional_sum" | "provisional_price" | "daywork" | "gc_service"
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_category: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="项")
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    # When is_fixed=1, amount is authoritative and (qty, price) are display-only.
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_fixed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 计税选项: "tax" / "no_tax" — 总承包服务费部分项目不计税
    tax_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="tax")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
