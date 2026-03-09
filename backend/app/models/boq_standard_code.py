"""Standard BOQ code knowledge base (GB50500 / industry standards).

Stores canonical bill-of-quantities codes with their standard names,
units, measurement rules, and common characteristics templates.
Used by validation engine and AI agents for compliance checking and
intelligent suggestions.
"""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BoqStandardCode(Base):
    __tablename__ = "boq_standard_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    standard_code: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # 标准编码 e.g. "010101001"
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # 标准名称 e.g. "平整场地"
    standard_unit: Mapped[str] = mapped_column(String(50), nullable=False)  # 标准单位 e.g. "m²"
    division: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # 分部 e.g. "土石方工程"
    chapter: Mapped[str] = mapped_column(String(100), nullable=False, default="")  # 章节 e.g. "A.1"
    measurement_rule: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 计量规则描述
    common_characteristics: Mapped[str] = mapped_column(Text, nullable=False, default="")  # 常见项目特征模板
    standard_version: Mapped[str] = mapped_column(String(50), nullable=False, default="GB50500-2013")  # 标准版本
    standard_type: Mapped[str] = mapped_column(String(50), nullable=False, default="GB50500")  # GB50500 | HKSMM4
    name_en: Mapped[str] = mapped_column(String(255), nullable=False, default="")  # English name
