"""Nucleo de inventario: existencias, libro de movimientos, orden FIFO/FEFO, salidas, traslados y anulaciones.

Reglas:
- El stock solo cambia junto con un movimiento, dentro de la misma transaccion.
- El descuento es un UPDATE atomico condicional: dos usuarios no pueden dejar stock negativo.
- Los movimientos no se editan ni se borran; se corrigen con un movimiento inverso (ANULACION).
"""
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.auditoria import auditar, siguiente_numero
from app.core.errores import ErrorNegocio, sin_permiso
from app.core.parametros import parametro
from app.core.seguridad import token_qr
from app.core.util import CERO, ahora, dec, dia_local, hoy, q2, q6
from app.modelos import (Bodega, DetalleDocumentoInventario, DocumentoInventario, ExcepcionFifo, Existencia, Lote,
                         MotivoMovimiento, MovimientoInventario, Producto, Proceso, ReservaStock, TipoMovimiento,
                         Ubicacion)

from .catalogo import a_unidad_base, politica_efectiva
from .lotes import cambiar_estado_lote, crear_lote

FUTURO = date(9999, 12, 31)
_tipos: dict[str, int] = {}


def tipo_id(db: Session, codigo: str) -> int:
    if codigo not in _tipos:
        _tipos.clear()
        _tipos.update(dict(db.execute(select(TipoMovimiento.codigo, TipoMovimiento.id)).all()))
    return _tipos[codigo]


def limpiar_cache() -> None:
    _tipos.clear()


def bloquear_producto(db: Session, producto_id: int) -> None:
    """Serializa reservas y salidas de un producto tomando el bloqueo de su fila (portable entre motores)."""
    db.execute(update(Producto).where(Producto.id == producto_id).values(version_stock=Producto.version_stock + 1))


# ---------------------------------------------------------------- existencias

def nueva_existencia(db: Session, ctx, *, producto: Producto, lote: Lote | None, bodega_id: int, ubicacion_id: int | None,
                     cantidad: Decimal, costo_unitario: Decimal, fecha_ingreso: datetime, granularidad: str,
                     detalle_id: int | None = None, padre: Existencia | None = None, envases: int | None = None,
                     proveedor_id: int | None = None, moneda: str = "CLP", fecha_costo: date | None = None) -> Existencia:
    prefijo = parametro(db, "existencias.prefijo", producto.empresa_id, "INV")
    e = Existencia(
        empresa_id=producto.empresa_id, codigo_publico=siguiente_numero(db, producto.empresa_id, "existencia", prefijo),
        token_qr=token_qr(), producto_id=producto.id, lote_id=lote.id if lote else None, bodega_id=bodega_id,
        ubicacion_id=ubicacion_id, detalle_origen_id=detalle_id, existencia_padre_id=padre.id if padre else None,
        granularidad=granularidad, envases=envases, fecha_ingreso=fecha_ingreso, cantidad_inicial=q6(cantidad),
        cantidad_fisica=CERO, unidad_id=producto.unidad_base_id, costo_unitario=q6(costo_unitario), moneda=moneda,
        fecha_costo=fecha_costo or dia_local(fecha_ingreso), proveedor_id=proveedor_id, estado="DISPONIBLE")
    db.add(e)
    db.flush()
    return e


def movimiento(db: Session, ctx, existencia: Existencia, tipo: str, cantidad: Decimal, *, costo_total: Decimal | None = None,
               fecha: datetime | None = None, bodega_origen_id=None, bodega_destino_id=None, ubicacion_origen_id=None,
               ubicacion_destino_id=None, proceso: Proceso | None = None, documento_id=None, detalle_id=None,
               motivo_id=None, motivo_texto=None, observacion=None, clave_idempotencia=None, cantidad_ingresada=None,
               unidad_ingresada_id=None, anula: MovimientoInventario | None = None, reserva_id=None) -> MovimientoInventario:
    """Inserta una fila en el libro. No modifica el saldo: eso lo hacen aumentar() / descontar()."""
    cantidad = q6(cantidad)
    if costo_total is None:
        costo_total = q2(cantidad * existencia.costo_unitario)
    m = MovimientoInventario(
        empresa_id=existencia.empresa_id, fecha=fecha or ahora(), tipo_movimiento_id=tipo_id(db, tipo), motivo_id=motivo_id,
        existencia_id=existencia.id, producto_id=existencia.producto_id, lote_id=existencia.lote_id, cantidad=cantidad,
        unidad_id=existencia.unidad_id, cantidad_ingresada=cantidad_ingresada, unidad_ingresada_id=unidad_ingresada_id,
        costo_unitario=existencia.costo_unitario, costo_total=costo_total, bodega_origen_id=bodega_origen_id,
        bodega_destino_id=bodega_destino_id, ubicacion_origen_id=ubicacion_origen_id,
        ubicacion_destino_id=ubicacion_destino_id, proceso_id=proceso.id if proceso else None,
        temporada_id=proceso.temporada_id if proceso else None, documento_id=documento_id, detalle_documento_id=detalle_id,
        reserva_id=reserva_id, movimiento_anulado_id=anula.id if anula else None,
        usuario_id=ctx.usuario.id if ctx else None, motivo_texto=motivo_texto, observacion=observacion,
        clave_idempotencia=clave_idempotencia)
    db.add(m)
    db.flush()
    return m


