"""Documentos de inventario, existencias, stock (fisico / reservado / disponible), movimientos y etiquetas QR."""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar, siguiente_numero
from app.core.crud import paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict, ahora, dec, inicio_dia_utc, json_valor, ocultar_costos
from app.modelos import (Bodega, DetalleDocumentoInventario, DocumentoInventario, Existencia, Lote, MotivoMovimiento,
                         MovimientoInventario, Proceso, Producto, Proveedor, ReservaStock, Subfamilia, Temporada,
                         TipoMovimiento, Ubicacion, UnidadMedida, Usuario)
from app.servicios import inventario as svc
from app.servicios.catalogo import politica_efectiva

router = APIRouter(prefix="/api", tags=["Inventario"])


# ---------------------------------------------------------------- serializadores

def existencia_dict(db: Session, e: Existencia, detalle: bool = False) -> dict:
    lote = e.lote
    d = {
        "id": e.id, "codigo_publico": e.codigo_publico, "producto_id": e.producto_id, "producto": e.producto.nombre,
        "producto_codigo": e.producto.codigo, "familia": e.producto.subfamilia.familia.nombre,
        "subfamilia": e.producto.subfamilia.nombre, "lote_id": e.lote_id, "lote": lote.codigo if lote else None,
        "lote_estado": lote.estado if lote else None,
        "fecha_vencimiento": json_valor(lote.fecha_vencimiento) if lote else None, "bodega_id": e.bodega_id,
        "bodega": e.bodega.nombre, "ubicacion_id": e.ubicacion_id,
        "ubicacion": e.ubicacion.codigo_completo if e.ubicacion else None, "granularidad": e.granularidad,
        "envases": e.envases, "fecha_ingreso": json_valor(e.fecha_ingreso), "cantidad_inicial": float(e.cantidad_inicial),
        "cantidad_fisica": float(e.cantidad_fisica), "unidad_id": e.unidad_id, "unidad": e.unidad.codigo,
        "costo_unitario": float(e.costo_unitario), "moneda": e.moneda,
        "valor_inicial": float(e.cantidad_inicial * e.costo_unitario),
        "valor_disponible": float(e.cantidad_fisica * e.costo_unitario), "estado": e.estado,
        "fecha_apertura": json_valor(e.fecha_apertura), "vence_abierta": json_valor(e.vence_abierta),
        "existencia_padre_id": e.existencia_padre_id, "etiquetas_impresas": e.etiquetas_impresas,
    }
    if detalle:
        res = svc.reservado(db, e.producto_id, existencia_id=e.id)
        d["cantidad_reservada"] = float(res)
        d["cantidad_disponible"] = float(max(Decimal(0), e.cantidad_fisica - res))
        d["token_qr"] = e.token_qr
        d["proveedor"] = db.get(Proveedor, e.proveedor_id).nombre if e.proveedor_id else None
        d["fecha_costo"] = json_valor(e.fecha_costo)
        d["unidad_consumo_id"] = e.producto.unidad_consumo_id or e.producto.unidad_base_id
        if e.detalle_origen_id:
            det = db.get(DetalleDocumentoInventario, e.detalle_origen_id)
            doc = db.get(DocumentoInventario, det.documento_id)
            d["documento_origen"] = {"id": doc.id, "numero": doc.numero, "tipo_documento": doc.tipo_documento,
                                     "numero_documento": doc.numero_documento}
    return d


def _alcance_existencias(c, ctx: Contexto):
    c = c.where(Existencia.empresa_id == ctx.empresa_id)
    if ctx.bodegas is not None:
        c = c.where(Existencia.bodega_id.in_(ctx.bodegas))
    if ctx.familias is not None:
        c = c.where(Existencia.producto_id.in_(
            select(Producto.id).join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).where(Subfamilia.familia_id.in_(ctx.familias))))
    return c


def obtener_existencia(db: Session, ctx: Contexto, id_: int) -> Existencia:
    e = db.get(Existencia, id_)
    if not e or e.empresa_id != ctx.empresa_id:
        raise no_encontrado("Existencia")
    ctx.exigir_bodega(e.bodega_id)
    ctx.exigir_familia(e.producto.subfamilia.familia_id)
    return e


