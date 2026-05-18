"""PricingStandard — 计价标准注册中心.

Each row represents a versioned pricing standard such as GB50500-2013,
GB/T 50500-2024, or HKSMM4. All other tables that need to be standard-aware
(BoqItem, QuotaItem, FeeStructure, …) hold a foreign key here.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PricingStandard(Base):
    __tablename__ = "pricing_standards"
    __table_args__ = (
        UniqueConstraint("code", "region", name="uq_pricing_standard_code_region"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Stable identifier, e.g. "GB50500-2013" / "GBT50500-2024" / "HKSMM4"
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    year: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # ""=国标
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="")  # ""=通用
    # 编码规则 / 费用结构 / 计算口径全部用 JSON 文本存，引擎按 code 路由解析
    coding_rule_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    fee_structure_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    rounding_rule: Mapped[str] = mapped_column(String(50), nullable=False, default="ROUND_HALF_UP")
    effective_date: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    superseded_by_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