def aumentar(db: Session, existencia: Existencia, cantidad: Decimal) -> None:
    db.execute(update(Existencia).where(Existencia.id == existencia.id).values(
        cantidad_fisica=Existencia.cantidad_fisica + q6(cantidad), version=Existencia.version + 1))
    db.execute(update(Existencia).where(Existencia.id == existencia.id, Existencia.estado == "AGOTADA",
                                        Existencia.cantidad_fisica > 0).values(estado="DISPONIBLE"))
    db.refresh(existencia)
    if existencia.lote and existencia.lote.estado == "AGOTADO":
        cambiar_estado_lote(db, None, existencia.lote, "DISPONIBLE", "Reingreso de stock")


def descontar(db: Session, existencia: Existencia, cantidad: Decimal) -> None:
    """UPDATE atomico condicional. Si otro usuario consumio antes, no afecta filas y se informa el saldo real."""
    cantidad = q6(cantidad)
    r = db.execute(update(Existencia).where(Existencia.id == existencia.id, Existencia.cantidad_fisica >= cantidad)
                   .values(cantidad_fisica=Existencia.cantidad_fisica - cantidad, version=Existencia.version + 1))
    if r.rowcount == 0:
        db.refresh(existencia)
        raise ErrorNegocio("STOCK_INSUFICIENTE", f"Stock insuficiente en {existencia.codigo_publico}: quedan "
                           f"{existencia.cantidad_fisica.normalize():f} {existencia.unidad.codigo}.", 409,
                           {"disponible": float(existencia.cantidad_fisica)})
    db.execute(update(Existencia).where(Existencia.id == existencia.id, Existencia.cantidad_fisica == 0,
                                        Existencia.estado == "DISPONIBLE").values(estado="AGOTADA"))
    db.refresh(existencia)
    if existencia.lote_id and existencia.cantidad_fisica == 0 and existencia.lote.estado == "DISPONIBLE":
        resto = db.scalar(select(func.coalesce(func.sum(Existencia.cantidad_fisica), 0)).where(Existencia.lote_id == existencia.lote_id))
        if dec(resto) == 0:
            cambiar_estado_lote(db, None, existencia.lote, "AGOTADO", "Sin stock")


def valor_libro(db: Session, existencia_id: int) -> Decimal:
    return dec(db.scalar(select(func.coalesce(func.sum(MovimientoInventario.costo_total), 0)).where(
        MovimientoInventario.existencia_id == existencia_id)))


def costo_salida(db: Session, existencia: Existencia, cantidad: Decimal) -> Decimal:
    """Costo exacto de la existencia. La salida que la deja en cero se lleva el remanente (sin residuo de redondeo)."""
    if q6(cantidad) == q6(existencia.cantidad_fisica):
        return valor_libro(db, existencia.id)
    return q2(cantidad * existencia.costo_unitario)


# ---------------------------------------------------------------- FIFO / FEFO

def _vence(e: Existencia) -> date:
    return (e.lote.fecha_vencimiento if e.lote and e.lote.fecha_vencimiento else None) or FUTURO


def evaluar_orden(db: Session, existencia: Existencia, politica: dict) -> dict | None:
    """Devuelve la existencia recomendada si hay otra que debio usarse antes; None si el orden es correcto.

    La antiguedad se mide siempre por fecha_ingreso, nunca por el numero de lote.
    """
    estrategia = politica["estrategia_salida"]
    if estrategia == "SIN_RECOMENDACION":
        return None
    ambito = parametro(db, "fifo.ambito", existencia.empresa_id, "BODEGA")
    tolerancia = timedelta(days=int(parametro(db, "fifo.tolerancia_dias", existencia.empresa_id, 0) or 0))
    c = select(Existencia).outerjoin(Lote, Existencia.lote_id == Lote.id).where(
        Existencia.producto_id == existencia.producto_id, Existencia.id != existencia.id,
        Existencia.cantidad_fisica > 0, Existencia.estado == "DISPONIBLE",
        (Lote.id.is_(None)) | (Lote.estado == "DISPONIBLE"),
        (Lote.fecha_vencimiento.is_(None)) | (Lote.fecha_vencimiento >= hoy()))
    if ambito == "BODEGA":
        c = c.where(Existencia.bodega_id == existencia.bodega_id)
    candidatas = db.scalars(c).unique().all()
    if not candidatas:
        return None
    por_ingreso = lambda e: (e.fecha_ingreso, e.id)  # noqa: E731
    dia = lambda e: dia_local(e.fecha_ingreso)  # noqa: E731
    mejor = None
    if estrategia == "FIFO":
        cand = min(candidatas, key=por_ingreso)
        if dia(cand) + tolerancia < dia(existencia):
            mejor = cand
    else:
        cand = min(candidatas, key=lambda e: (_vence(e),) + por_ingreso(e))
        if _vence(cand) < _vence(existencia):
            mejor = cand
        elif estrategia == "FEFO_FIFO" and _vence(cand) == _vence(existencia) and dia(cand) + tolerancia < dia(existencia):
            mejor = cand
    if mejor is None:
        return None
    return {
        "estrategia": estrategia, "politica": politica["politica_fifo"], "existencia_id": mejor.id,
        "codigo_publico": mejor.codigo_publico, "producto": mejor.producto.nombre,
        "lote": mejor.lote.codigo if mejor.lote else None, "fecha_ingreso": mejor.fecha_ingreso.isoformat() + "Z",
        "fecha_vencimiento": mejor.lote.fecha_vencimiento.isoformat() if mejor.lote and mejor.lote.fecha_vencimiento else None,
        "cantidad_disponible": float(mejor.cantidad_fisica), "unidad": mejor.unidad.codigo,
        "bodega": mejor.bodega.nombre, "ubicacion": mejor.ubicacion.codigo_completo if mejor.ubicacion else None,
        "mensaje": ("Está utilizando una existencia más reciente. Existe stock más antiguo disponible."
                    if estrategia == "FIFO" or _vence(mejor) == _vence(existencia)
                    else "Existe stock con vencimiento más próximo disponible."),
    }


