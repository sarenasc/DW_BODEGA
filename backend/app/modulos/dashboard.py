"""Dashboard principal y de antiguedad."""
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.util import dec, dia_local, hoy, inicio_dia_utc, json_valor, ocultar_costos
from app.modelos import Alerta, ExcepcionFifo, MovimientoInventario, Producto, ReservaStock, Subfamilia
from app.servicios import costeo
from app.servicios import reportes as svc

from .alertas import resumen_alertas
from .reportes import filtros_de

router = APIRouter(prefix="/api", tags=["Dashboard"])
SALIDAS = ("CONSUMO", "SALIDA", "MERMA", "VENCIMIENTO", "ANULACION")


def _top(grupos: dict, n: int = 10, clave: str = "valor") -> list[dict]:
    return [{"nombre": k, clave: float(v)} for k, v in sorted(grupos.items(), key=lambda kv: -kv[1])[:n] if v]


@router.get("/dashboard")
def dashboard(desde: date | None = None, hasta: date | None = None, bodega_id: int | None = None,
              familia_id: int | None = None, subfamilia_id: int | None = None, producto_id: int | None = None,
              especie: str | None = None, proceso_id: int | None = None, productor: str | None = None,
              temporada_id: int | None = None, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("dashboard:ver"))):
    hoy_ = hoy()
    hasta = hasta or hoy_
    desde = desde or hasta - timedelta(days=29)
    f = filtros_de(ctx, desde, hasta, bodega_id, familia_id, subfamilia_id, producto_id, proceso_id, temporada_id, especie, productor)

    # ---- inventario (foto actual; no depende del rango de fechas)
    existencias = [svc._fila_existencia(e) for e in svc.existencias_con_stock(db, f)]
    total = sum((x["valor"] for x in existencias), Decimal(0))
    por = {k: defaultdict(Decimal) for k in ("bodega", "familia", "subfamilia")}
    for x in existencias:
        for k in por:
            por[k][x[k]] += x["valor"]
    fisico_prod: dict[int, Decimal] = defaultdict(Decimal)
    for x in existencias:
        fisico_prod[x["producto_id"]] += x["cantidad"]
    rangos = svc.rangos_antiguedad(db, ctx.empresa_id)
    limite_antiguo = rangos[1][2] if len(rangos) > 2 else 60  # segundo limite configurado (60 por defecto)
    antiguas = [x for x in existencias if x["dias"] > limite_antiguo]
    vencidas = [x for x in existencias if x["fecha_vencimiento"] and x["fecha_vencimiento"] < hoy_]
    por_vencer = [x for x in existencias if x["fecha_vencimiento"] and hoy_ <= x["fecha_vencimiento"] <= hoy_ + timedelta(days=30)]

    # ---- bajo minimo
    cp = select(Producto).where(Producto.empresa_id == ctx.empresa_id, Producto.activo.is_(True), Producto.stock_minimo.is_not(None))
    if familia_id or ctx.familias is not None:
        cp = cp.join(Subfamilia, Producto.subfamilia_id == Subfamilia.id)
        if familia_id:
            cp = cp.where(Subfamilia.familia_id == familia_id)
        if ctx.familias is not None:
            cp = cp.where(Subfamilia.familia_id.in_(ctx.familias))
    if subfamilia_id:
        cp = cp.where(Producto.subfamilia_id == subfamilia_id)
    if producto_id:
        cp = cp.where(Producto.id == producto_id)
    bajo = []
    if not bodega_id:  # el minimo se define por producto, no por bodega
        for p in db.scalars(cp).unique():
            actual = fisico_prod.get(p.id, Decimal(0))
            if actual <= p.stock_minimo:
                bajo.append({"producto_id": p.id, "producto": p.nombre, "stock": float(actual), "minimo": float(p.stock_minimo),
                             "unidad": p.unidad_base.codigo,
                             "nivel": "AGOTADO" if actual <= 0 else "CRITICO" if p.stock_critico is not None and actual <= p.stock_critico else "BAJO"})
    reservado = dec(db.scalar(select(func.coalesce(func.sum(ReservaStock.cantidad - ReservaStock.cantidad_consumida), 0)).where(
        ReservaStock.empresa_id == ctx.empresa_id, ReservaStock.estado == "ACTIVA")))

    # ---- consumos del periodo (las anulaciones se suman con su signo: el neto es el consumo real)
    movs = svc.movimientos(db, f, SALIDAS)
    por_dia: dict[date, Decimal] = defaultdict(Decimal)
    por_producto: dict[str, Decimal] = defaultdict(Decimal)
    for m in movs:
        por_dia[dia_local(m["fecha"])] += -m["costo_total"]
        por_producto[m["producto"]] += -m["costo_total"]
    serie = [{"fecha": (desde + timedelta(days=i)).isoformat(), "costo": float(por_dia.get(desde + timedelta(days=i), 0))}
             for i in range((hasta - desde).days + 1)]
    semana = sum((v for d, v in por_dia.items() if d > hoy_ - timedelta(days=7)), Decimal(0))

    # ---- costos de proceso
    kw = dict(desde=desde, hasta=hasta, temporada_id=temporada_id, especie=especie or None, productor=productor or None,
              proceso_id=proceso_id, bodega_id=bodega_id, familia_id=familia_id, subfamilia_id=subfamilia_id,
              producto_id=producto_id, bodegas=ctx.bodegas, familias=ctx.familias)
    por_proceso = costeo.analisis(db, ctx.empresa_id, "proceso", **kw)
    por_especie = costeo.analisis(db, ctx.empresa_id, "especie", **kw)
    costo_procesos = sum(Decimal(str(x["costo"])) for x in por_proceso)
    kilos = sum(Decimal(str(x["kilos"])) for x in por_proceso)

    fuera_fifo = db.scalar(select(func.count()).select_from(ExcepcionFifo).join(
        MovimientoInventario, ExcepcionFifo.movimiento_id == MovimientoInventario.id).where(
        MovimientoInventario.empresa_id == ctx.empresa_id, ExcepcionFifo.fecha >= inicio_dia_utc(desde)))
    ultimos = svc.movimientos(db, svc.Filtros(empresa_id=ctx.empresa_id, bodega_id=bodega_id, familia_id=familia_id,
                                              producto_id=producto_id, bodegas=ctx.bodegas, familias=ctx.familias))[:10]
    mas_antigua = min(existencias, key=lambda x: x["fecha_ingreso"]) if existencias else None
    edad = (sum((x["dias"] * x["valor"] for x in existencias), Decimal(0)) / total) if total else \
        (Decimal(sum(x["dias"] for x in existencias)) / len(existencias) if existencias else Decimal(0))

    datos = {
        "periodo": {"desde": desde.isoformat(), "hasta": hasta.isoformat()},
        "valor_total_inventario": float(total),
        "valor_por_bodega": _top(por["bodega"]), "valor_por_familia": _top(por["familia"]),
        "valor_por_subfamilia": _top(por["subfamilia"]),
        "stock_total": {"existencias": len(existencias), "productos": len(fisico_prod), "lotes": len({x["lote_id"] for x in existencias if x["lote_id"]}),
                        "reservado": float(reservado)},
        "stock_antiguo": {"dias": limite_antiguo, "existencias": len(antiguas), "valor_inventario": float(sum((x["valor"] for x in antiguas), Decimal(0)))},
        "stock_bajo_minimo": {"cantidad": len(bajo), "productos": sorted(bajo, key=lambda b: b["stock"] / b["minimo"] if b["minimo"] else 0)[:10]},
        "proximos_a_vencer": {"cantidad": len({x["lote_id"] for x in por_vencer}), "valor_inventario": float(sum((x["valor"] for x in por_vencer), Decimal(0))),
                              "lotes": [{"lote_id": x["lote_id"], "lote": x["lote"], "producto": x["producto"],
                                         "fecha_vencimiento": json_valor(x["fecha_vencimiento"]),
                                         "dias": (x["fecha_vencimiento"] - hoy_).days, "cantidad": float(x["cantidad"]), "unidad": x["unidad"]}
                                        for x in sorted(por_vencer, key=lambda x: x["fecha_vencimiento"])[:8]]},
        "vencidos": {"cantidad": len({x["lote_id"] for x in vencidas}), "valor_inventario": float(sum((x["valor"] for x in vencidas), Decimal(0)))},
        "consumo_del_dia": {"costo": float(por_dia.get(hoy_, 0)), "movimientos": sum(1 for m in movs if dia_local(m["fecha"]) == hoy_)},
        "consumo_semanal": {"costo": float(semana)},
        "consumo_periodo": {"costo": float(sum(por_dia.values(), Decimal(0))), "serie": serie},
        "costo_por_especie": por_especie[:10], "costo_por_proceso": por_proceso[:10],
        "costo_por_kilo": {"costo": float(costo_procesos), "kilos": float(kilos),
                           "costo_por_kilo": float(costo_procesos / kilos) if kilos else None,
                           "estado_kilos": "PROVISORIO" if any(x["procesos_provisorios"] for x in por_proceso) else "DEFINITIVO"},
        "productos_mas_consumidos": _top(por_producto, 10, "costo"),
        "consumos_fuera_de_fifo": fuera_fifo,
        "ultimos_movimientos": [{k: json_valor(m[k]) for k in ("id", "fecha", "tipo", "tipo_codigo", "producto", "lote", "cantidad",
                                                              "unidad", "costo_total", "usuario", "proceso", "bodega")} for m in ultimos],
        "antiguedad": {
            "rangos": [{"rango": n, "existencias": sum(1 for x in existencias if x["dias"] >= d and (h is None or x["dias"] <= h)),
                        "valor_inventario": float(sum((x["valor"] for x in existencias if x["dias"] >= d and (h is None or x["dias"] <= h)), Decimal(0)))}
                       for n, d, h in rangos],
            "edad_promedio_dias": round(float(edad), 1),
            "lote_mas_antiguo": {"lote": mas_antigua["lote"], "producto": mas_antigua["producto"], "dias": mas_antigua["dias"],
                                 "fecha_ingreso": json_valor(mas_antigua["fecha_ingreso"]), "existencia_id": mas_antigua["existencia_id"],
                                 "codigo_publico": mas_antigua["codigo_publico"]} if mas_antigua else None,
            "productos_con_stock_antiguo": len({x["producto_id"] for x in antiguas}),
        },
        "alertas": resumen_alertas(db, ctx) if ctx.puede("alertas:ver") else None,
    }
    if not ctx.ver_costos:
        datos = ocultar_costos(datos, False)
        for k in ("valor_por_bodega", "valor_por_familia", "valor_por_subfamilia", "costo_por_especie", "costo_por_proceso",
                  "productos_mas_consumidos"):
            datos[k] = []
        datos["consumo_periodo"]["serie"] = []
        datos["costo_por_kilo"] = None
        for k in ("consumo_del_dia", "consumo_semanal", "consumo_periodo"):
            datos[k]["costo"] = None
    return datos


__all__ = ["router", "Alerta"]