def resolver_codigo(db: Session, ctx: Contexto, codigo: str) -> Existencia:
    """Acepta lo que entregue un lector: la URL del QR, el token o el codigo publico INV-..."""
    crudo = (codigo or "").strip()
    token = crudo.rstrip("/").split("/")[-1].split("token=")[-1].split("&")[0].strip()
    e = db.scalar(select(Existencia).where(or_(Existencia.token_qr == token.upper(),
                                               func.upper(Existencia.codigo_publico) == token.upper())))
    if not e or e.empresa_id != ctx.empresa_id:
        raise ErrorNegocio("QR_DESCONOCIDO", "El codigo leido no corresponde a ninguna existencia.", 404)
    ctx.exigir_bodega(e.bodega_id)
    ctx.exigir_familia(e.producto.subfamilia.familia_id)
    return e


# ---------------------------------------------------------------- existencias

@router.get("/existencias")
def listar_existencias(q: str | None = None, producto_id: int | None = None, bodega_id: int | None = None,
                       lote_id: int | None = None, ubicacion_id: int | None = None, estado: str | None = None,
                       con_stock: bool = True, sin_ubicacion: bool = False, pagina: int = Query(1, ge=1),
                       tam: int = Query(50, le=1000), db: Session = Depends(get_db),
                       ctx: Contexto = Depends(requiere("inventario:ver"))):
    c = _alcance_existencias(select(Existencia).join(Producto, Existencia.producto_id == Producto.id)
                             .outerjoin(Lote, Existencia.lote_id == Lote.id), ctx)
    if q:
        p = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Existencia.codigo_publico).like(p), func.lower(Producto.nombre).like(p),
                        func.lower(Producto.codigo).like(p), func.lower(Lote.codigo).like(p)))
    for col, val in ((Existencia.producto_id, producto_id), (Existencia.bodega_id, bodega_id), (Existencia.lote_id, lote_id),
                     (Existencia.ubicacion_id, ubicacion_id), (Existencia.estado, estado)):
        if val:
            c = c.where(col == val)
    if con_stock:
        c = c.where(Existencia.cantidad_fisica > 0)
    if sin_ubicacion:
        c = c.where(Existencia.ubicacion_id.is_(None))
    r = paginar(db, c.order_by(Existencia.fecha_ingreso, Existencia.id), pagina, tam, lambda e: existencia_dict(db, e))
    return ocultar_costos(r, ctx.ver_costos)


