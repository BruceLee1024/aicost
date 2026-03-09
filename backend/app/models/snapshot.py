from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from app.db.base import Base


class Snapshot(Base):
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(
        String(50), nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
    )
    grand_total: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
