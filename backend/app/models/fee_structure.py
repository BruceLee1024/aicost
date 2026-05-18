"""FeeStructure — 每个计价标准下的费用项目树.

Mirrors the GB50500 五大费 hierarchy:
  分部分项工程费 (FBFX)
    ├─ 综合单价 (FBFX.ZHDJ)
    │   ├─ 人工费 / 材料费 / 机械费 / 管理费 / 利润 / 风险费
  措施项目费 (CSXM)
    ├─ 单价措施 / 总价措施 / 安全文明施工费(不可竞争)
  其他项目费 (QTXM)
    ├─ 暂列金额 / 暂估价 / 计日工 / 总承包服务费
  规费 (GF)
    ├─ 社会保险费 / 住房公积金 / 工程排污费
  税金 (SJ)
    ├─ 增值税 (一般计税 9% / 简易计税 3%)

Each row is a node in this tree; parent_id links to a parent node.
The pricing engine v2 iterates this tree depth-first to compute totals.
"""

from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeeStructure(Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint(
            "pricing_standard_id", "fee_code",
            name="uq_fee_structure_std_code",
        ),
        Index("ix_fee_structure_std", "pricing_standard_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pricing_standard_id: Mapped[int] = mapped_column(
        ForeignKey("pricing_standards.id"), nullable=False,
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("fee_structures.id"), nullable=True, default=None,
    )
    # Stable code path, dot-separated: "FBFX" / "FBFX.ZHDJ" / "FBFX.ZHDJ.GLF"
    fee_code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # "sum_children" / "sum_lines" / "base_x_rate" / "fixed" / "labor_index_diff"
    formula: Mapped[str] = mapped_column(String(50), nullable=False, default="sum_children")
    # When formula = "base_x_rate": which fee_code is the base
    base_code: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    default_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 1 = 不可竞争 (安全文明施工费 / 规费 / 税金 等)
    is_competitive: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 1 = 是叶子节点 (实际取值的金额项)
    is_leaf: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
