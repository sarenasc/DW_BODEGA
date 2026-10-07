"""Operaciones avanzadas: inventario fisico, prestamos, fraccionamiento / sublotes y apertura de envase."""
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar, siguiente_numero
from app.core.crud import paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import CERO, a_dict, ahora, hoy, ocultar_costos, q6
from app.modelos import (Bodega, ConteoInventario, DetalleConteoInventario, Existencia, Prestamo, Ubicacion, Usuario)
from app.servicios import inventario as svc
from app.servicios.alertas import crear_alerta
from app.servicios.catalogo import a_unidad_base, politica_efectiva
from app.servicios.lotes import crear_lote

from .bodegas import _descendientes, bodega_de
from .inventario import existencia_dict, obtener_existencia, resolver_codigo

router = APIRouter(prefix="/api", tags=["Operaciones"])


# ---------------------------------------------------------------- inventario fisico

class ConteoEntrada(BaseModel):
    bodega_id: int
    ubicacion_id: int | None = None
    observaciones: str | None = None


def _conteo(db: Session, c: ConteoInventario, detalle: bool = False) -> dict:
    contadas = [d for d in c.detalles if d.cantidad_contada is not None]
    con_dif = [d for d in contadas if d.diferencia]
    d = a_dict(c, bodega=db.get(Bodega, c.bodega_id).nombre,
               ubicacion=db.get(Ubicacion, c.ubicacion_id).codigo_completo if c.ubicacion_id else None,
               usuario=db.get(Usuario, c.usuario_id).nombre if c.usuario_id else None,
               lineas=len(c.detalles), contadas=len(contadas), con_diferencia=len(con_dif))
    if detalle:
        filas = []
        for x in sorted(c.detalles, key=lambda x: x.id):
            e = db.get(Existencia, x.existencia_id)
            filas.append(a_dict(x, codigo_publico=e.codigo_publico, producto=e.producto.nombre, unidad=e.unidad.codigo,
                                lote=e.lote.codigo if e.lote else None,
                                ubicacion=e.ubicacion.codigo_completo if e.ubicacion else None,
                                valor_diferencia=(x.diferencia * e.costo_unitario) if x.diferencia is not None else None))
        d["detalles"] = filas
    return d


def _obtener_conteo(db: Session, ctx: Contexto, id_: int) -> ConteoInventario:
    c = db.get(ConteoInventario, id_)
    if not c or c.empresa_id != ctx.empresa_id:
        raise no_encontrado("Conteo")
    ctx.exigir_bodega(c.bodega_id)
    return c