@router.get("/existencias/por-codigo")
def por_codigo(codigo: str, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    return ocultar_costos(existencia_dict(db, resolver_codigo(db, ctx, codigo), detalle=True), ctx.ver_costos)


@router.get("/existencias/{id_}")
def ver_existencia(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    e = obtener_existencia(db, ctx, id_)
    d = existencia_dict(db, e, detalle=True)
    d["movimientos"] = [movimiento_dict(db, m) for m in db.scalars(
        select(MovimientoInventario).where(MovimientoInventario.existencia_id == e.id).order_by(MovimientoInventario.id))]
    return ocultar_costos(d, ctx.ver_costos)


class Reubicacion(BaseModel):
    ubicacion_id: int | None


@router.post("/existencias/{id_}/ubicar")
def ubicar(id_: int, d: Reubicacion, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:editar"))):
    """Asigna o cambia la ubicacion dentro de la misma bodega (queda registrado como traslado)."""
    e = obtener_existencia(db, ctx, id_)
    if e.ubicacion_id == d.ubicacion_id:
        return existencia_dict(db, e, detalle=True)
    if e.cantidad_fisica > 0:
        svc.trasladar(db, ctx, e, e.cantidad_fisica, e.bodega_id, d.ubicacion_id, observacion="Asignacion de ubicacion")
    else:
        e.ubicacion_id = d.ubicacion_id
    auditar(db, ctx, "existencia", e.id, "UBICAR", nuevo={"ubicacion_id": d.ubicacion_id})
    return ocultar_costos(existencia_dict(db, e, detalle=True), ctx.ver_costos)


class BloqueoExistencia(BaseModel):
    bloquear: bool
    motivo: str


@router.post("/existencias/{id_}/bloqueo")
def bloquear_existencia(id_: int, d: BloqueoExistencia, db: Session = Depends(get_db),
                        ctx: Contexto = Depends(requiere("lotes:bloquear"))):
    e = obtener_existencia(db, ctx, id_)
    if e.estado in ("ANULADA", "AGOTADA"):
        raise ErrorNegocio("ESTADO", f"La existencia esta {e.estado}.")
    e.estado = "BLOQUEADA" if d.bloquear else "DISPONIBLE"
    auditar(db, ctx, "existencia", e.id, "BLOQUEAR" if d.bloquear else "DESBLOQUEAR", motivo=d.motivo)
    return existencia_dict(db, e)


# ---------------------------------------------------------------- stock

@router.get("/stock")
def stock(agrupar: str = "producto", producto_id: int | None = None, bodega_id: int | None = None,
          familia_id: int | None = None, subfamilia_id: int | None = None, q: str | None = None,
          solo_bajo_minimo: bool = False, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    """Stock fisico, reservado, disponible y comprometido. agrupar: producto | bodega | lote | ubicacion."""
    if agrupar not in ("producto", "bodega", "lote", "ubicacion"):
        raise ErrorNegocio("AGRUPAR", "agrupar debe ser producto, bodega, lote o ubicacion.")
    claves = [Existencia.producto_id]
    if agrupar in ("bodega", "lote", "ubicacion"):
        claves.append(Existencia.bodega_id)
    if agrupar in ("lote", "ubicacion"):
        claves.append(Existencia.lote_id)
    if agrupar == "ubicacion":
        claves.append(Existencia.ubicacion_id)
    c = _alcance_existencias(select(*claves, func.sum(Existencia.cantidad_fisica),
                                    func.sum(Existencia.cantidad_fisica * Existencia.costo_unitario),
                                    func.min(Existencia.fecha_ingreso), func.count(Existencia.id))
                             .join(Producto, Existencia.producto_id == Producto.id)
                             .join(Subfamilia, Producto.subfamilia_id == Subfamilia.id), ctx)
    c = c.where(Existencia.cantidad_fisica > 0, Existencia.estado != "ANULADA")
    for col, val in ((Existencia.producto_id, producto_id), (Existencia.bodega_id, bodega_id),
                     (Subfamilia.familia_id, familia_id), (Producto.subfamilia_id, subfamilia_id)):
        if val:
            c = c.where(col == val)
    if q:
        p = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Producto.nombre).like(p), func.lower(Producto.codigo).like(p)))
    filas = db.execute(c.group_by(*claves)).all()

    # Reservas activas pendientes, sumadas al nivel de cada fila.
    reservas = db.scalars(select(ReservaStock).where(ReservaStock.empresa_id == ctx.empresa_id, ReservaStock.estado == "ACTIVA")).unique().all()
    borradores = db.execute(
        select(Existencia.producto_id, Existencia.bodega_id, Existencia.lote_id, Existencia.ubicacion_id,
               func.sum(DetalleDocumentoInventario.cantidad))
        .join(DetalleDocumentoInventario, DetalleDocumentoInventario.existencia_id == Existencia.id)
        .join(DocumentoInventario, DetalleDocumentoInventario.documento_id == DocumentoInventario.id)
        .where(DocumentoInventario.estado == "BORRADOR", DocumentoInventario.clase.in_(("SALIDA", "TRASLADO")),
               DocumentoInventario.empresa_id == ctx.empresa_id)
        .group_by(Existencia.producto_id, Existencia.bodega_id, Existencia.lote_id, Existencia.ubicacion_id)).all()

    def reservado_en(pid, bid=None, lid=None):
        total = Decimal(0)
        for r in reservas:
            if r.producto_id != pid:
                continue
            if agrupar == "producto" or (agrupar == "bodega" and r.bodega_id == bid) or \
                    (agrupar in ("lote", "ubicacion") and r.lote_id is not None and r.lote_id == lid and r.bodega_id in (None, bid)):
                total += r.cantidad - r.cantidad_consumida
        return total

    def borrador_en(pid, bid=None, lid=None, uid=None):
        return sum((dec(b[4]) for b in borradores if b[0] == pid and (agrupar == "producto" or b[1] == bid)
                    and (agrupar in ("producto", "bodega") or b[2] == lid) and (agrupar != "ubicacion" or b[3] == uid)), Decimal(0))

    productos = {p.id: p for p in db.scalars(select(Producto).where(Producto.id.in_({f[0] for f in filas}))).unique()} if filas else {}
    bodegas = dict(db.execute(select(Bodega.id, Bodega.nombre)).all())
    lotes = {x.id: x for x in db.scalars(select(Lote).where(Lote.id.in_({f[2] for f in filas if len(claves) > 2 and f[2]}))).unique()} \
        if agrupar in ("lote", "ubicacion") and filas else {}
    ubic = dict(db.execute(select(Ubicacion.id, Ubicacion.codigo_completo)).all()) if agrupar == "ubicacion" else {}
    salida = []
    for f in filas:
        pid = f[0]
        bid = f[1] if len(claves) > 1 else None
        lid = f[2] if len(claves) > 2 else None
        uid = f[3] if len(claves) > 3 else None
        fisico_, valor, antiguo, n = f[len(claves):]
        p = productos[pid]
        res = reservado_en(pid, bid, lid)
        fila = {
            "producto_id": pid, "producto_codigo": p.codigo, "producto": p.nombre, "familia": p.subfamilia.familia.nombre,
            "subfamilia": p.subfamilia.nombre, "unidad": p.unidad_base.codigo, "stock_fisico": float(fisico_),
            "stock_reservado": float(res), "stock_disponible": float(max(Decimal(0), dec(fisico_) - res)),
            "stock_comprometido": float(res + borrador_en(pid, bid, lid, uid)), "valor_inventario": float(dec(valor)),
            "existencias": n, "ingreso_mas_antiguo": json_valor(antiguo),
            "stock_minimo": json_valor(p.stock_minimo), "stock_critico": json_valor(p.stock_critico),
            "bajo_minimo": agrupar == "producto" and p.stock_minimo is not None and dec(fisico_) <= p.stock_minimo,
        }
        if bid:
            fila.update(bodega_id=bid, bodega=bodegas.get(bid))
        if agrupar in ("lote", "ubicacion"):
            lote = lotes.get(lid)
            fila.update(lote_id=lid, lote=lote.codigo if lote else None, lote_estado=lote.estado if lote else None,
                        fecha_vencimiento=json_valor(lote.fecha_vencimiento) if lote else None)
        if agrupar == "ubicacion":
            fila.update(ubicacion_id=uid, ubicacion=ubic.get(uid))
        salida.append(fila)
    if agrupar == "producto" and not (producto_id or bodega_id or q):
        # Productos con minimo definido y sin existencias tambien se informan (stock agotado).
        con = {f["producto_id"] for f in salida}
        cp = select(Producto).where(Producto.empresa_id == ctx.empresa_id, Producto.activo.is_(True),
                                    Producto.stock_minimo.is_not(None))
        if familia_id:
            cp = cp.join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).where(Subfamilia.familia_id == familia_id)
        if subfamilia_id:
            cp = cp.where(Producto.subfamilia_id == subfamilia_id)
        for p in db.scalars(cp).unique():
            if p.id in con or (ctx.familias is not None and p.subfamilia.familia_id not in ctx.familias):
                continue
            salida.append({"producto_id": p.id, "producto_codigo": p.codigo, "producto": p.nombre,
                           "familia": p.subfamilia.familia.nombre, "subfamilia": p.subfamilia.nombre,
                           "unidad": p.unidad_base.codigo, "stock_fisico": 0.0, "stock_reservado": 0.0,
                           "stock_disponible": 0.0, "stock_comprometido": 0.0, "valor_inventario": 0.0, "existencias": 0,
                           "ingreso_mas_antiguo": None, "stock_minimo": json_valor(p.stock_minimo),
                           "stock_critico": json_valor(p.stock_critico), "bajo_minimo": True})
    if solo_bajo_minimo:
        salida = [f for f in salida if f["bajo_minimo"]]
    salida.sort(key=lambda f: (f["producto"], f.get("bodega") or "", f.get("lote") or ""))
    return ocultar_costos(salida, ctx.ver_costos)


