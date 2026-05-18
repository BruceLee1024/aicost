"""CalcRuleDict — 工程量计算规则字典.

GB50854/55/56 等专业工程量计算规范规定：每个清单项目编码对应一条
工程量计算规则 + 工作内容 + 标准计量单位。本表把这些规则结构化,
供 BOQ 编辑器查阅、Agent 校验、报告输出引用。

code_pattern 支持前缀匹配: "010101001%" 匹配整个 010101001 项目族。
"""

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CalcRuleDict(Base):
    __tablename__ = "calc_rule_dict"
    __table_args__ = (
        Index("ix_crd_std_pattern", "pricing_standard_id", "code_pattern"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pricing_standard_id: Mapped[int] = mapped_column(
        ForeignKey("pricing_standards.id"), nullable=False,
    )
    # Profession bucket: "房建" / "市政" / "安装" / "装饰" / "园林" / "人防" / "其他"
    profession: Mapped[str] = mapped_column(String(50), nullable=False, default="房建")
    # Section path: "土石方工程" / "砌筑工程" / "混凝土及钢筋混凝土工程"
    chapter: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    section: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 12-digit BOQ code prefix (national first 9 digits + sequence). Use "%" wildcard.
    code_pattern: Mapped[str] = mapped_column(String(20), nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    standard_unit: Mapped[str] = mapped_column(String(50), nullable=False)
    # 工程量计算规则原文（GB50854 列出的具体公式 / 扣减规则）
    rule_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    work_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 项目特征模板：JSON 数组，每个元素 {key, label, required, options?}
    feature_template_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
