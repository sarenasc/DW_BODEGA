"""Reservas de stock: compromiso previo al consumo. Reservar no genera movimiento ni descuenta stock fisico."""
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar, siguiente_numero
from app.core.crud import paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.parametros import parametro
from app.core.util import a_dict, ahora, q6
from app.modelos import Bodega, Existencia, Lote, Proceso, Producto, ReservaStock, Usuario
from app.servicios import inventario as svc
from app.servicios.catalogo import a_unidad_base

router = APIRouter(prefix="/api", tags=["Reservas de stock"])


def reserva_dict(db: Session, r: ReservaStock) -> dict:
    return a_dict(
        r, producto=r.producto.nombre, producto_codigo=r.producto.codigo, unidad=r.producto.unidad_base.codigo,
        pendiente=r.cantidad - r.cantidad_consumida if r.estado == "ACTIVA" else Decimal(0),
        bodega=db.get(Bodega, r.bodega_id).nombre if r.bodega_id else None,
        lote=db.get(Lote, r.lote_id).codigo if r.lote_id else None,
        existencia=db.get(Existencia, r.existencia_id).codigo_publico if r.existencia_id else None,
        proceso=db.get(Proceso, r.proceso_id).codigo if r.proceso_id else None,
        usuario=db.get(Usuario, r.usuario_id).nombre if r.usuario_id else None)


class ReservaEntrada(BaseModel):
    producto_id: int
    cantidad: Decimal
    unidad_id: int | None = None
    bodega_id: int | None = None
    lote_id: int | None = None
    existencia_id: int | None = None
    proceso_id: int | None = None
    area: str | None = None
    documento_referencia: str | None = None
    motivo: str | None = None
    fecha_vencimiento: datetime | None = None
    observacion: str | None = None


def disponibilidad(db: Session, producto_id: int, bodega_id=None, lote_id=None, existencia_id=None,
                   excluir_reserva_id: int | None = None) -> dict:
    """Stock fisico, reservado y disponible en el nivel solicitado y en los niveles que lo contienen."""
    niveles = [("producto", svc.fisico(db, producto_id), svc.reservado(db, producto_id, excluir_reserva_id=excluir_reserva_id))]
    if bodega_id:
        niveles.append(("bodega", svc.fisico(db, producto_id, bodega_id=bodega_id),
                        svc.reservado(db, producto_id, bodega_id=bodega_id, excluir_reserva_id=excluir_reserva_id)))
    if lote_id:
        niveles.append(("lote", svc.fisico(db, producto_id, bodega_id=bodega_id, lote_id=lote_id),
                        svc.reservado(db, producto_id, lote_id=lote_id, excluir_reserva_id=excluir_reserva_id)))
    if existencia_id:
        e = db.get(Existencia, existencia_id)
        utilizable = e.cantidad_fisica if e and e.estado == "DISPONIBLE" else Decimal(0)
        niveles.append(("existencia", utilizable,
                        svc.reservado(db, producto_id, existencia_id=existencia_id, excluir_reserva_id=excluir_reserva_id)))
    detalle = [{"nivel": n, "stock_fisico": float(f), "stock_reservado": float(r), "stock_disponible": float(max(Decimal(0), f - r))}
               for n, f, r in niveles]
    return {"stock_disponible": min(d["stock_disponible"] for d in detalle), "stock_fisico": detalle[-1]["stock_fisico"],
            "stock_reservado": detalle[-1]["stock_reservado"], "niveles": detalle}