# ---------------------------------------------------------------- movimientos

def movimiento_dict(db: Session, m: MovimientoInventario, extendido: bool = False) -> dict:
    e = m.existencia
    d = {
        "id": m.id, "fecha": json_valor(m.fecha), "tipo": m.tipo.codigo, "tipo_nombre": m.tipo.nombre,
        "existencia_id": m.existencia_id, "codigo_publico": e.codigo_publico, "producto_id": m.producto_id,
        "producto": e.producto.nombre, "producto_codigo": e.producto.codigo, "lote_id": m.lote_id,
        "lote": e.lote.codigo if e.lote else None, "cantidad": float(m.cantidad), "unidad": e.unidad.codigo,
        "costo_unitario": float(m.costo_unitario), "costo_total": float(m.costo_total), "proceso_id": m.proceso_id,
        "documento_id": m.documento_id, "usuario_id": m.usuario_id, "motivo_texto": m.motivo_texto,
        "observacion": m.observacion, "movimiento_anulado_id": m.movimiento_anulado_id,
        "bodega_origen_id": m.bodega_origen_id, "bodega_destino_id": m.bodega_destino_id,
        "ubicacion_origen_id": m.ubicacion_origen_id, "ubicacion_destino_id": m.ubicacion_destino_id,
        "anulado": svc.esta_anulado(db, m.id),
    }
    if extendido:
        d["usuario"] = db.get(Usuario, m.usuario_id).nombre if m.usuario_id else None
        d["proceso"] = db.get(Proceso, m.proceso_id).codigo if m.proceso_id else None
        d["documento"] = db.get(DocumentoInventario, m.documento_id).numero if m.documento_id else None
        d["bodega"] = e.bodega.nombre
    return d