def validar_estado_consumible(ctx, existencia: Existencia) -> list[str]:
    """Reglas no negociables por la politica FIFO: bloqueo, cuarentena y vencimiento."""
    avisos = []
    if existencia.estado == "ANULADA":
        raise ErrorNegocio("EXISTENCIA_ANULADA", "La existencia esta anulada.")
    lote = existencia.lote
    bloqueada = existencia.estado == "BLOQUEADA" or (lote and lote.estado in ("BLOQUEADO", "CUARENTENA"))
    if lote and lote.estado == "ANULADO":
        raise ErrorNegocio("LOTE_ANULADO", f"El lote {lote.codigo} esta anulado.")
    if bloqueada:
        estado = lote.estado if lote and lote.estado != "DISPONIBLE" else "BLOQUEADA"
        if not ctx or not ctx.puede("lotes:consumir_bloqueado"):
            raise ErrorNegocio("LOTE_BLOQUEADO", f"El lote {lote.codigo if lote else ''} esta en estado {estado} "
                                                 "y no puede consumirse.", 403)
        avisos.append(f"Lote en estado {estado}: consumo autorizado por permiso especial.")
    vencido = (lote and (lote.estado == "VENCIDO" or (lote.fecha_vencimiento and lote.fecha_vencimiento < hoy()))) or \
              (existencia.vence_abierta and existencia.vence_abierta < hoy())
    if vencido:
        if not ctx or not ctx.puede("lotes:consumir_vencido"):
            raise ErrorNegocio("LOTE_VENCIDO", f"El lote {lote.codigo if lote else ''} esta vencido.", 403)
        avisos.append("Lote vencido: consumo autorizado por permiso especial.")
    return avisos


# ---------------------------------------------------------------- reservas (lectura)

def _pendiente():
    return ReservaStock.cantidad - ReservaStock.cantidad_consumida


def reservado(db: Session, producto_id: int, *, bodega_id=None, lote_id=None, existencia_id=None,
              excluir_proceso_id: int | None = None, excluir_reserva_id: int | None = None) -> Decimal:
    """Suma pendiente de reservas ACTIVAS en el nivel indicado (producto, bodega, lote o existencia)."""
    c = select(func.coalesce(func.sum(_pendiente()), 0)).where(
        ReservaStock.producto_id == producto_id, ReservaStock.estado == "ACTIVA")
    if existencia_id is not None:
        c = c.where(ReservaStock.existencia_id == existencia_id)
    elif lote_id is not None:
        c = c.where(ReservaStock.lote_id == lote_id)
    elif bodega_id is not None:
        c = c.where(ReservaStock.bodega_id == bodega_id)
    if excluir_proceso_id is not None:
        c = c.where((ReservaStock.proceso_id.is_(None)) | (ReservaStock.proceso_id != excluir_proceso_id))
    if excluir_reserva_id is not None:
        c = c.where(ReservaStock.id != excluir_reserva_id)
    return dec(db.scalar(c))


def fisico(db: Session, producto_id: int, *, bodega_id=None, lote_id=None) -> Decimal:
    """Stock fisico utilizable: existencias disponibles de lotes disponibles."""
    c = select(func.coalesce(func.sum(Existencia.cantidad_fisica), 0)).outerjoin(Lote, Existencia.lote_id == Lote.id).where(
        Existencia.producto_id == producto_id, Existencia.estado == "DISPONIBLE",
        (Lote.id.is_(None)) | (Lote.estado == "DISPONIBLE"))
    if bodega_id is not None:
        c = c.where(Existencia.bodega_id == bodega_id)
    if lote_id is not None:
        c = c.where(Existencia.lote_id == lote_id)
    return dec(db.scalar(c))


def disponible_para(db: Session, existencia: Existencia, proceso_id: int | None) -> Decimal:
    """Cuanto puede retirarse de la existencia sin tocar stock reservado por otros."""
    p = existencia.producto_id
    limites = [existencia.cantidad_fisica - reservado(db, p, existencia_id=existencia.id, excluir_proceso_id=proceso_id)]
    lote = existencia.lote
    if existencia.estado != "DISPONIBLE" or (lote and lote.estado != "DISPONIBLE"):
        # Una existencia bloqueada no forma parte del stock utilizable que respalda las reservas generales:
        # consumirla (con permiso especial) no le quita respaldo a nadie.
        return max(CERO, limites[0])
    limites += [
        fisico(db, p, bodega_id=existencia.bodega_id) - reservado(db, p, bodega_id=existencia.bodega_id, excluir_proceso_id=proceso_id),
        fisico(db, p) - reservado(db, p, excluir_proceso_id=proceso_id),
    ]
    if existencia.lote_id:
        limites.append(fisico(db, p, lote_id=existencia.lote_id) - reservado(db, p, lote_id=existencia.lote_id, excluir_proceso_id=proceso_id))
    return max(CERO, min(min(limites), existencia.cantidad_fisica))


