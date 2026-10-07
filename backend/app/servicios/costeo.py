"""Costeo de procesos: costo total, base de kilos configurable, costo por kilo y analisis multidimensional."""
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.parametros import parametro
from app.core.util import CERO, dec
from app.modelos import (BASES_COSTEO, Bodega, Existencia, Familia, MovimientoInventario, Proceso, Producto, Subfamilia,
                         Temporada)

ETIQUETAS_BASE = {"kilos_procesados": "Kilos procesados", "kilos_recepcionados": "Kilos recepcionados",
                  "kilos_producidos": "Kilos producidos", "kilos_despachados": "Kilos despachados"}
DIM_PROCESO = ("proceso", "especie", "variedad", "productor", "exportadora", "lote_productivo", "temporada", "semana", "mes",
               "turno", "linea")
DIM_PRODUCTO = ("producto", "familia", "subfamilia", "bodega")
DIMENSIONES = DIM_PROCESO + DIM_PRODUCTO


def campo_base(db: Session, p: Proceso) -> str:
    return p.base_costeo or parametro(db, "costeo.base_kilos", p.empresa_id, "kilos_procesados")


def kilos_base(db: Session, p: Proceso, campo: str | None = None) -> Decimal | None:
    """Kilos usados como divisor. Un proceso cerrado usa siempre sus kilos definitivos."""
    if p.estado == "CERRADO" and p.kilos_definitivos is not None:
        return p.kilos_definitivos
    campo = campo or campo_base(db, p)
    if campo in BASES_COSTEO:
        return getattr(p, campo)
    valor = (p.datos_adicionales or {}).get(campo.removeprefix("extra."))
    try:
        return dec(valor) if valor not in (None, "") else None
    except Exception:
        return None


def costo_proceso(db: Session, proceso_id: int) -> Decimal:
    """Suma de consumos valorizados. Los movimientos inversos (anulaciones, devoluciones) restan por su signo."""
    return -dec(db.scalar(select(func.coalesce(func.sum(MovimientoInventario.costo_total), 0)).where(
        MovimientoInventario.proceso_id == proceso_id)))


def resumen_costos(db: Session, p: Proceso) -> dict:
    campo = campo_base(db, p)
    kilos = kilos_base(db, p, campo)
    total = costo_proceso(db, p.id)
    filas = db.execute(
        select(Producto.id, Producto.codigo, Producto.nombre, Subfamilia.nombre, Familia.nombre,
               func.sum(MovimientoInventario.cantidad), func.sum(MovimientoInventario.costo_total))
        .join(Producto, MovimientoInventario.producto_id == Producto.id)
        .join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).join(Familia, Subfamilia.familia_id == Familia.id)
        .where(MovimientoInventario.proceso_id == p.id)
        .group_by(Producto.id, Producto.codigo, Producto.nombre, Subfamilia.nombre, Familia.nombre)).all()
    unidades = {x.id: x.unidad_base.codigo for x in db.scalars(select(Producto).where(Producto.id.in_([f[0] for f in filas]))).unique()} if filas else {}
    por_producto = [{"producto_id": f[0], "producto_codigo": f[1], "producto": f[2], "subfamilia": f[3], "familia": f[4],
                     "cantidad": float(-dec(f[5])), "unidad": unidades.get(f[0]), "costo": float(-dec(f[6])),
                     "costo_por_kilo": float(-dec(f[6]) / kilos) if kilos else None}
                    for f in filas if dec(f[5]) != 0 or dec(f[6]) != 0]
    por_familia: dict[str, Decimal] = defaultdict(lambda: CERO)
    for f in filas:
        por_familia[f[4]] += -dec(f[6])
    return {
        "costo_total": float(total), "base_costeo": campo, "base_costeo_nombre": ETIQUETAS_BASE.get(campo, campo),
        "kilos": float(kilos) if kilos is not None else None, "estado_kilos": p.estado_kilos,
        "costo_por_kilo": float(total / kilos) if kilos else None,
        "por_producto": sorted(por_producto, key=lambda x: -x["costo"]),
        "por_familia": [{"familia": k, "costo": float(v), "costo_por_kilo": float(v / kilos) if kilos else None}
                        for k, v in sorted(por_familia.items(), key=lambda kv: -kv[1]) if v != 0],
    }