@router.get("/movimientos")
def listar_movimientos(tipo: str | None = None, producto_id: int | None = None, lote_id: int | None = None,
                       existencia_id: int | None = None, proceso_id: int | None = None, bodega_id: int | None = None,
                       usuario_id: int | None = None, temporada_id: int | None = None, desde: datetime | None = None,
                       hasta: datetime | None = None, q: str | None = None, pagina: int = Query(1, ge=1),
                       tam: int = Query(50, le=1000), db: Session = Depends(get_db),
                       ctx: Contexto = Depends(requiere("movimientos:ver"))):
    c = select(MovimientoInventario).join(Existencia, MovimientoInventario.existencia_id == Existencia.id) \
        .join(Producto, MovimientoInventario.producto_id == Producto.id)
    c = _alcance_existencias(c, ctx)
    if tipo:
        c = c.join(TipoMovimiento, MovimientoInventario.tipo_movimiento_id == TipoMovimiento.id).where(TipoMovimiento.codigo == tipo)
    for col, val in ((MovimientoInventario.producto_id, producto_id), (MovimientoInventario.lote_id, lote_id),
                     (MovimientoInventario.existencia_id, existencia_id), (MovimientoInventario.proceso_id, proceso_id),
                     (MovimientoInventario.usuario_id, usuario_id), (MovimientoInventario.temporada_id, temporada_id)):
        if val:
            c = c.where(col == val)
    if bodega_id:
        c = c.where(or_(MovimientoInventario.bodega_origen_id == bodega_id, MovimientoInventario.bodega_destino_id == bodega_id))
    if desde:
        c = c.where(MovimientoInventario.fecha >= desde)
    if hasta:
        c = c.where(MovimientoInventario.fecha <= hasta)
    if q:
        p = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Producto.nombre).like(p), func.lower(Existencia.codigo_publico).like(p)))
    r = paginar(db, c.order_by(MovimientoInventario.id.desc()), pagina, tam, lambda m: movimiento_dict(db, m, True))
    return ocultar_costos(r, ctx.ver_costos)


class Anulacion(BaseModel):
    motivo: str


@router.post("/movimientos/{id_}/anular")
def anular_movimiento(id_: int, d: Anulacion, db: Session = Depends(get_db),
                      ctx: Contexto = Depends(requiere("movimientos:anular"))):
    """No elimina el movimiento: genera su inverso y deja ambos en el libro."""
    m = db.get(MovimientoInventario, id_)
    if not m or m.empresa_id != ctx.empresa_id:
        raise no_encontrado("Movimiento")
    obtener_existencia(db, ctx, m.existencia_id)
    if m.tipo.codigo == "INGRESO":
        raise ErrorNegocio("NO_ANULABLE", "Un ingreso se anula desde su documento de origen.")
    inverso = svc.anular_movimiento(db, ctx, m, d.motivo)
    return ocultar_costos(movimiento_dict(db, inverso, True), ctx.ver_costos)


# ---------------------------------------------------------------- documentos

