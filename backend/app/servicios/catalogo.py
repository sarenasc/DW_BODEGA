"""Reglas de catalogo: politica heredada y conversion de unidades."""
from collections import deque
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errores import ErrorNegocio
from app.core.util import dec
from app.modelos import (CAMPOS_POLITICA, ESTRATEGIAS, GRANULARIDADES, POLITICA_GLOBAL, POLITICAS_FIFO,
                         ConversionUnidad, Producto, UnidadMedida)

VALORES_VALIDOS = {"granularidad": GRANULARIDADES, "estrategia_salida": ESTRATEGIAS, "politica_fifo": POLITICAS_FIFO,
                   "prioridad_vencimiento": ("MANUAL", "CALCULADA")}


def validar_politica(obj) -> None:
    for campo, validos in VALORES_VALIDOS.items():
        v = getattr(obj, campo, None)
        if v is not None and v not in validos:
            raise ErrorNegocio("VALOR_INVALIDO", f"{campo}: valor no permitido ({v}). Opciones: {', '.join(validos)}.")


def politica_efectiva(producto: Producto) -> dict:
    """Resuelve producto -> subfamilia -> familia -> valor global. Indica de donde proviene cada valor."""
    sub = producto.subfamilia
    niveles = (("PRODUCTO", producto), ("SUBFAMILIA", sub), ("FAMILIA", sub.familia if sub else None))
    valores, origen = {}, {}
    for campo in CAMPOS_POLITICA:
        for nombre, obj in niveles:
            v = getattr(obj, campo, None) if obj is not None else None
            if v is not None:
                valores[campo], origen[campo] = v, nombre
                break
        else:
            valores[campo], origen[campo] = POLITICA_GLOBAL[campo], "GLOBAL"
    valores["origen"] = origen
    return valores


def factor_conversion(db: Session, producto_id: int | None, origen_id: int, destino_id: int) -> Decimal:
    """Factor tal que cantidad_destino = cantidad_origen x factor. Busca en conversiones del producto y universales."""
    if origen_id == destino_id:
        return Decimal(1)
    filas = db.scalars(select(ConversionUnidad).where(
        or_(ConversionUnidad.producto_id == producto_id, ConversionUnidad.producto_id.is_(None)))).all()
    grafo: dict[int, list[tuple[int, Decimal]]] = {}
    # Las conversiones propias del producto se agregan primero para que tengan prioridad.
    for c in sorted(filas, key=lambda c: c.producto_id is None):
        grafo.setdefault(c.unidad_origen_id, []).append((c.unidad_destino_id, dec(c.factor)))
        grafo.setdefault(c.unidad_destino_id, []).append((c.unidad_origen_id, Decimal(1) / dec(c.factor)))
    cola, vistos = deque([(origen_id, Decimal(1))]), {origen_id}
    while cola:
        actual, acumulado = cola.popleft()
        for siguiente, f in grafo.get(actual, []):
            if siguiente in vistos:
                continue
            if siguiente == destino_id:
                return acumulado * f
            vistos.add(siguiente)
            cola.append((siguiente, acumulado * f))
    u = {x.id: x.codigo for x in db.scalars(select(UnidadMedida).where(UnidadMedida.id.in_([origen_id, destino_id])))}
    raise ErrorNegocio("SIN_CONVERSION", f"No hay conversion configurada de {u.get(origen_id)} a {u.get(destino_id)} "
                                         "para este producto.", datos={"origen": origen_id, "destino": destino_id})


def a_unidad_base(db: Session, producto: Producto, cantidad, unidad_id: int | None) -> tuple[Decimal, Decimal]:
    """Devuelve (cantidad en unidad base, factor aplicado)."""
    f = factor_conversion(db, producto.id, unidad_id or producto.unidad_base_id, producto.unidad_base_id)
    return dec(cantidad) * f, f
