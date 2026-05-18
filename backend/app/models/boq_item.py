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
    # ── GB50500 合规扩展 (M1 双轨重构) ──
    # 标准化 12 位编码段：{prof:"01", chapter:"01", section:"01", item:"001", seq:"001"}
    code_segments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 项目特征结构化 (键值对数组)，与 characteristics 字符串并存
    feature_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 工程量计算规则原文 (来自 CalcRuleDict / GB50854…)
    calc_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 该项工程量推导公式: e.g. "L×B×H = 12×8×3 = 288"
    calc_formula: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 工作内容
    work_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 1=暂估项 (其他项目费里 "暂估价" 在 BOQ 中的体现)
    is_provisional: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 三级分部分项树（GB50300）：父节点 BOQ 项 (分部 → 子分部 → 分项)
    parent_division_id: Mapped[int | None] = mapped_column(
        ForeignKey("boq_items.id"), nullable=True, default=None,
    )
    # 关联到本项目所采用的计价标准
    pricing_standard_id: Mapped[int | None] = mapped_column(
        ForeignKey("pricing_standards.id"), nullable=True, default=None,
    )