class DetalleEntrada(BaseModel):
    producto_id: int | None = None
    existencia_id: int | None = None
    cantidad: Decimal
    unidad_id: int | None = None
    precio_unitario: Decimal | None = None
    lote_id: int | None = None
    lote_manual: str | None = None
    campos_lote: dict | None = None
    referencia_externa: str | None = None
    fecha_fabricacion: date | None = None
    fecha_vencimiento: date | None = None
    ubicacion_id: int | None = None
    ubicacion_destino_id: int | None = None
    bultos: int | None = Field(default=None, ge=1, le=500)
    observaciones: str | None = None


class DocumentoEntrada(BaseModel):
    clase: str | None = None
    motivo_id: int | None = None
    tipo_documento: str | None = None
    numero_documento: str | None = None
    fecha_documento: date | None = None
    fecha: datetime | None = None
    proveedor_id: int | None = None
    bodega_id: int | None = None
    bodega_destino_id: int | None = None
    proceso_id: int | None = None
    temporada_id: int | None = None
    moneda: str | None = None
    observaciones: str | None = None
    detalles: list[DetalleEntrada] | None = None
    confirmar: bool = False


def documento_dict(db: Session, doc: DocumentoInventario, detalle: bool = False) -> dict:
    d = a_dict(doc, bodega=db.get(Bodega, doc.bodega_id).nombre,
               bodega_destino=db.get(Bodega, doc.bodega_destino_id).nombre if doc.bodega_destino_id else None,
               proveedor=db.get(Proveedor, doc.proveedor_id).nombre if doc.proveedor_id else None,
               motivo=db.get(MotivoMovimiento, doc.motivo_id).nombre if doc.motivo_id else None,
               proceso=db.get(Proceso, doc.proceso_id).codigo if doc.proceso_id else None,
               usuario=db.get(Usuario, doc.usuario_id).nombre if doc.usuario_id else None,
               lineas=len(doc.detalles), costo_total=float(sum((dec(x.costo_total) for x in doc.detalles), Decimal(0))))
    if detalle:
        unidades = dict(db.execute(select(UnidadMedida.id, UnidadMedida.codigo)).all())
        ubic = dict(db.execute(select(Ubicacion.id, Ubicacion.codigo_completo).where(
            Ubicacion.bodega_id.in_([doc.bodega_id, doc.bodega_destino_id or doc.bodega_id]))).all())
        lineas = []
        for x in doc.detalles:
            e = db.get(Existencia, x.existencia_id) if x.existencia_id else None
            p = db.get(Producto, x.producto_id)
            lote = db.get(Lote, x.lote_id) if x.lote_id else None
            lineas.append(a_dict(x, producto=p.nombre, producto_codigo=p.codigo, unidad=unidades.get(x.unidad_id),
                                 unidad_base=p.unidad_base.codigo, lote=lote.codigo if lote else None,
                                 ubicacion=ubic.get(x.ubicacion_id), ubicacion_destino=ubic.get(x.ubicacion_destino_id),
                                 existencia=e.codigo_publico if e else None,
                                 campos_lote=json.loads(x.campos_lote) if x.campos_lote else None))
        d["detalles"] = lineas
        d["existencias"] = [existencia_dict(db, e) for e in db.scalars(
            select(Existencia).where(Existencia.detalle_origen_id.in_([x.id for x in doc.detalles])).order_by(Existencia.id)).unique()] \
            if doc.detalles and doc.clase == "INGRESO" else []
    return d


def obtener_documento(db: Session, ctx: Contexto, id_: int) -> DocumentoInventario:
    doc = db.get(DocumentoInventario, id_)
    if not doc or doc.empresa_id != ctx.empresa_id:
        raise no_encontrado("Documento")
    ctx.exigir_bodega(doc.bodega_id)
    return doc


