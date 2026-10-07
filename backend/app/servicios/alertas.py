"""Centro de alertas: creacion sin duplicados, evaluacion de reglas configurables y resolucion automatica."""
from datetime import timedelta
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.util import ahora, dec, dia_local, hoy
from app.modelos import (Alerta, Existencia, Lote, Prestamo, Proceso, Producto, ReglaAlerta, ReservaStock)

ABIERTAS = ("NUEVA", "LEIDA", "EN_GESTION")
# Alertas de estado: se resuelven solas cuando la condicion deja de cumplirse.
DE_ESTADO = ("STOCK_BAJO", "STOCK_CRITICO", "STOCK_AGOTADO", "PRODUCTO_VENCIDO", "PROXIMO_A_VENCER", "STOCK_ANTIGUO",
             "LOTE_BLOQUEADO", "LOTE_CUARENTENA", "PROCESO_SIN_SINCRONIZAR", "PRESTAMO_VENCIDO")

# Canales de notificacion (email, Teams, Telegram, WhatsApp...). Cada canal es una funcion que recibe la alerta.
# Hoy no hay canales registrados: el punto de extension existe para agregarlos sin tocar el resto.
CANALES: dict[str, Callable[[Alerta], None]] = {}


def registrar_canal(nombre: str, enviar: Callable[[Alerta], None]) -> None:
    CANALES[nombre.upper()] = enviar


def _notificar(alerta: Alerta, regla: ReglaAlerta | None) -> None:
    for nombre in (regla.canales if regla and regla.canales else []):
        canal = CANALES.get(str(nombre).upper())
        if canal:
            try:
                canal(alerta)
                alerta.notificada = True
            except Exception:  # una falla de notificacion no debe revertir la operacion de negocio
                pass


def _regla(db: Session, empresa_id: int, tipo: str) -> ReglaAlerta | None:
    return db.scalar(select(ReglaAlerta).where(ReglaAlerta.empresa_id == empresa_id, ReglaAlerta.tipo == tipo))


def crear_alerta(db: Session, empresa_id: int, tipo: str, titulo: str, descripcion: str | None = None, *,
                 entidad: str | None = None, entidad_id: int | None = None, clave: str | None = None,
                 bodega_id: int | None = None, usuario_id: int | None = None, fecha_vencimiento=None,
                 severidad: str | None = None, regla: ReglaAlerta | None = None) -> Alerta | None:
    regla = regla or _regla(db, empresa_id, tipo)
    if regla is not None and not regla.activa:
        return None
    clave = clave or f"{tipo}:{entidad}:{entidad_id}"
    existente = db.scalar(select(Alerta).where(Alerta.empresa_id == empresa_id, Alerta.clave == clave,
                                               Alerta.estado.in_(ABIERTAS)))
    if existente:
        existente.descripcion = descripcion or existente.descripcion
        return existente
    a = Alerta(empresa_id=empresa_id, tipo=tipo, severidad=severidad or (regla.severidad if regla else "MEDIA"),
               titulo=titulo[:200], descripcion=descripcion, entidad=entidad, entidad_id=entidad_id, clave=clave,
               bodega_id=bodega_id, usuario_id=usuario_id, fecha_vencimiento=fecha_vencimiento)
    db.add(a)
    db.flush()
    _notificar(a, regla)
    return a


