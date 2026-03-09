from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RulePackage(Base):
    __tablename__ = "rule_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    management_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.08)
    profit_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.05)
    regulatory_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.03)
    tax_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.09)
    rounding_rule: Mapped[str] = mapped_column(String(50), nullable=False, default="ROUND_HALF_UP")
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
