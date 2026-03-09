from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContractMeasurement(Base):
    __tablename__ = "contract_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    measured_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    cumulative_qty: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    approved_by: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    approved_at: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False, default=lambda: datetime.now(timezone.utc).isoformat()
    )

