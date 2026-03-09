from sqlalchemy import Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaterialPrice(Base):
    __tablename__ = "material_prices"
    __table_args__ = (
        Index("ix_material_price_lookup", "name", "region", "effective_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    spec: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="manual")
    region: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    effective_date: Mapped[str] = mapped_column(String(20), nullable=False, default="1970-01-01")