def aplicar_a_reservas(db: Session, existencia: Existencia, proceso_id: int | None, cantidad: Decimal) -> int | None:
    """El consumo reduce o cierra las reservas del mismo proceso. Reservar no descuenta: aqui no hay doble rebaja."""
    if proceso_id is None:
        return None
    reservas = db.scalars(select(ReservaStock).where(
        ReservaStock.producto_id == existencia.producto_id, ReservaStock.proceso_id == proceso_id,
        ReservaStock.estado == "ACTIVA").order_by(ReservaStock.existencia_id.is_(None), ReservaStock.lote_id.is_(None),
                                                  ReservaStock.bodega_id.is_(None), ReservaStock.id)).all()
    restante, primera = q6(cantidad), None
    for r in reservas:
        if restante <= 0:
            break
        if (r.existencia_id and r.existencia_id != existencia.id) or (r.lote_id and r.lote_id != existencia.lote_id) or \
                (r.bodega_id and r.bodega_id != existencia.bodega_id):
            continue
        usar = min(restante, r.cantidad - r.cantidad_consumida)
        r.cantidad_consumida += usar
        restante -= usar
        primera = primera or r.id
        if r.cantidad_consumida >= r.cantidad:
            r.estado, r.fecha_cierre = "CONSUMIDA", ahora()
    return primera


# ---------------------------------------------------------------- salidas

def registrar_salida(db: Session, ctx, existencia: Existencia, cantidad_base: Decimal, tipo: str, *,
                     proceso: Proceso | None = None, motivo_id=None, motivo_texto=None, observacion=None,
                     justificacion: str | None = None, confirmar_fifo: bool = False, clave_idempotencia: str | None = None,
                     cantidad_ingresada=None, unidad_ingresada_id=None, documento_id=None, detalle_id=None,
                     evaluar_fifo: bool = True, fecha: datetime | None = None) -> tuple[MovimientoInventario, dict]:
    """Salida o consumo de una existencia concreta, valorizada con su propio costo unitario."""
    info: dict = {"duplicado": False, "avisos": [], "fifo": None}
    if clave_idempotencia:
        previo = db.scalar(select(MovimientoInventario).where(MovimientoInventario.clave_idempotencia == clave_idempotencia))
        if previo:  # doble toque o reintento por mala senal: se devuelve el mismo movimiento
            info["duplicado"] = True
            return previo, info
    cantidad_base = q6(cantidad_base)
    if cantidad_base <= 0:
        raise ErrorNegocio("CANTIDAD", "La cantidad debe ser mayor que cero.")
    if ctx:
        ctx.exigir_bodega(existencia.bodega_id)
        ctx.exigir_familia(existencia.producto.subfamilia.familia_id)

    bloquear_producto(db, existencia.producto_id)
    db.refresh(existencia)
    info["avisos"] = validar_estado_consumible(ctx, existencia)
    politica = politica_efectiva(existencia.producto)

    recomendada = evaluar_orden(db, existencia, politica) if evaluar_fifo else None
    if recomendada:
        pol = recomendada["politica"]
        if pol == "BLOQUEAR":
            raise ErrorNegocio("FIFO_BLOQUEADO", recomendada["mensaje"] + " La política no permite continuar.", 409, recomendada)
        if pol == "PERMISO" and not (ctx and ctx.puede("fifo:omitir")):
            raise ErrorNegocio("FIFO_PERMISO", recomendada["mensaje"] + " Requiere un permiso especial.", 403, recomendada)
        if pol == "JUSTIFICAR" and not (justificacion or "").strip():
            raise ErrorNegocio("FIFO_JUSTIFICACION", recomendada["mensaje"] + " Indique una justificación.", 409, recomendada)
        if not confirmar_fifo and not (pol == "JUSTIFICAR" and (justificacion or "").strip()):
            raise ErrorNegocio("FIFO_ADVERTENCIA", recomendada["mensaje"], 409, recomendada)
        info["fifo"] = recomendada

    if parametro(db, "reservas.bloquean_consumo", existencia.empresa_id, True):
        libre = disponible_para(db, existencia, proceso.id if proceso else None)
        if cantidad_base > libre and cantidad_base <= existencia.cantidad_fisica:
            raise ErrorNegocio("STOCK_RESERVADO", f"Solo hay {libre.normalize():f} {existencia.unidad.codigo} disponibles: "
                               "el resto está reservado.", 409,
                               {"disponible": float(libre), "fisico": float(existencia.cantidad_fisica)})

    costo = costo_salida(db, existencia, cantidad_base)
    descontar(db, existencia, cantidad_base)
    reserva_id = aplicar_a_reservas(db, existencia, proceso.id if proceso else None, cantidad_base)
    m = movimiento(db, ctx, existencia, tipo, -cantidad_base, costo_total=-costo, fecha=fecha,
                   bodega_origen_id=existencia.bodega_id, ubicacion_origen_id=existencia.ubicacion_id, proceso=proceso,
                   documento_id=documento_id, detalle_id=detalle_id, motivo_id=motivo_id, motivo_texto=motivo_texto,
                   observacion=observacion, clave_idempotencia=clave_idempotencia, cantidad_ingresada=cantidad_ingresada,
                   unidad_ingresada_id=unidad_ingresada_id, reserva_id=reserva_id)
    if recomendada:
        db.add(ExcepcionFifo(movimiento_id=m.id, existencia_recomendada_id=recomendada["existencia_id"],
                             estrategia=recomendada["estrategia"], politica=recomendada["politica"],
                             justificacion=(justificacion or "").strip() or None, usuario_id=ctx.usuario.id if ctx else None))
        from .alertas import crear_alerta
        crear_alerta(db, existencia.empresa_id, "CONSUMO_FUERA_FIFO",
                     f"Consumo fuera de orden: {existencia.producto.nombre}",
                     f"Se uso {existencia.codigo_publico} existiendo {recomendada['codigo_publico']} "
                     f"(lote {recomendada['lote'] or '-'}) con prioridad.", entidad="movimiento", entidad_id=m.id,
                     clave=f"FIFO:{m.id}", bodega_id=existencia.bodega_id, usuario_id=ctx.usuario.id if ctx else None)
    return m, info