def _aplicar_documento(db: Session, ctx: Contexto, doc: DocumentoInventario, d: DocumentoEntrada) -> None:
    for campo in ("motivo_id", "tipo_documento", "numero_documento", "fecha_documento", "fecha", "proveedor_id",
                  "bodega_destino_id", "proceso_id", "temporada_id", "moneda", "observaciones"):
        if campo in d.model_fields_set:
            setattr(doc, campo, getattr(d, campo))
    if doc.fecha is None:
        doc.fecha = ahora()
    if doc.fecha.tzinfo is not None:
        from datetime import UTC
        doc.fecha = doc.fecha.astimezone(UTC).replace(tzinfo=None)
    if (doc.fecha - ahora()).total_seconds() > 300:
        raise ErrorNegocio("FECHA", "La fecha del documento no puede ser futura.")
    if doc.motivo_id:
        motivo = db.get(MotivoMovimiento, doc.motivo_id)
        esperado = "INGRESO" if doc.clase == "INGRESO" else "SALIDA"
        if not motivo or (doc.clase in ("INGRESO", "SALIDA") and motivo.clase != esperado):
            raise ErrorNegocio("MOTIVO", "El motivo no corresponde a la clase del documento.")
    if doc.bodega_destino_id:
        ctx.exigir_bodega(doc.bodega_destino_id)
    if doc.temporada_id is None:
        t = db.scalar(select(Temporada).where(Temporada.empresa_id == ctx.empresa_id, Temporada.actual.is_(True)))
        doc.temporada_id = t.id if t else None
    if d.detalles is not None:
        nuevas = []
        for n, x in enumerate(d.detalles, 1):
            existencia = obtener_existencia(db, ctx, x.existencia_id) if x.existencia_id else None
            producto_id = x.producto_id or (existencia.producto_id if existencia else None)
            producto = db.get(Producto, producto_id) if producto_id else None
            if not producto or producto.empresa_id != ctx.empresa_id:
                raise ErrorNegocio("PRODUCTO", f"Linea {n}: debe indicar un producto valido.")
            if doc.clase != "INGRESO" and not existencia:
                raise ErrorNegocio("EXISTENCIA", f"Linea {n}: debe indicar la existencia.")
            nuevas.append(DetalleDocumentoInventario(
                producto_id=producto.id, existencia_id=x.existencia_id, cantidad=x.cantidad,
                unidad_id=x.unidad_id or (producto.unidad_base_id if doc.clase != "INGRESO"
                                          else producto.unidad_compra_id or producto.unidad_base_id),
                precio_unitario=x.precio_unitario, lote_id=x.lote_id, lote_manual=x.lote_manual,
                campos_lote=json.dumps(x.campos_lote) if x.campos_lote else None, referencia_externa=x.referencia_externa,
                fecha_fabricacion=x.fecha_fabricacion, fecha_vencimiento=x.fecha_vencimiento, ubicacion_id=x.ubicacion_id,
                ubicacion_destino_id=x.ubicacion_destino_id, bultos=x.bultos, observaciones=x.observaciones))
        doc.detalles = nuevas
    db.flush()


PERMISO_CLASE = {"INGRESO": "inventario:crear", "SALIDA": "movimientos:crear", "TRASLADO": "traslados:crear",
                 "AJUSTE": "inventario:ajustar"}


