"""Utilidades comunes: fechas UTC, decimales y serializacion de modelos."""
import os
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

CERO = Decimal("0")
Q6 = Decimal("0.000001")
Q2 = Decimal("0.01")


def ahora() -> datetime:
    """Fecha/hora UTC sin zona (formato portable entre motores)."""
    return datetime.now(UTC).replace(tzinfo=None)


_ZONA: ZoneInfo | None = None


def zona() -> ZoneInfo:
    """Zona horaria de operacion (WMS_ZONA_HORARIA). Las fechas se guardan en UTC y los dias se cuentan en esta zona."""
    global _ZONA
    if _ZONA is None:
        try:
            _ZONA = ZoneInfo(os.environ.get("WMS_ZONA_HORARIA", "America/Santiago"))
        except Exception:
            _ZONA = ZoneInfo("UTC")
    return _ZONA


def hoy() -> date:
    """Dia actual en la zona de operacion: a las 21:00 de Chile ya es manana en UTC, pero no en la bodega."""
    return datetime.now(zona()).date()


def dia_local(momento: datetime) -> date:
    """Dia calendario local de una fecha/hora guardada en UTC."""
    return momento.replace(tzinfo=UTC).astimezone(zona()).date()


def inicio_dia_utc(dia: date) -> datetime:
    """Instante UTC (sin zona) en que comienza un dia local: limite inferior para filtrar por fecha."""
    return datetime.combine(dia, time.min, tzinfo=zona()).astimezone(UTC).replace(tzinfo=None)


def dec(valor) -> Decimal:
    if valor is None:
        return CERO
    if isinstance(valor, Decimal):
        return valor
    return Decimal(str(valor))


def q6(valor) -> Decimal:
    return dec(valor).quantize(Q6, rounding=ROUND_HALF_UP)


def q2(valor) -> Decimal:
    return dec(valor).quantize(Q2, rounding=ROUND_HALF_UP)


def json_valor(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds") + "Z"
    if isinstance(v, (date, time)):
        return v.isoformat()
    return v


def a_dict(obj, excluir: tuple[str, ...] = (), **extra) -> dict:
    """Serializa las columnas de un modelo SQLAlchemy a tipos JSON."""
    if obj is None:
        return None
    d = {c.key: json_valor(getattr(obj, c.key)) for c in obj.__table__.columns if c.key not in excluir}
    d.update({k: json_valor(v) for k, v in extra.items()})
    return d


CAMPOS_COSTO = (
    "costo_unitario", "costo_total", "precio_unitario", "costo_unitario_base", "costo_referencial",
    "valor", "valor_inicial", "valor_disponible", "valor_inventario", "costo_por_kilo", "costo",
)


def ocultar_costos(dato, ver: bool):
    """Elimina campos de costo cuando el usuario no tiene el permiso costos:ver."""
    if ver:
        return dato
    if isinstance(dato, list):
        return [ocultar_costos(x, ver) for x in dato]
    if isinstance(dato, dict):
        return {k: (None if k in CAMPOS_COSTO or k.startswith(("costo_", "valor_")) else ocultar_costos(v, ver))
                for k, v in dato.items()}
    return dato