@router.get("/conteos")
def listar_conteos(estado: str | None = None, bodega_id: int | None = None, pagina: int = 1, tam: int = Query(50, le=200),
                   db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:ver"))):
    c = select(ConteoInventario).where(ConteoInventario.empresa_id == ctx.empresa_id)
    if estado:
        c = c.where(ConteoInventario.estado == estado)
    if bodega_id:
        c = c.where(ConteoInventario.bodega_id == bodega_id)
    if ctx.bodegas is not None:
        c = c.where(ConteoInventario.bodega_id.in_(ctx.bodegas))
    return paginar(db, c.order_by(ConteoInventario.id.desc()), pagina, tam, lambda x: _conteo(db, x))


@router.get("/conteos/{id_}")
def ver_conteo(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:ver"))):
    return ocultar_costos(_conteo(db, _obtener_conteo(db, ctx, id_), True), ctx.ver_costos)


@router.post("/conteos", status_code=201)
def crear_conteo(d: ConteoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:contar"))):
    """Abre el conteo y toma la foto del stock del sistema en la bodega o ubicacion elegida."""
    bodega_de(db, ctx, d.bodega_id)
    c = ConteoInventario(empresa_id=ctx.empresa_id, numero=siguiente_numero(db, ctx.empresa_id, "conteo", "CNT", 6),
                         bodega_id=d.bodega_id, ubicacion_id=d.ubicacion_id, usuario_id=ctx.usuario.id, observaciones=d.observaciones)
    q = select(Existencia).where(Existencia.bodega_id == d.bodega_id, Existencia.cantidad_fisica > 0, Existencia.estado != "ANULADA")
    if d.ubicacion_id:
        u = db.get(Ubicacion, d.ubicacion_id)
        if not u or u.bodega_id != d.bodega_id:
            raise ErrorNegocio("UBICACION", "La ubicacion no pertenece a la bodega.")
        q = q.where(Existencia.ubicacion_id.in_([u.id] + _descendientes(db, u.id)))
    for e in db.scalars(q).unique():
        if ctx.familias is None or e.producto.subfamilia.familia_id in ctx.familias:
            c.detalles.append(DetalleConteoInventario(existencia_id=e.id, producto_id=e.producto_id, cantidad_sistema=e.cantidad_fisica))
    db.add(c)
    db.flush()
    auditar(db, ctx, "conteo", c.id, "CREAR", nuevo={"numero": c.numero, "lineas": len(c.detalles)})
    return _conteo(db, c, True)


class LineaConteo(BaseModel):
    existencia_id: int | None = None
    codigo: str | None = None  # lo leido por el lector QR
    cantidad: Decimal = Field(ge=0)
    observacion: str | None = None


@router.post("/conteos/{id_}/contar")
def contar(id_: int, d: LineaConteo, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:contar"))):
    """Registra la cantidad encontrada y muestra la diferencia contra el sistema."""
    c = _obtener_conteo(db, ctx, id_)
    if c.estado != "ABIERTO":
        raise ErrorNegocio("ESTADO", f"El conteo esta {c.estado}.", 409)
    e = obtener_existencia(db, ctx, d.existencia_id) if d.existencia_id else resolver_codigo(db, ctx, d.codigo or "")
    if e.bodega_id != c.bodega_id:
        raise ErrorNegocio("OTRA_BODEGA", f"{e.codigo_publico} pertenece a {e.bodega.nombre}: registre un traslado.", 409)
    linea = next((x for x in c.detalles if x.existencia_id == e.id), None)
    fuera_de_lugar = False
    if linea is None:  # existe en el sistema pero no en la ubicacion contada
        linea = DetalleConteoInventario(existencia_id=e.id, producto_id=e.producto_id, cantidad_sistema=e.cantidad_fisica)
        c.detalles.append(linea)
        fuera_de_lugar = c.ubicacion_id is not None
    linea.cantidad_sistema = e.cantidad_fisica  # se compara contra el saldo vigente al momento de contar
    linea.cantidad_contada = q6(d.cantidad)
    linea.diferencia = linea.cantidad_contada - linea.cantidad_sistema
    linea.contado_en = ahora()
    linea.observacion = d.observacion or ("Encontrada fuera de su ubicacion registrada" if fuera_de_lugar else linea.observacion)
    db.flush()
    return ocultar_costos({"linea": a_dict(linea, codigo_publico=e.codigo_publico, producto=e.producto.nombre, unidad=e.unidad.codigo,
                                           valor_diferencia=linea.diferencia * e.costo_unitario),
                           "conteo": _conteo(db, c)}, ctx.ver_costos)


@router.post("/conteos/{id_}/cerrar")
def cerrar_conteo(id_: int, no_contadas_en_cero: bool = False, db: Session = Depends(get_db),
                  ctx: Contexto = Depends(requiere("conteos:contar"))):
    """Termina el conteo y lo deja en revision. Los ajustes no se aplican hasta la autorizacion."""
    c = _obtener_conteo(db, ctx, id_)
    if c.estado != "ABIERTO":
        raise ErrorNegocio("ESTADO", f"El conteo esta {c.estado}.", 409)
    if no_contadas_en_cero:
        for x in c.detalles:
            if x.cantidad_contada is None:
                x.cantidad_contada, x.diferencia, x.contado_en = CERO, -x.cantidad_sistema, ahora()
                x.observacion = "No encontrada"
    c.estado = "EN_REVISION"
    difs = [x for x in c.detalles if x.diferencia]
    if difs:
        crear_alerta(db, c.empresa_id, "DIFERENCIA_INVENTARIO", f"Diferencias en conteo {c.numero}",
                     f"{len(difs)} existencia(s) con diferencia entre lo contado y el sistema. Requiere autorizacion.",
                     entidad="conteo", entidad_id=c.id, bodega_id=c.bodega_id, usuario_id=ctx.usuario.id)
    auditar(db, ctx, "conteo", c.id, "CERRAR", nuevo={"diferencias": len(difs)})
    return ocultar_costos(_conteo(db, c, True), ctx.ver_costos)


@router.post("/conteos/{id_}/autorizar")
def autorizar_conteo(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:autorizar"))):
    """Genera los ajustes (movimientos AJUSTE_POSITIVO / AJUSTE_NEGATIVO) de las diferencias aprobadas."""
    c = _obtener_conteo(db, ctx, id_)
    if c.estado != "EN_REVISION":
        raise ErrorNegocio("ESTADO", "Solo un conteo EN_REVISION puede autorizarse.", 409)
    ajustes = 0
    for x in c.detalles:
        if x.cantidad_contada is None or x.movimiento_ajuste_id:
            continue
        e = db.get(Existencia, x.existencia_id)
        diferencia = x.cantidad_contada - e.cantidad_fisica  # contra el saldo actual: pudo haber consumo entre medio
        if diferencia == 0:
            continue
        m = svc.ajustar(db, ctx, e, diferencia, motivo_texto=f"Inventario fisico {c.numero}")
        x.movimiento_ajuste_id, x.diferencia = m.id, diferencia
        ajustes += 1
    c.estado, c.autorizado_por, c.fecha_autorizacion = "AUTORIZADO", ctx.usuario.id, ahora()
    auditar(db, ctx, "conteo", c.id, "AUTORIZAR", nuevo={"ajustes": ajustes})
    from app.modelos import Alerta
    for a in db.scalars(select(Alerta).where(Alerta.entidad == "conteo", Alerta.entidad_id == c.id,
                                             Alerta.estado.in_(("NUEVA", "LEIDA", "EN_GESTION")))):
        a.estado, a.resuelta_por, a.fecha_resolucion, a.observacion = "RESUELTA", ctx.usuario.id, ahora(), "Ajustes autorizados."
    db.flush()
    return ocultar_costos({**_conteo(db, c, True), "ajustes_generados": ajustes}, ctx.ver_costos)


@router.post("/conteos/{id_}/anular")
def anular_conteo(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("conteos:contar"))):
    c = _obtener_conteo(db, ctx, id_)
    if c.estado in ("AUTORIZADO", "ANULADO"):
        raise ErrorNegocio("ESTADO", f"El conteo esta {c.estado}.", 409)
    c.estado = "ANULADO"
    auditar(db, ctx, "conteo", c.id, "ANULAR")
    return _conteo(db, c)


# ---------------------------------------------------------------- prestamos

class PrestamoEntrada(BaseModel):
    existencia_id: int
    cantidad: Decimal
    unidad_id: int | None = None
    persona: str
    area: str | None = None
    fecha_devolucion_esperada: date | None = None
    observacion: str | None = None


def _prestamo(db: Session, p: Prestamo) -> dict:
    e = db.get(Existencia, p.existencia_id)
    vencido = p.estado in ("ACTIVO", "PARCIAL") and p.fecha_devolucion_esperada is not None and p.fecha_devolucion_esperada < hoy()
    return a_dict(p, producto=e.producto.nombre, codigo_publico=e.codigo_publico, unidad=e.unidad.codigo,
                  bodega=e.bodega.nombre, pendiente=p.cantidad - p.cantidad_devuelta, vencido=vencido)


@router.get("/prestamos")
def listar_prestamos(estado: str | None = None, vencidos: bool = False, pagina: int = 1, tam: int = Query(50, le=200),
                     db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("prestamos:ver"))):
    c = select(Prestamo).where(Prestamo.empresa_id == ctx.empresa_id)
    if estado:
        c = c.where(Prestamo.estado == estado)
    if vencidos:
        c = c.where(Prestamo.estado.in_(("ACTIVO", "PARCIAL")), Prestamo.fecha_devolucion_esperada < hoy())
    return paginar(db, c.order_by(Prestamo.id.desc()), pagina, tam, lambda p: _prestamo(db, p))


@router.post("/prestamos", status_code=201)
def crear_prestamo(d: PrestamoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("prestamos:administrar"))):
    e = obtener_existencia(db, ctx, d.existencia_id)
    if not d.persona.strip():
        raise ErrorNegocio("PERSONA", "Debe indicar a quien se presta.")
    base, _ = a_unidad_base(db, e.producto, d.cantidad, d.unidad_id)
    m, _info = svc.registrar_salida(db, ctx, e, base, "PRESTAMO", evaluar_fifo=False, motivo_texto=f"Prestamo a {d.persona}",
                                    observacion=d.observacion, cantidad_ingresada=d.cantidad, unidad_ingresada_id=d.unidad_id or e.unidad_id)
    p = Prestamo(empresa_id=ctx.empresa_id, numero=siguiente_numero(db, ctx.empresa_id, "prestamo", "PRE", 6),
                 existencia_id=e.id, producto_id=e.producto_id, cantidad=q6(base), persona=d.persona.strip(), area=d.area,
                 fecha_devolucion_esperada=d.fecha_devolucion_esperada, observacion=d.observacion, usuario_id=ctx.usuario.id,
                 movimiento_salida_id=m.id)
    db.add(p)
    db.flush()
    auditar(db, ctx, "prestamo", p.id, "CREAR", nuevo={"numero": p.numero, "persona": p.persona, "cantidad": float(base)})
    return _prestamo(db, p)


class Devolucion(BaseModel):
    cantidad: Decimal | None = None  # vacio = todo lo pendiente
    observacion: str | None = None


@router.post("/prestamos/{id_}/devolver")
def devolver(id_: int, d: Devolucion, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("prestamos:administrar"))):
    p = db.get(Prestamo, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Prestamo")
    if p.estado not in ("ACTIVO", "PARCIAL"):
        raise ErrorNegocio("ESTADO", f"El prestamo esta {p.estado}.", 409)
    pendiente = p.cantidad - p.cantidad_devuelta
    cantidad = q6(d.cantidad) if d.cantidad is not None else pendiente
    if cantidad <= 0 or cantidad > pendiente:
        raise ErrorNegocio("CANTIDAD", f"La devolucion debe ser mayor que cero y no superar lo pendiente ({pendiente.normalize():f}).")
    e = db.get(Existencia, p.existencia_id)
    svc.bloquear_producto(db, e.producto_id)
    svc.aumentar(db, e, cantidad)
    svc.movimiento(db, ctx, e, "DEVOLUCION_PRESTAMO", cantidad, bodega_destino_id=e.bodega_id, ubicacion_destino_id=e.ubicacion_id,
                   motivo_texto=f"Devolucion de {p.numero}", observacion=d.observacion)
    p.cantidad_devuelta += cantidad
    if p.cantidad_devuelta >= p.cantidad:
        p.estado, p.fecha_devolucion_real = "DEVUELTO", ahora()
    else:
        p.estado = "PARCIAL"
    auditar(db, ctx, "prestamo", p.id, "DEVOLVER", nuevo={"cantidad": float(cantidad), "estado": p.estado})
    db.flush()
    return _prestamo(db, p)


# ---------------------------------------------------------------- fraccionamiento y sublotes

class Parte(BaseModel):
    cantidad: Decimal = Field(gt=0)
    ubicacion_id: int | None = None


class Fraccionamiento(BaseModel):
    partes: list[Parte] = Field(min_length=1, max_length=200)
    crear_sublotes: bool = True
    observacion: str | None = None


@router.post("/existencias/{id_}/fraccionar", status_code=201)
def fraccionar(id_: int, d: Fraccionamiento, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:editar"))):
    """Divide una existencia en varias (p. ej. tambor de 200 L en 4 bidones de 50 L), con sublotes opcionales."""
    origen = obtener_existencia(db, ctx, id_)
    svc.bloquear_producto(db, origen.producto_id)
    db.refresh(origen)
    svc.validar_estado_consumible(ctx, origen)
    total = sum((q6(p.cantidad) for p in d.partes), CERO)
    if total > origen.cantidad_fisica:
        raise ErrorNegocio("STOCK_INSUFICIENTE", f"Las partes suman {total.normalize():f} y la existencia tiene "
                           f"{origen.cantidad_fisica.normalize():f} {origen.unidad.codigo}.", 409)
    politica = politica_efectiva(origen.producto)
    con_sublotes = d.crear_sublotes and origen.lote is not None and bool(politica["permite_sublotes"])
    valor_origen = svc.costo_salida(db, origen, total)
    svc.descontar(db, origen, total)
    salida = svc.movimiento(db, ctx, origen, "FRACCIONAMIENTO_SALIDA", -total, costo_total=-valor_origen,
                            bodega_origen_id=origen.bodega_id, ubicacion_origen_id=origen.ubicacion_id, observacion=d.observacion)
    nuevas, asignado = [], CERO
    for i, parte in enumerate(d.partes):
        cant = q6(parte.cantidad)
        valor = valor_origen - asignado if i == len(d.partes) - 1 else (cant * origen.costo_unitario).quantize(Decimal("0.01"))
        asignado += valor
        lote = origen.lote
        if con_sublotes:
            lote = crear_lote(db, ctx, origen.producto, fecha=origen.fecha_ingreso, lote_padre=origen.lote,
                              fecha_fabricacion=origen.lote.fecha_fabricacion, fecha_vencimiento=origen.lote.fecha_vencimiento,
                              politica={**politica, "usa_vencimiento": False})
        ubicacion = parte.ubicacion_id if parte.ubicacion_id is not None else origen.ubicacion_id
        svc._ubicacion_valida(db, origen.bodega_id, ubicacion, False, f"Parte {i + 1}")
        # La parte hereda costo unitario y fecha de ingreso: fraccionar no genera resultado ni rejuvenece el stock.
        e = svc.nueva_existencia(db, ctx, producto=origen.producto, lote=lote, bodega_id=origen.bodega_id, ubicacion_id=ubicacion,
                                 cantidad=cant, costo_unitario=origen.costo_unitario, fecha_ingreso=origen.fecha_ingreso,
                                 granularidad="POR_ENVASE", padre=origen, proveedor_id=origen.proveedor_id, moneda=origen.moneda,
                                 fecha_costo=origen.fecha_costo)
        svc.aumentar(db, e, cant)
        svc.movimiento(db, ctx, e, "FRACCIONAMIENTO_ENTRADA", cant, costo_total=valor, bodega_destino_id=e.bodega_id,
                       ubicacion_destino_id=ubicacion, observacion=f"Desde {origen.codigo_publico}")
        nuevas.append(e)
    auditar(db, ctx, "existencia", origen.id, "FRACCIONAR", nuevo={
        "lote_origen": origen.lote.codigo if origen.lote else None, "cantidad_origen": float(total),
        "partes": [{"existencia": e.codigo_publico, "lote": e.lote.codigo if e.lote else None, "cantidad": float(e.cantidad_inicial)} for e in nuevas],
        "movimiento": salida.id})
    db.refresh(origen)
    return ocultar_costos({"origen": existencia_dict(db, origen), "nuevas": [existencia_dict(db, e) for e in nuevas]}, ctx.ver_costos)


# ---------------------------------------------------------------- apertura de envase

@router.post("/existencias/{id_}/abrir")
def abrir_envase(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("movimientos:crear"))):
    """Registra fecha, usuario y cantidad restante al abrir. Calcula la vida util tras apertura si esta configurada."""
    e = obtener_existencia(db, ctx, id_)
    if e.fecha_apertura is not None:
        raise ErrorNegocio("YA_ABIERTA", f"El envase ya fue abierto el {e.fecha_apertura:%d-%m-%Y}.", 409)
    if e.cantidad_fisica <= 0:
        raise ErrorNegocio("SIN_STOCK", "La existencia no tiene stock.")
    dias = politica_efectiva(e.producto)["vida_util_abierto_dias"]
    e.fecha_apertura, e.abierta_por = ahora(), ctx.usuario.id
    e.vence_abierta = hoy() + timedelta(days=int(dias)) if dias else None
    auditar(db, ctx, "existencia", e.id, "ABRIR_ENVASE", nuevo={"cantidad_restante": float(e.cantidad_fisica),
                                                               "vence_abierta": e.vence_abierta.isoformat() if e.vence_abierta else None})
    db.flush()
    return ocultar_costos(existencia_dict(db, e, True), ctx.ver_costos)