# ---------------------------------------------------------------- anulacion

NO_ANULABLES = ("TRASLADO_SALIDA", "TRASLADO_ENTRADA", "FRACCIONAMIENTO_SALIDA", "FRACCIONAMIENTO_ENTRADA", "ANULACION")


def anular_movimiento(db: Session, ctx, m: MovimientoInventario, motivo: str, *, forzar_tipo: bool = False) -> MovimientoInventario:
    """Genera el movimiento inverso. El original no se modifica ni se elimina."""
    if not (motivo or "").strip():
        raise ErrorNegocio("MOTIVO", "Debe indicar el motivo de la anulacion.")
    if m.tipo.codigo in NO_ANULABLES and not forzar_tipo:
        raise ErrorNegocio("NO_ANULABLE", "Este tipo de movimiento no se anula directamente: registre la operacion inversa.")
    if db.scalar(select(MovimientoInventario.id).where(MovimientoInventario.movimiento_anulado_id == m.id)):
        raise ErrorNegocio("YA_ANULADO", "El movimiento ya fue anulado.", 409)
    e = db.get(Existencia, m.existencia_id)
    bloquear_producto(db, e.producto_id)
    db.refresh(e)
    if m.proceso_id:
        p = db.get(Proceso, m.proceso_id)
        if p.estado == "CERRADO":
            raise ErrorNegocio("PROCESO_CERRADO", "El proceso esta cerrado: no se pueden anular sus consumos.", 409)
    if m.cantidad < 0:
        aumentar(db, e, -m.cantidad)
    else:
        descontar(db, e, m.cantidad)
    inverso = movimiento(db, ctx, e, "ANULACION", -m.cantidad, costo_total=-m.costo_total,
                         bodega_origen_id=m.bodega_destino_id, bodega_destino_id=m.bodega_origen_id,
                         ubicacion_origen_id=m.ubicacion_destino_id, ubicacion_destino_id=m.ubicacion_origen_id,
                         proceso=db.get(Proceso, m.proceso_id) if m.proceso_id else None, documento_id=m.documento_id,
                         detalle_id=m.detalle_documento_id, motivo_id=m.motivo_id, motivo_texto=motivo.strip(), anula=m,
                         reserva_id=m.reserva_id)
    if m.reserva_id and m.cantidad < 0:  # el consumo anulado devuelve su parte a la reserva
        r = db.get(ReservaStock, m.reserva_id)
        if r and r.estado in ("ACTIVA", "CONSUMIDA"):
            r.cantidad_consumida = max(CERO, r.cantidad_consumida + m.cantidad)
            if r.estado == "CONSUMIDA" and r.cantidad_consumida < r.cantidad:
                r.estado, r.fecha_cierre = "ACTIVA", None
    auditar(db, ctx, "movimiento", m.id, "ANULAR", nuevo={"movimiento_inverso": inverso.id}, motivo=motivo)
    return inverso


def esta_anulado(db: Session, movimiento_id: int) -> bool:
    return db.scalar(select(MovimientoInventario.id).where(MovimientoInventario.movimiento_anulado_id == movimiento_id)) is not None


# ---------------------------------------------------------------- documentos

def _ubicacion_valida(db: Session, bodega_id: int, ubicacion_id: int | None, requerida: bool, etiqueta: str) -> None:
    if ubicacion_id is None:
        if requerida:
            raise ErrorNegocio("UBICACION_REQUERIDA", f"{etiqueta}: debe indicar la ubicacion.")
        return
    u = db.get(Ubicacion, ubicacion_id)
    if not u or u.bodega_id != bodega_id or not u.activo:
        raise ErrorNegocio("UBICACION", f"{etiqueta}: la ubicacion no pertenece a la bodega o esta inactiva.")
    if not u.almacenable:
        raise ErrorNegocio("UBICACION", f"{etiqueta}: {u.codigo_completo} no admite stock (elija una posicion).")


