from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MeasureItem(Base):
    __tablename__ = "measure_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    calc_base: Mapped[str] = mapped_column(String(50), nullable=False, default="direct")  # "direct" | "pre_tax"
    rate: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_fixed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 1=fixed amount, 0=rate-based
