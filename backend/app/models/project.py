from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_package_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("rule_packages.id"), nullable=True, default=None,
    )
    # ── Multi-standard support ──
    standard_type: Mapped[str] = mapped_column(String(50), nullable=False, default="GB50500")  # GB50500 | HKSMM4
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="zh")  # zh | en | bilingual
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")  # CNY | HKD