def _confirmar_ingreso(db: Session, ctx, doc: DocumentoInventario, tipo_mov: str) -> list[Existencia]:
    import json
    bodega = db.get(Bodega, doc.bodega_id)
    proceso = db.get(Proceso, doc.proceso_id) if doc.proceso_id else None
    from app.modelos import Temporada
    temporada = db.get(Temporada, doc.temporada_id).codigo if doc.temporada_id else ""
    creadas: list[Existencia] = []
    for n, det in enumerate(doc.detalles, 1):
        producto = db.get(Producto, det.producto_id)
        if not producto or producto.empresa_id != doc.empresa_id or not producto.activo:
            raise ErrorNegocio("PRODUCTO", f"Linea {n}: producto inexistente o inactivo.")
        if ctx:
            ctx.exigir_familia(producto.subfamilia.familia_id)
        pol = politica_efectiva(producto)
        if dec(det.cantidad) <= 0:
            raise ErrorNegocio("CANTIDAD", f"Linea {n}: la cantidad debe ser mayor que cero.")
        if det.precio_unitario is None or dec(det.precio_unitario) < 0:
            raise ErrorNegocio("COSTO_REQUERIDO", f"Linea {n}: todo ingreso debe indicar su valor unitario.")
        base, factor = a_unidad_base(db, producto, det.cantidad, det.unidad_id)
        det.cantidad_base = q6(base)
        det.costo_unitario_base = q6(dec(det.precio_unitario) / factor)
        det.costo_total = q2(dec(det.cantidad) * dec(det.precio_unitario))
        _ubicacion_valida(db, doc.bodega_id, det.ubicacion_id, bool(pol["requiere_ubicacion"]), f"Linea {n}")

        lote = None
        if pol["usa_lote"]:
            if det.lote_id:
                lote = db.get(Lote, det.lote_id)
                if not lote or lote.producto_id != producto.id or lote.estado == "ANULADO":
                    raise ErrorNegocio("LOTE", f"Linea {n}: el lote indicado no corresponde al producto.")
            else:
                lote = crear_lote(db, ctx, producto, bodega=bodega, fecha=doc.fecha, codigo_manual=det.lote_manual,
                                  manuales=json.loads(det.campos_lote) if det.campos_lote else None,
                                  fecha_fabricacion=det.fecha_fabricacion, fecha_vencimiento=det.fecha_vencimiento,
                                  referencia_externa=det.referencia_externa, proceso_codigo=proceso.codigo if proceso else "",
                                  temporada=temporada, documento_id=doc.id, politica=pol)
                det.lote_id = lote.id
            det.fecha_vencimiento = lote.fecha_vencimiento

        # Granularidad: cuantas existencias (QR) genera la linea.
        gran = pol["granularidad"]
        unidad_es_envase = det.unidad_id != producto.unidad_base_id
        if gran == "POR_ENVASE":
            partes = det.bultos or (int(det.cantidad) if unidad_es_envase and dec(det.cantidad) == int(det.cantidad) else 1)
        elif gran == "UNIDAD_LOGISTICA":
            partes = det.bultos or 1
        else:  # POR_LOTE y CONSOLIDADA: una sola existencia con el total
            partes = 1
        if partes < 1 or partes > 500:
            raise ErrorNegocio("BULTOS", f"Linea {n}: la cantidad de existencias a generar debe estar entre 1 y 500.")
        envases_c = int(dec(det.cantidad) / partes) if unidad_es_envase and gran != "POR_ENVASE" else None
        porcion = q6(det.cantidad_base / partes)
        valor_total, asignado_c, asignado_v = det.costo_total, CERO, CERO
        for i in range(partes):
            ultima = i == partes - 1
            cant = det.cantidad_base - asignado_c if ultima else porcion
            valor = valor_total - asignado_v if ultima else q2(porcion * det.costo_unitario_base)
            asignado_c += cant
            asignado_v += valor
            e = nueva_existencia(db, ctx, producto=producto, lote=lote, bodega_id=doc.bodega_id,
                                 ubicacion_id=det.ubicacion_id, cantidad=cant, costo_unitario=det.costo_unitario_base,
                                 fecha_ingreso=doc.fecha, granularidad=gran, detalle_id=det.id, envases=envases_c,
                                 proveedor_id=doc.proveedor_id, moneda=doc.moneda, fecha_costo=doc.fecha_documento)
            aumentar(db, e, cant)
            movimiento(db, ctx, e, tipo_mov, cant, costo_total=valor, fecha=doc.fecha, bodega_destino_id=doc.bodega_id,
                       ubicacion_destino_id=det.ubicacion_id, proceso=proceso, documento_id=doc.id, detalle_id=det.id,
                       motivo_id=doc.motivo_id, cantidad_ingresada=det.cantidad if partes == 1 else None,
                       unidad_ingresada_id=det.unidad_id if partes == 1 else None)
            creadas.append(e)
    return creadas


