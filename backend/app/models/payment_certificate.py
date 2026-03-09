from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentCertificate(Base):
    __tablename__ = "payment_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    gross_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    prepayment_deduction: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    retention: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    net_payable: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="issued")
    issued_at: Mapped[str] = mapped_column(
        String(50), nullable=False, default=lambda: datetime.now(timezone.utc).isoformat()
    )

