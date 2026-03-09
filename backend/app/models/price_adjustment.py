from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PriceAdjustment(Base):
    __tablename__ = "price_adjustments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    boq_item_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    adjustment_type: Mapped[str] = mapped_column(String(100), nullable=False, default="change_order")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, default=lambda: datetime.now(timezone.utc).isoformat()
    )