def trasladar(db: Session, ctx, existencia: Existencia, cantidad: Decimal, bodega_destino_id: int,
              ubicacion_destino_id: int | None, *, documento_id=None, detalle_id=None, observacion=None) -> Existencia:
    """Genera salida y entrada relacionadas. Traslado total: la existencia conserva su QR. Parcial: nace una hija."""
    cantidad = q6(cantidad)
    if cantidad <= 0:
        raise ErrorNegocio("CANTIDAD", "La cantidad debe ser mayor que cero.")
    if ctx:
        ctx.exigir_bodega(existencia.bodega_id)
        ctx.exigir_bodega(bodega_destino_id)
    bloquear_producto(db, existencia.producto_id)
    db.refresh(existencia)
    if existencia.estado == "ANULADA":
        raise ErrorNegocio("EXISTENCIA_ANULADA", "La existencia esta anulada.")
    if existencia.bodega_id == bodega_destino_id and existencia.ubicacion_id == ubicacion_destino_id:
        raise ErrorNegocio("MISMO_DESTINO", "El destino es igual al origen.")
    _ubicacion_valida(db, bodega_destino_id, ubicacion_destino_id, False, "Destino")
    if cantidad > disponible_para(db, existencia, None) and cantidad <= existencia.cantidad_fisica and \
            existencia.bodega_id != bodega_destino_id and parametro(db, "reservas.bloquean_consumo", existencia.empresa_id, True):
        raise ErrorNegocio("STOCK_RESERVADO", "La cantidad a trasladar incluye stock reservado en la bodega de origen.", 409)
    comun = dict(bodega_origen_id=existencia.bodega_id, bodega_destino_id=bodega_destino_id,
                 ubicacion_origen_id=existencia.ubicacion_id, ubicacion_destino_id=ubicacion_destino_id,
                 documento_id=documento_id, detalle_id=detalle_id, observacion=observacion)
    if cantidad == q6(existencia.cantidad_fisica):
        valor = valor_libro(db, existencia.id)
        movimiento(db, ctx, existencia, "TRASLADO_SALIDA", -cantidad, costo_total=-valor, **comun)
        movimiento(db, ctx, existencia, "TRASLADO_ENTRADA", cantidad, costo_total=valor, **comun)
        db.execute(update(Existencia).where(Existencia.id == existencia.id).values(
            bodega_id=bodega_destino_id, ubicacion_id=ubicacion_destino_id, version=Existencia.version + 1))
        db.refresh(existencia)
        return existencia
    valor = q2(cantidad * existencia.costo_unitario)
    descontar(db, existencia, cantidad)
    movimiento(db, ctx, existencia, "TRASLADO_SALIDA", -cantidad, costo_total=-valor, **comun)
    # La hija hereda lote, costo y fecha de ingreso: el traslado no rejuvenece el stock ni genera resultado.
    hija = nueva_existencia(db, ctx, producto=existencia.producto, lote=existencia.lote, bodega_id=bodega_destino_id,
                            ubicacion_id=ubicacion_destino_id, cantidad=cantidad, costo_unitario=existencia.costo_unitario,
                            fecha_ingreso=existencia.fecha_ingreso, granularidad=existencia.granularidad, padre=existencia,
                            proveedor_id=existencia.proveedor_id, moneda=existencia.moneda, fecha_costo=existencia.fecha_costo)
    aumentar(db, hija, cantidad)
    movimiento(db, ctx, hija, "TRASLADO_ENTRADA", cantidad, costo_total=valor, **comun)
    return hija


def ajustar(db: Session, ctx, existencia: Existencia, diferencia: Decimal, *, motivo_texto: str, documento_id=None,
            detalle_id=None, motivo_id=None) -> MovimientoInventario:
    diferencia = q6(diferencia)
    if diferencia == 0:
        raise ErrorNegocio("CANTIDAD", "El ajuste no puede ser cero.")
    bloquear_producto(db, existencia.producto_id)
    db.refresh(existencia)
    if diferencia > 0:
        aumentar(db, existencia, diferencia)
        return movimiento(db, ctx, existencia, "AJUSTE_POSITIVO", diferencia, bodega_destino_id=existencia.bodega_id,
                          ubicacion_destino_id=existencia.ubicacion_id, documento_id=documento_id, detalle_id=detalle_id,
                          motivo_texto=motivo_texto, motivo_id=motivo_id)
    costo = costo_salida(db, existencia, -diferencia)
    descontar(db, existencia, -diferencia)
    return movimiento(db, ctx, existencia, "AJUSTE_NEGATIVO", diferencia, costo_total=-costo,
                      bodega_origen_id=existencia.bodega_id, ubicacion_origen_id=existencia.ubicacion_id,
                      documento_id=documento_id, detalle_id=detalle_id, motivo_texto=motivo_texto, motivo_id=motivo_id)


def _existencia_de(db: Session, doc: DocumentoInventario, det: DetalleDocumentoInventario, n: int) -> Existencia:
    e = db.get(Existencia, det.existencia_id) if det.existencia_id else None
    if not e or e.empresa_id != doc.empresa_id:
        raise ErrorNegocio("EXISTENCIA", f"Linea {n}: debe indicar una existencia valida.")
    if e.bodega_id != doc.bodega_id:
        raise ErrorNegocio("EXISTENCIA", f"Linea {n}: la existencia {e.codigo_publico} no esta en la bodega del documento.")
    return e