def evaluar_reglas(db: Session, empresa_id: int) -> dict:
    """Recorre las reglas activas. Devuelve cuantas alertas se crearon y cuantas se resolvieron solas."""
    reglas = {r.tipo: r for r in db.scalars(select(ReglaAlerta).where(ReglaAlerta.empresa_id == empresa_id))}
    activas = {t: r for t, r in reglas.items() if r.activa}
    antes = db.scalar(select(func.count()).select_from(Alerta).where(Alerta.empresa_id == empresa_id))
    vigentes: dict[str, set[str]] = {t: set() for t in DE_ESTADO}

    def alerta(tipo, titulo, desc, entidad, entidad_id, **kw):
        if tipo not in activas:
            return
        clave = f"{tipo}:{entidad}:{entidad_id}"
        vigentes.setdefault(tipo, set()).add(clave)
        crear_alerta(db, empresa_id, tipo, titulo, desc, entidad=entidad, entidad_id=entidad_id, clave=clave,
                     regla=activas[tipo], **kw)

    def num(valor) -> str:
        return f"{dec(valor).normalize():f}"

    # --- niveles de stock por producto
    stock = dict(db.execute(select(Existencia.producto_id, func.sum(Existencia.cantidad_fisica)).where(
        Existencia.empresa_id == empresa_id, Existencia.estado.in_(("DISPONIBLE", "BLOQUEADA"))).group_by(Existencia.producto_id)).all())
    for p in db.scalars(select(Producto).where(Producto.empresa_id == empresa_id, Producto.activo.is_(True))).unique():
        if p.stock_minimo is None and p.stock_critico is None:
            continue
        total, u = dec(stock.get(p.id)), p.unidad_base.codigo
        if total <= 0:
            alerta("STOCK_AGOTADO", f"Sin stock: {p.nombre}", f"{p.codigo} no tiene existencias.", "producto", p.id)
        elif p.stock_critico is not None and total <= p.stock_critico:
            alerta("STOCK_CRITICO", f"Stock critico: {p.nombre}",
                   f"Quedan {num(total)} {u}; nivel critico {num(p.stock_critico)} {u}.", "producto", p.id)
        elif p.stock_minimo is not None and total <= p.stock_minimo:
            alerta("STOCK_BAJO", f"Stock bajo: {p.nombre}",
                   f"Quedan {num(total)} {u}; minimo {num(p.stock_minimo)} {u}.", "producto", p.id)

    # --- lotes: vencimiento y estados
    hoy_ = hoy()
    dias_aviso = int((activas.get("PROXIMO_A_VENCER").parametros or {}).get("dias", 30)) if "PROXIMO_A_VENCER" in activas else 30
    sumas = dict(db.execute(select(Existencia.lote_id, func.sum(Existencia.cantidad_fisica)).where(
        Existencia.empresa_id == empresa_id, Existencia.cantidad_fisica > 0, Existencia.lote_id.is_not(None))
        .group_by(Existencia.lote_id)).all())
    lotes = db.scalars(select(Lote).where(Lote.id.in_(list(sumas)))).unique().all() if sumas else []
    for lote in lotes:
        cantidad = sumas[lote.id]
        nombre, u = lote.producto.nombre, lote.producto.unidad_base.codigo
        if lote.fecha_vencimiento and lote.fecha_vencimiento < hoy_:
            if lote.estado == "DISPONIBLE":
                from .lotes import cambiar_estado_lote
                cambiar_estado_lote(db, None, lote, "VENCIDO", "Vencimiento automatico")
            alerta("PRODUCTO_VENCIDO", f"Lote vencido: {lote.codigo}",
                   f"{nombre}: {num(cantidad)} {u} vencidos el {lote.fecha_vencimiento:%d-%m-%Y}.", "lote", lote.id)
        elif lote.fecha_vencimiento and (lote.fecha_vencimiento - hoy_).days <= dias_aviso:
            alerta("PROXIMO_A_VENCER", f"Proximo a vencer: {lote.codigo}",
                   f"{nombre}: {num(cantidad)} {u} vencen en {(lote.fecha_vencimiento - hoy_).days} dias "
                   f"({lote.fecha_vencimiento:%d-%m-%Y}).", "lote", lote.id,
                   fecha_vencimiento=ahora().replace(year=lote.fecha_vencimiento.year, month=lote.fecha_vencimiento.month,
                                                     day=min(lote.fecha_vencimiento.day, 28)))
        if lote.estado == "BLOQUEADO":
            alerta("LOTE_BLOQUEADO", f"Lote bloqueado: {lote.codigo}", f"{nombre}: {num(cantidad)} {u} retenidos.", "lote", lote.id)
        elif lote.estado == "CUARENTENA":
            alerta("LOTE_CUARENTENA", f"Lote en cuarentena: {lote.codigo}", f"{nombre}: {num(cantidad)} {u} en cuarentena.", "lote", lote.id)

    # --- stock antiguo
    if "STOCK_ANTIGUO" in activas:
        dias = int((activas["STOCK_ANTIGUO"].parametros or {}).get("dias", 60))
        limite = ahora() - timedelta(days=dias)
        for e in db.scalars(select(Existencia).where(Existencia.empresa_id == empresa_id, Existencia.cantidad_fisica > 0,
                                                     Existencia.fecha_ingreso < limite)).unique():
            alerta("STOCK_ANTIGUO", f"Stock antiguo: {e.producto.nombre}",
                   f"{e.codigo_publico} ingreso hace {(hoy_ - dia_local(e.fecha_ingreso)).days} dias y conserva "
                   f"{num(e.cantidad_fisica)} {e.unidad.codigo}.", "existencia", e.id, bodega_id=e.bodega_id)

    # --- procesos abiertos sin sincronizar
    if "PROCESO_SIN_SINCRONIZAR" in activas:
        horas = int((activas["PROCESO_SIN_SINCRONIZAR"].parametros or {}).get("horas", 24))
        limite = ahora() - timedelta(hours=horas)
        for p in db.scalars(select(Proceso).where(Proceso.empresa_id == empresa_id, Proceso.estado == "ABIERTO",
                                                  Proceso.fuente_id.is_not(None))):
            if p.ultima_sincronizacion is None or p.ultima_sincronizacion < limite:
                alerta("PROCESO_SIN_SINCRONIZAR", f"Proceso sin sincronizar: {p.codigo}",
                       f"Ultima sincronizacion: {p.ultima_sincronizacion:%d-%m-%Y %H:%M}." if p.ultima_sincronizacion
                       else "Nunca se ha sincronizado con produccion.", "proceso", p.id)

    # --- prestamos vencidos
    for pr in db.scalars(select(Prestamo).where(Prestamo.empresa_id == empresa_id, Prestamo.estado.in_(("ACTIVO", "PARCIAL")),
                                                Prestamo.fecha_devolucion_esperada < hoy_)):
        alerta("PRESTAMO_VENCIDO", f"Prestamo vencido: {pr.numero}",
               f"{pr.persona} debia devolver el {pr.fecha_devolucion_esperada:%d-%m-%Y}.", "prestamo", pr.id)

    # --- reservas vencidas: se liberan y se avisa (evento, no se resuelve sola)
    for r in db.scalars(select(ReservaStock).where(ReservaStock.empresa_id == empresa_id, ReservaStock.estado == "ACTIVA",
                                                   ReservaStock.fecha_vencimiento < ahora())).unique():
        r.estado, r.fecha_cierre = "VENCIDA", ahora()
        if "RESERVA_VENCIDA" in activas:
            crear_alerta(db, empresa_id, "RESERVA_VENCIDA", f"Reserva vencida: {r.numero}",
                         f"{r.producto.nombre}: se liberaron {num(r.cantidad - r.cantidad_consumida)} "
                         f"{r.producto.unidad_base.codigo} reservados.", entidad="reserva", entidad_id=r.id,
                         clave=f"RESERVA_VENCIDA:reserva:{r.id}", bodega_id=r.bodega_id, regla=activas["RESERVA_VENCIDA"])

    # --- resolucion automatica de alertas de estado cuya condicion ya no se cumple
    resueltas = 0
    for a in db.scalars(select(Alerta).where(Alerta.empresa_id == empresa_id, Alerta.estado.in_(ABIERTAS),
                                             Alerta.tipo.in_(DE_ESTADO))):
        if a.clave not in vigentes.get(a.tipo, set()):
            a.estado, a.fecha_resolucion, a.observacion = "RESUELTA", ahora(), "Condicion normalizada (resolucion automatica)."
            resueltas += 1
    db.flush()
    despues = db.scalar(select(func.count()).select_from(Alerta).where(Alerta.empresa_id == empresa_id))
    return {"creadas": despues - antes, "resueltas": resueltas}