def crear_reserva(db: Session, ctx: Contexto, d: ReservaEntrada) -> ReservaStock:
    producto = db.get(Producto, d.producto_id)
    if not producto or producto.empresa_id != ctx.empresa_id:
        raise no_encontrado("Producto")
    ctx.exigir_familia(producto.subfamilia.familia_id)
    existencia = db.get(Existencia, d.existencia_id) if d.existencia_id else None
    lote = db.get(Lote, d.lote_id) if d.lote_id else None
    if existencia:
        if existencia.producto_id != producto.id:
            raise ErrorNegocio("EXISTENCIA", "La existencia no corresponde al producto.")
        d.bodega_id, d.lote_id = existencia.bodega_id, existencia.lote_id
    if lote and lote.producto_id != producto.id:
        raise ErrorNegocio("LOTE", "El lote no corresponde al producto.")
    if d.bodega_id:
        ctx.exigir_bodega(d.bodega_id)
    if d.proceso_id:
        proceso = db.get(Proceso, d.proceso_id)
        if not proceso or proceso.empresa_id != ctx.empresa_id:
            raise no_encontrado("Proceso")
        if proceso.estado in ("CERRADO", "ANULADO"):
            raise ErrorNegocio("PROCESO", f"El proceso esta {proceso.estado}: no admite reservas.", 409)
    base, _ = a_unidad_base(db, producto, d.cantidad, d.unidad_id)
    base = q6(base)
    if base <= 0:
        raise ErrorNegocio("CANTIDAD", "La cantidad a reservar debe ser mayor que cero.")
    if d.fecha_vencimiento and d.fecha_vencimiento.tzinfo is not None:
        from datetime import UTC
        d.fecha_vencimiento = d.fecha_vencimiento.astimezone(UTC).replace(tzinfo=None)
    if d.fecha_vencimiento and d.fecha_vencimiento <= ahora():
        raise ErrorNegocio("FECHA", "La fecha limite de la reserva debe ser futura.")

    # Serializa con otras reservas y consumos del mismo producto antes de medir el disponible.
    svc.bloquear_producto(db, producto.id)
    disp = disponibilidad(db, producto.id, d.bodega_id, d.lote_id, d.existencia_id)
    if base > Decimal(str(disp["stock_disponible"])):
        permitido = parametro(db, "reservas.permitir_exceder", ctx.empresa_id, False) and ctx.puede("reservas:exceder")
        if not permitido:
            raise ErrorNegocio("SIN_DISPONIBLE", f"No se puede reservar {base.normalize():f} {producto.unidad_base.codigo}: "
                               f"el stock disponible es {disp['stock_disponible']:g}.", 409, disp)
    r = ReservaStock(empresa_id=ctx.empresa_id, numero=siguiente_numero(db, ctx.empresa_id, "reserva", "RES", 7),
                     producto_id=producto.id, bodega_id=d.bodega_id, lote_id=d.lote_id, existencia_id=d.existencia_id,
                     proceso_id=d.proceso_id, area=d.area, documento_referencia=d.documento_referencia, motivo=d.motivo,
                     cantidad=base, unidad_id=producto.unidad_base_id, fecha_vencimiento=d.fecha_vencimiento,
                     usuario_id=ctx.usuario.id, observacion=d.observacion)
    r.producto = producto
    db.add(r)
    db.flush()
    auditar(db, ctx, "reserva", r.id, "CREAR", nuevo={"numero": r.numero, "producto": producto.codigo, "cantidad": float(base)})
    return r


@router.get("/reservas")
def listar(estado: str | None = None, producto_id: int | None = None, proceso_id: int | None = None,
           bodega_id: int | None = None, pagina: int = Query(1, ge=1), tam: int = Query(50, le=500),
           db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("reservas:ver"))):
    c = select(ReservaStock).where(ReservaStock.empresa_id == ctx.empresa_id)
    for col, val in ((ReservaStock.estado, estado), (ReservaStock.producto_id, producto_id),
                     (ReservaStock.proceso_id, proceso_id), (ReservaStock.bodega_id, bodega_id)):
        if val:
            c = c.where(col == val)
    if ctx.bodegas is not None:
        c = c.where((ReservaStock.bodega_id.is_(None)) | (ReservaStock.bodega_id.in_(ctx.bodegas)))
    return paginar(db, c.order_by(ReservaStock.id.desc()), pagina, tam, lambda r: reserva_dict(db, r))


@router.get("/reservas/disponibilidad")
def ver_disponibilidad(producto_id: int, bodega_id: int | None = None, lote_id: int | None = None,
                       existencia_id: int | None = None, db: Session = Depends(get_db),
                       ctx: Contexto = Depends(requiere("reservas:ver"))):
    p = db.get(Producto, producto_id)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Producto")
    d = disponibilidad(db, producto_id, bodega_id, lote_id, existencia_id)
    d["unidad"] = p.unidad_base.codigo
    return d


@router.post("/reservas", status_code=201)
def crear(d: ReservaEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("reservas:crear"))):
    return reserva_dict(db, crear_reserva(db, ctx, d))


class Cierre(BaseModel):
    motivo: str | None = None


def _cerrar(db: Session, ctx: Contexto, id_: int, estado: str, motivo: str | None) -> dict:
    r = db.get(ReservaStock, id_)
    if not r or r.empresa_id != ctx.empresa_id:
        raise no_encontrado("Reserva")
    if r.estado != "ACTIVA":
        raise ErrorNegocio("ESTADO", f"La reserva esta {r.estado}.", 409)
    if estado == "ANULADA" and r.cantidad_consumida > 0:
        raise ErrorNegocio("CON_CONSUMO", "La reserva ya tiene consumos: liberela en lugar de anularla.", 409)
    r.estado, r.fecha_cierre, r.cerrada_por = estado, ahora(), ctx.usuario.id
    if motivo:
        r.observacion = ((r.observacion or "") + f" | {estado}: {motivo}").strip(" |")[:300]
    auditar(db, ctx, "reserva", r.id, estado, motivo=motivo)
    return reserva_dict(db, r)


@router.post("/reservas/{id_}/liberar")
def liberar(id_: int, d: Cierre, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("reservas:crear"))):
    """Devuelve al disponible el saldo no consumido."""
    return _cerrar(db, ctx, id_, "LIBERADA", d.motivo)


@router.post("/reservas/{id_}/anular")
def anular(id_: int, d: Cierre, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("reservas:crear"))):
    return _cerrar(db, ctx, id_, "ANULADA", d.motivo)