@router.get("/documentos")
def listar_documentos(clase: str | None = None, estado: str | None = None, bodega_id: int | None = None,
                      proveedor_id: int | None = None, q: str | None = None, desde: date | None = None,
                      hasta: date | None = None, pagina: int = Query(1, ge=1), tam: int = Query(50, le=500),
                      db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    c = select(DocumentoInventario).where(DocumentoInventario.empresa_id == ctx.empresa_id)
    if ctx.bodegas is not None:
        c = c.where(DocumentoInventario.bodega_id.in_(ctx.bodegas))
    for col, val in ((DocumentoInventario.clase, clase), (DocumentoInventario.estado, estado),
                     (DocumentoInventario.bodega_id, bodega_id), (DocumentoInventario.proveedor_id, proveedor_id)):
        if val:
            c = c.where(col == val)
    if q:
        p = f"%{q.lower()}%"
        c = c.where(or_(func.lower(DocumentoInventario.numero).like(p), func.lower(DocumentoInventario.numero_documento).like(p)))
    if desde:
        c = c.where(DocumentoInventario.fecha >= inicio_dia_utc(desde))
    if hasta:
        c = c.where(DocumentoInventario.fecha < inicio_dia_utc(hasta + timedelta(days=1)))
    r = paginar(db, c.order_by(DocumentoInventario.id.desc()), pagina, tam, lambda x: documento_dict(db, x))
    return ocultar_costos(r, ctx.ver_costos)


@router.get("/documentos/{id_}")
def ver_documento(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    return ocultar_costos(documento_dict(db, obtener_documento(db, ctx, id_), True), ctx.ver_costos)


@router.post("/documentos", status_code=201)
def crear_documento(d: DocumentoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    if d.clase not in PERMISO_CLASE:
        raise ErrorNegocio("CLASE", "clase debe ser INGRESO, SALIDA, TRASLADO o AJUSTE.")
    ctx.exigir(PERMISO_CLASE[d.clase])
    if not d.bodega_id:
        raise ErrorNegocio("BODEGA", "Debe indicar la bodega.")
    bodega = db.get(Bodega, d.bodega_id)
    if not bodega or bodega.empresa_id != ctx.empresa_id:
        raise no_encontrado("Bodega")
    ctx.exigir_bodega(bodega.id)
    prefijo = {"INGRESO": "ING", "SALIDA": "SAL", "TRASLADO": "TRA", "AJUSTE": "AJU"}[d.clase]
    doc = DocumentoInventario(empresa_id=ctx.empresa_id, numero=siguiente_numero(db, ctx.empresa_id, f"doc_{d.clase}", prefijo, 7),
                              clase=d.clase, bodega_id=bodega.id, usuario_id=ctx.usuario.id, moneda=d.moneda or "CLP",
                              fecha=d.fecha or ahora())
    db.add(doc)
    db.flush()
    _aplicar_documento(db, ctx, doc, d)
    auditar(db, ctx, "documento_inventario", doc.id, "CREAR", nuevo={"numero": doc.numero, "clase": doc.clase})
    if d.confirmar:
        svc.confirmar_documento(db, ctx, doc)
    return ocultar_costos(documento_dict(db, doc, True), ctx.ver_costos)


@router.put("/documentos/{id_}")
def editar_documento(id_: int, d: DocumentoEntrada, db: Session = Depends(get_db),
                     ctx: Contexto = Depends(requiere("inventario:editar"))):
    doc = obtener_documento(db, ctx, id_)
    if doc.estado != "BORRADOR":
        raise ErrorNegocio("ESTADO", f"El documento esta {doc.estado}: solo un borrador puede editarse.", 409)
    ctx.exigir(PERMISO_CLASE[doc.clase])
    _aplicar_documento(db, ctx, doc, d)
    auditar(db, ctx, "documento_inventario", doc.id, "EDITAR")
    if d.confirmar:
        svc.confirmar_documento(db, ctx, doc)
    return ocultar_costos(documento_dict(db, doc, True), ctx.ver_costos)


@router.post("/documentos/{id_}/confirmar")
def confirmar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    doc = obtener_documento(db, ctx, id_)
    ctx.exigir(PERMISO_CLASE[doc.clase])
    svc.confirmar_documento(db, ctx, doc)
    return ocultar_costos(documento_dict(db, doc, True), ctx.ver_costos)


@router.post("/documentos/{id_}/anular")
def anular(id_: int, d: Anulacion, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    doc = obtener_documento(db, ctx, id_)
    ctx.exigir("movimientos:anular" if doc.estado == "CONFIRMADO" else PERMISO_CLASE[doc.clase])
    svc.anular_documento(db, ctx, doc, d.motivo)
    return ocultar_costos(documento_dict(db, doc, True), ctx.ver_costos)


@router.get("/productos/{id_}/politica-ingreso")
def politica_ingreso(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    """Lo que el formulario de ingreso necesita saber del producto: lote, vencimiento, ubicacion, granularidad."""
    from app.modelos import PlantillaLote
    from app.servicios.lotes import version_vigente
    p = db.get(Producto, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Producto")
    pol = politica_efectiva(p)
    plantilla = db.get(PlantillaLote, pol["plantilla_lote_id"]) if pol["plantilla_lote_id"] else None
    version = version_vigente(plantilla) if plantilla and plantilla.activa else None
    manuales = [s.configuracion for s in version.segmentos if s.tipo == "MANUAL"] if version else []
    return {"producto_id": p.id, "unidad_base_id": p.unidad_base_id, "unidad_base": p.unidad_base.codigo,
            "unidad_compra_id": p.unidad_compra_id or p.unidad_base_id, "costo_referencial": json_valor(p.costo_referencial)
            if ctx.ver_costos else None, "politica": pol,
            "lote": {"modo": plantilla.modo if version else "MANUAL" if pol["usa_lote"] else None,
                     "plantilla": plantilla.nombre if version else None, "campos_manuales": manuales,
                     "requiere_codigo": bool(pol["usa_lote"]) and (version is None or plantilla.modo == "MANUAL")}}
