"""Base declarativa y tipos comunes. Solo tipos portables entre motores."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, MetaData, Numeric
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.util import ahora

CONVENCION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Cantidad = Numeric(18, 6)
Costo = Numeric(18, 6)
Monto = Numeric(18, 2)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCION)


class ConId:
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class ConFechas:
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    actualizado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora, onupdate=ahora)


__all__ = ["Base", "ConId", "ConFechas", "Cantidad", "Costo", "Monto", "Decimal"]