def confirmar_documento(db: Session, ctx, doc: DocumentoInventario) -> dict:
    """BORRADOR -> CONFIRMADO. Genera los movimientos, que desde aqui son inmutables."""
    if doc.estado != "BORRADOR":
        raise ErrorNegocio("ESTADO", f"El documento esta {doc.estado}: solo un borrador puede confirmarse.", 409)
    if not doc.detalles:
        raise ErrorNegocio("SIN_DETALLE", "El documento no tiene lineas.")
    if ctx:
        ctx.exigir_bodega(doc.bodega_id)
    motivo = db.get(MotivoMovimiento, doc.motivo_id) if doc.motivo_id else None
    proceso = db.get(Proceso, doc.proceso_id) if doc.proceso_id else None
    if motivo and motivo.requiere_documento and not (doc.numero_documento or "").strip():
        raise ErrorNegocio("DOCUMENTO_REQUERIDO", f"El motivo {motivo.nombre} exige numero de documento.")
    if motivo and motivo.requiere_proceso and not proceso:
        raise ErrorNegocio("PROCESO_REQUERIDO", f"El motivo {motivo.nombre} exige un proceso.")
    if proceso and proceso.estado != "ABIERTO" and doc.clase == "SALIDA":
        raise ErrorNegocio("PROCESO_NO_ABIERTO", "El proceso debe estar ABIERTO para registrar consumos.", 409)
    resultado: dict = {"existencias": []}
    if doc.clase == "INGRESO":
        tipo = motivo.tipo_movimiento.codigo if motivo else "INGRESO"
        resultado["existencias"] = [e.id for e in _confirmar_ingreso(db, ctx, doc, tipo)]
    elif doc.clase == "SALIDA":
        tipo = motivo.tipo_movimiento.codigo if motivo else "SALIDA"
        for n, det in enumerate(doc.detalles, 1):
            e = _existencia_de(db, doc, det, n)
            base, _ = a_unidad_base(db, e.producto, det.cantidad, det.unidad_id)
            det.cantidad_base = q6(base)
            m, _info = registrar_salida(db, ctx, e, base, tipo, proceso=proceso, motivo_id=doc.motivo_id,
                                        justificacion=det.observaciones or doc.observaciones, confirmar_fifo=True,
                                        documento_id=doc.id, detalle_id=det.id, cantidad_ingresada=det.cantidad,
                                        unidad_ingresada_id=det.unidad_id, observacion=det.observaciones)
            det.costo_unitario_base, det.costo_total, det.lote_id = e.costo_unitario, -m.costo_total, e.lote_id
    elif doc.clase == "TRASLADO":
        destino = doc.bodega_destino_id or doc.bodega_id
        for n, det in enumerate(doc.detalles, 1):
            e = _existencia_de(db, doc, det, n)
            base, _ = a_unidad_base(db, e.producto, det.cantidad, det.unidad_id)
            det.cantidad_base = q6(base)
            hija = trasladar(db, ctx, e, base, destino, det.ubicacion_destino_id, documento_id=doc.id, detalle_id=det.id,
                             observacion=det.observaciones)
            resultado["existencias"].append(hija.id)
    elif doc.clase == "AJUSTE":
        if not (doc.observaciones or "").strip():
            raise ErrorNegocio("MOTIVO", "Un ajuste debe indicar el motivo en observaciones.")
        for n, det in enumerate(doc.detalles, 1):
            e = _existencia_de(db, doc, det, n)
            base, _ = a_unidad_base(db, e.producto, det.cantidad, det.unidad_id)
            det.cantidad_base = q6(base)
            ajustar(db, ctx, e, base, motivo_texto=doc.observaciones, documento_id=doc.id, detalle_id=det.id,
                    motivo_id=doc.motivo_id)
    else:
        raise ErrorNegocio("CLASE", f"Clase de documento desconocida: {doc.clase}")
    doc.estado, doc.confirmado_en, doc.confirmado_por = "CONFIRMADO", ahora(), ctx.usuario.id if ctx else None
    db.flush()
    auditar(db, ctx, "documento_inventario", doc.id, "CONFIRMAR", nuevo={"numero": doc.numero, "clase": doc.clase})
    return resultado


def anular_documento(db: Session, ctx, doc: DocumentoInventario, motivo: str) -> None:
    """Borrador: se marca anulado. Confirmado: se revierte cada movimiento con su inverso."""
    if doc.estado == "ANULADO":
        raise ErrorNegocio("ESTADO", "El documento ya esta anulado.", 409)
    if not (motivo or "").strip():
        raise ErrorNegocio("MOTIVO", "Debe indicar el motivo de la anulacion.")
    if doc.estado == "CONFIRMADO":
        if doc.clase == "TRASLADO":
            raise ErrorNegocio("NO_ANULABLE", "Un traslado confirmado se corrige con un traslado inverso.")
        movs = db.scalars(select(MovimientoInventario).where(
            MovimientoInventario.documento_id == doc.id, MovimientoInventario.movimiento_anulado_id.is_(None))
            .order_by(MovimientoInventario.id.desc())).all()
        for m in movs:
            if esta_anulado(db, m.id):
                continue
            if doc.clase == "INGRESO":
                e = db.get(Existencia, m.existencia_id)
                otros = db.scalar(select(func.count()).select_from(MovimientoInventario).where(
                    MovimientoInventario.existencia_id == e.id, MovimientoInventario.id != m.id))
                hijas = db.scalar(select(func.count()).select_from(Existencia).where(Existencia.existencia_padre_id == e.id))
                if otros or hijas:
                    raise ErrorNegocio("CON_MOVIMIENTOS", f"La existencia {e.codigo_publico} ya tiene movimientos "
                                       "posteriores: anule o revierta primero esos movimientos.", 409)
            anular_movimiento(db, ctx, m, motivo)
            if doc.clase == "INGRESO":
                e = db.get(Existencia, m.existencia_id)
                e.estado = "ANULADA"
                if e.lote_id and e.lote.documento_origen_id == doc.id:
                    vivas = db.scalar(select(func.count()).select_from(Existencia).where(
                        Existencia.lote_id == e.lote_id, Existencia.estado != "ANULADA", Existencia.id != e.id))
                    if not vivas:  # el numero de lote no se reutiliza
                        cambiar_estado_lote(db, ctx, e.lote, "ANULADO", f"Anulacion de {doc.numero}")
    doc.estado, doc.anulado_en, doc.anulado_por, doc.motivo_anulacion = "ANULADO", ahora(), ctx.usuario.id if ctx else None, motivo
    auditar(db, ctx, "documento_inventario", doc.id, "ANULAR", motivo=motivo)