def _clave_proceso(p: Proceso, dimension: str, temporadas: dict[int, str]) -> str:
    if dimension == "proceso":
        return p.codigo
    if dimension == "temporada":
        return temporadas.get(p.temporada_id) or p.temporada or "Sin temporada"
    if dimension == "semana":
        return f"{p.fecha.isocalendar()[0]}-S{p.fecha.isocalendar()[1]:02d}" if p.fecha else "Sin fecha"
    if dimension == "mes":
        return f"{p.fecha:%Y-%m}" if p.fecha else "Sin fecha"
    return getattr(p, dimension) or f"Sin {dimension.replace('_', ' ')}"


def analisis(db: Session, empresa_id: int, dimension: str, *, desde: date | None = None, hasta: date | None = None,
             temporada_id: int | None = None, especie: str | None = None, productor: str | None = None,
             proceso_id: int | None = None, bodega_id: int | None = None, familia_id: int | None = None,
             subfamilia_id: int | None = None, producto_id: int | None = None, bodegas: set[int] | None = None,
             familias: set[int] | None = None) -> list[dict]:
    """Costo, kilos y costo por kilo agrupados por una dimension del proceso o del producto consumido."""
    if dimension not in DIMENSIONES:
        raise ValueError(dimension)
    c = (select(MovimientoInventario.proceso_id, MovimientoInventario.producto_id, Producto.nombre, Subfamilia.nombre,
                Familia.nombre, Existencia.bodega_id, func.sum(MovimientoInventario.costo_total))
         .join(Proceso, MovimientoInventario.proceso_id == Proceso.id)
         .join(Producto, MovimientoInventario.producto_id == Producto.id)
         .join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).join(Familia, Subfamilia.familia_id == Familia.id)
         .join(Existencia, MovimientoInventario.existencia_id == Existencia.id)
         .where(Proceso.empresa_id == empresa_id, Proceso.estado != "ANULADO"))
    filtros = ((Proceso.temporada_id, temporada_id), (Proceso.especie, especie), (Proceso.productor, productor),
               (Proceso.id, proceso_id), (Existencia.bodega_id, bodega_id), (Familia.id, familia_id),
               (Subfamilia.id, subfamilia_id), (Producto.id, producto_id))
    for col, val in filtros:
        if val not in (None, ""):
            c = c.where(col == val)
    if desde:
        c = c.where(Proceso.fecha >= desde)
    if hasta:
        c = c.where(Proceso.fecha <= hasta)
    if bodegas is not None:
        c = c.where(Existencia.bodega_id.in_(bodegas))
    if familias is not None:
        c = c.where(Familia.id.in_(familias))
    filas = db.execute(c.group_by(MovimientoInventario.proceso_id, MovimientoInventario.producto_id, Producto.nombre,
                                  Subfamilia.nombre, Familia.nombre, Existencia.bodega_id)).all()
    if not filas:
        return []
    procesos = {p.id: p for p in db.scalars(select(Proceso).where(Proceso.id.in_({f[0] for f in filas})))}
    temporadas = dict(db.execute(select(Temporada.id, Temporada.codigo)).all())
    nombres_bodega = dict(db.execute(select(Bodega.id, Bodega.nombre)).all())
    kilos_proc = {pid: kilos_base(db, p) for pid, p in procesos.items()}
    grupos: dict[str, dict] = {}
    for pid, _prod, nombre_prod, sub, fam, bid, costo in filas:
        p = procesos[pid]
        if dimension in DIM_PROCESO:
            clave = _clave_proceso(p, dimension, temporadas)
        else:
            clave = {"producto": nombre_prod, "subfamilia": sub, "familia": fam, "bodega": nombres_bodega.get(bid, "-")}[dimension]
        g = grupos.setdefault(clave, {"clave": clave, "costo": CERO, "procesos": set(), "provisorios": 0})
        g["costo"] += -dec(costo)
        g["procesos"].add(pid)
    salida = []
    for g in grupos.values():
        kilos = sum((dec(kilos_proc[pid]) for pid in g["procesos"] if kilos_proc[pid]), CERO)
        provisorios = sum(1 for pid in g["procesos"] if procesos[pid].estado_kilos != "DEFINITIVO")
        salida.append({"clave": g["clave"], "costo": float(g["costo"]), "kilos": float(kilos),
                       "costo_por_kilo": float(g["costo"] / kilos) if kilos else None, "procesos": len(g["procesos"]),
                       "procesos_provisorios": provisorios,
                       "estado_kilos": "PROVISORIO" if provisorios else "DEFINITIVO"})
    return sorted(salida, key=lambda x: -x["costo"])


__all__ = ["analisis", "resumen_costos", "costo_proceso", "kilos_base", "campo_base", "DIMENSIONES", "datetime"]
