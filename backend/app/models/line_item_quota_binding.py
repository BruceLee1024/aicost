from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LineItemQuotaBinding(Base):
    __tablename__ = "line_item_quota_bindings"
    __table_args__ = (
        UniqueConstraint("boq_item_id", "quota_item_id", name="uq_boq_quota_binding"),
        Index("ix_binding_boq_item_id", "boq_item_id"),
        Index("ix_binding_quota_item_id", "quota_item_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    boq_item_id: Mapped[int] = mapped_column(ForeignKey("boq_items.id"), nullable=False)
    quota_item_id: Mapped[int] = mapped_column(ForeignKey("quota_items.id"), nullable=False)
    coefficient: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
