from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CalcResult(Base):
    __tablename__ = "calc_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"), nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0)
