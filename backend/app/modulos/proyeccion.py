"""Proyeccion de insumos: segun el historial por especie, calcula la receta necesaria para los kilos que faltan por procesar."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio
from app.core.util import CERO, dec, ocultar_costos
from app.modelos import MovimientoInventario, Proceso, Producto, Subfamilia
from app.servicios import costeo
from app.servicios import inventario as inv

router = APIRouter(prefix="/api", tags=["Proyeccion de insumos"])


def tasas_por_especie(db: Session, ctx: Contexto, *, desde: date | None = None, hasta: date | None = None,
                      temporada_id: int | None = None, solo_cerrados: bool = True, familia_id: int | None = None) -> dict:
    """Consumo historico por kilo, por especie y producto.

    tasa = cantidad consumida del producto en los procesos de la especie / kilos base de TODOS esos procesos.
    Se divide por todos los procesos de la especie (no solo por los que usaron el producto) para obtener el uso promedio real.
    """
    c = select(Proceso).where(Proceso.empresa_id == ctx.empresa_id, Proceso.especie.is_not(None),
                              Proceso.estado.in_(("CERRADO",) if solo_cerrados else ("CERRADO", "ABIERTO")))
    if desde:
        c = c.where(Proceso.fecha >= desde)
    if hasta:
        c = c.where(Proceso.fecha <= hasta)
    if temporada_id:
        c = c.where(Proceso.temporada_id == temporada_id)
    procesos = {p.id: p for p in db.scalars(c)}
    kilos: dict[str, Decimal] = defaultdict(lambda: CERO)
    cuenta: dict[str, int] = defaultdict(int)
    validos: dict[int, str] = {}
    for p in procesos.values():
        k = costeo.kilos_base(db, p)
        if k and k > 0:  # un proceso sin kilos no aporta a la tasa
            kilos[p.especie] += dec(k)
            cuenta[p.especie] += 1
            validos[p.id] = p.especie
    uso: dict[tuple[str, int], list[Decimal]] = defaultdict(lambda: [CERO, CERO])
    if validos:
        q = (select(MovimientoInventario.proceso_id, MovimientoInventario.producto_id, func.sum(MovimientoInventario.cantidad),
                    func.sum(MovimientoInventario.costo_total))
             .join(Producto, MovimientoInventario.producto_id == Producto.id)
             .join(Subfamilia, Producto.subfamilia_id == Subfamilia.id)
             .where(MovimientoInventario.proceso_id.in_(list(validos))))
        if familia_id:
            q = q.where(Subfamilia.familia_id == familia_id)
        if ctx.familias is not None:
            q = q.where(Subfamilia.familia_id.in_(ctx.familias))
        for pid, prod_id, cantidad, costo in db.execute(q.group_by(MovimientoInventario.proceso_id, MovimientoInventario.producto_id)):
            fila = uso[(validos[pid], prod_id)]
            fila[0] += -dec(cantidad)  # los consumos son negativos; las anulaciones los compensan
            fila[1] += -dec(costo)
    return {"kilos": dict(kilos), "procesos": dict(cuenta), "uso": {k: v for k, v in uso.items() if v[0] > 0}}


@router.get("/proyeccion/historial")
def historial(desde: date | None = None, hasta: date | None = None, temporada_id: int | None = None, solo_cerrados: bool = True,
              familia_id: int | None = None, db: Session = Depends(get_db),
              ctx: Contexto = Depends(requiere("procesos:ver", "inventario:ver"))):
    """Base del calculo: por especie, kilos procesados, cantidad de procesos y gasto historico por kilo."""
    t = tasas_por_especie(db, ctx, desde=desde, hasta=hasta, temporada_id=temporada_id, solo_cerrados=solo_cerrados, familia_id=familia_id)
    salida = []
    for especie in sorted(t["kilos"]):
        costo = sum((v[1] for (e, _), v in t["uso"].items() if e == especie), CERO)
        salida.append({"especie": especie, "procesos": t["procesos"][especie], "kilos": float(t["kilos"][especie]),
                       "costo": float(costo), "costo_por_kilo": float(costo / t["kilos"][especie]),
                       "productos": sum(1 for (e, _) in t["uso"] if e == especie)})
    return ocultar_costos(salida, ctx.ver_costos)


class Pendiente(BaseModel):
    especie: str
    kilos: Decimal = Field(gt=0)


class ProyeccionEntrada(BaseModel):
    pendientes: list[Pendiente] = Field(min_length=1)
    desde: date | None = None
    hasta: date | None = None
    temporada_id: int | None = None
    solo_cerrados: bool = True
    familia_id: int | None = None
    bodega_id: int | None = None


@router.post("/proyeccion")
def proyectar(d: ProyeccionEntrada, db: Session = Depends(get_db),
              ctx: Contexto = Depends(requiere("procesos:ver", "inventario:ver"))):
    """Receta que falta por aplicar: kilos pendientes por especie x consumo historico por kilo, comparada con el stock disponible."""
    if d.bodega_id:
        ctx.exigir_bodega(d.bodega_id)
    t = tasas_por_especie(db, ctx, desde=d.desde, hasta=d.hasta, temporada_id=d.temporada_id, solo_cerrados=d.solo_cerrados,
                          familia_id=d.familia_id)
    pendientes: dict[str, Decimal] = defaultdict(lambda: CERO)
    for p in d.pendientes:
        pendientes[p.especie.strip()] += p.kilos
    sin_historial = sorted(e for e in pendientes if e not in t["kilos"])
    if len(sin_historial) == len(pendientes):
        raise ErrorNegocio("SIN_HISTORIAL", "No hay procesos con kilos y consumos para las especies indicadas en el periodo elegido. "
                                            "Amplie el periodo o incluya los procesos abiertos.")
    requerido: dict[int, dict] = {}
    detalle = []
    for especie, kg in pendientes.items():
        if especie not in t["kilos"]:
            continue
        for (e, prod_id), (cantidad, costo) in t["uso"].items():
            if e != especie:
                continue
            tasa = cantidad / t["kilos"][especie]          # unidades de producto por kilo de fruta
            necesita = tasa * kg
            costo_unitario = costo / cantidad if cantidad else CERO  # costo historico promedio; solo referencial
            fila = requerido.setdefault(prod_id, {"cantidad": CERO, "costo": CERO})
            fila["cantidad"] += necesita
            fila["costo"] += necesita * costo_unitario
            detalle.append({"especie": especie, "producto_id": prod_id, "kilos_pendientes": float(kg),
                            "por_1000_kg": float(tasa * 1000), "cantidad": float(necesita), "costo_estimado": float(necesita * costo_unitario)})
    productos = {p.id: p for p in db.scalars(select(Producto).where(Producto.id.in_(list(requerido)))).unique()} if requerido else {}
    lineas = []
    for prod_id, fila in requerido.items():
        p = productos[prod_id]
        fisico = inv.fisico(db, prod_id, bodega_id=d.bodega_id)
        reservado = inv.reservado(db, prod_id, bodega_id=d.bodega_id) if d.bodega_id else inv.reservado(db, prod_id)
        disponible = max(CERO, fisico - reservado)
        faltante = max(CERO, fila["cantidad"] - disponible)
        lineas.append({
            "producto_id": prod_id, "producto_codigo": p.codigo, "producto": p.nombre, "subfamilia": p.subfamilia.nombre,
            "unidad": p.unidad_base.codigo, "cantidad_requerida": float(fila["cantidad"]), "stock_fisico": float(fisico),
            "stock_reservado": float(reservado), "stock_disponible": float(disponible), "faltante": float(faltante),
            "alcanza": faltante == 0, "costo_estimado": float(fila["costo"]),
            "cobertura": float(min(Decimal(1), disponible / fila["cantidad"])) if fila["cantidad"] else 1.0})
    nombres = {pid: p.nombre for pid, p in productos.items()}
    unidades = {pid: p.unidad_base.codigo for pid, p in productos.items()}
    for x in detalle:
        x["producto"], x["unidad"] = nombres[x["producto_id"]], unidades[x["producto_id"]]
    lineas.sort(key=lambda x: (x["alcanza"], x["producto"]))
    detalle.sort(key=lambda x: (x["especie"], x["producto"]))
    kilos_total = sum((kg for e, kg in pendientes.items() if e in t["kilos"]), CERO)
    costo_total = sum((Decimal(str(x["costo_estimado"])) for x in lineas), CERO)
    return ocultar_costos({
        "productos": lineas, "detalle": detalle, "sin_historial": sin_historial,
        "base": [{"especie": e, "procesos": t["procesos"][e], "kilos_historicos": float(t["kilos"][e])} for e in pendientes if e in t["kilos"]],
        "resumen": {"kilos_pendientes": float(kilos_total), "productos": len(lineas), "con_faltante": sum(1 for x in lineas if not x["alcanza"]),
                    "costo_estimado": float(costo_total), "costo_por_kilo": float(costo_total / kilos_total) if kilos_total else None},
    }, ctx.ver_costos)
