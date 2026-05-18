from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class QuotaItem(Base):
    __tablename__ = "quota_items"
    # Note: legacy unique-on-quota_code remains via the column-level unique=True below
    # for backward compatibility with existing data and migrations. The new
    # composite uniqueness (quota_code, pricing_standard_id) is enforced
    # additionally so the same code can exist across different standards.
    __table_args__ = (
        Index("ix_quota_item_std_prof", "pricing_standard_id", "profession"),
    )

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
    # ── 2024 版动态人工费机制 ──
    # 2024 版：直接给"定额人工费"金额，配合 LaborCostIndex 动态调整。
    # 2018/2013 旧版本可继续使用 labor_qty × 类别均价 模式，这两组字段并存。
    labor_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    material_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    machine_fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    labor_index_base: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    # ── Standard / 专业 / 换算 ──
    pricing_standard_id: Mapped[int | None] = mapped_column(
        ForeignKey("pricing_standards.id"), nullable=True, default=None,
    )
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="房建")
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    # 换算系数表 / 单位换算约束 (JSON)
    conversion_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    unit_constraint_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
