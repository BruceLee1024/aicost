from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from app.db.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[int] = mapped_column(Integer, nullable=True)
    before_json: Mapped[str] = mapped_column(Text, nullable=True, default=None)
    after_json: Mapped[str] = mapped_column(Text, nullable=True, default=None)
    timestamp: Mapped[str] = mapped_column(
        String(50), nullable=False,
        default=lambda: datetime.now(timezone.utc).isoformat(),
    )
