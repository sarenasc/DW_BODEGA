"""Procesos productivos: copia local, apertura, actualizacion, cierre y costeo."""
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.auditoria import auditar, siguiente_numero
from app.core.crud import paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict, ahora, json_valor, ocultar_costos
from app.modelos import (BASES_COSTEO, CAMPOS_NUMERICOS, CAMPOS_PROCESO, CambioProceso, CapturaProceso,
                         FuenteIntegracion, MovimientoInventario, Proceso, ReservaStock, Temporada, TipoMovimiento, Usuario)
from app.servicios import costeo
from app.servicios.alertas import crear_alerta
from app.servicios.integracion import sincronizar_proceso

router = APIRouter(prefix="/api", tags=["Procesos"])
VER = "procesos:ver"


def obtener_proceso(db: Session, ctx: Contexto, id_: int) -> Proceso:
    p = db.get(Proceso, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Proceso")
    return p


def proceso_dict(db: Session, p: Proceso, ctx: Contexto, detalle: bool = False) -> dict:
    d = a_dict(p)
    campo = costeo.campo_base(db, p)
    kilos = costeo.kilos_base(db, p, campo)
    total = costeo.costo_proceso(db, p.id)
    d.update(base_costeo_efectiva=campo, base_costeo_nombre=costeo.ETIQUETAS_BASE.get(campo, campo),
             kilos_base=float(kilos) if kilos is not None else None, costo_total=float(total),
             costo_por_kilo=float(total / kilos) if kilos else None, tiene_fuente=p.fuente_id is not None)
    if detalle:
        nombres = dict(db.execute(select(Usuario.id, Usuario.nombre)).all())
        d["fuente"] = db.get(FuenteIntegracion, p.fuente_id).nombre if p.fuente_id else None
        d["temporada_codigo"] = db.get(Temporada, p.temporada_id).codigo if p.temporada_id else p.temporada
        d["abierto_por_nombre"], d["cerrado_por_nombre"] = nombres.get(p.abierto_por), nombres.get(p.cerrado_por)
        d["costos"] = costeo.resumen_costos(db, p)
        d["cambios"] = [a_dict(c, usuario=nombres.get(c.usuario_id)) for c in db.scalars(
            select(CambioProceso).where(CambioProceso.proceso_id == p.id).order_by(CambioProceso.id.desc()).limit(200))]
        d["capturas"] = db.scalar(select(func.count()).select_from(CapturaProceso).where(CapturaProceso.proceso_id == p.id))
        d["reservas_activas"] = db.scalar(select(func.count()).select_from(ReservaStock).where(
            ReservaStock.proceso_id == p.id, ReservaStock.estado == "ACTIVA"))
    return ocultar_costos(d, ctx.ver_costos)


class ProcesoEntrada(BaseModel):
    codigo: str | None = None
    numero: str | None = None
    tipo: str | None = None
    fecha: date | None = None
    hora_inicio: str | None = None
    hora_termino: str | None = None
    temporada_id: int | None = None
    exportadora: str | None = None
    productor: str | None = None
    codigo_productor: str | None = None
    campo: str | None = None
    predio: str | None = None
    especie: str | None = None
    variedad: str | None = None
    lote_productivo: str | None = None
    numero_lote: str | None = None
    kilos_recepcionados: Decimal | None = None
    kilos_procesados: Decimal | None = None
    kilos_producidos: Decimal | None = None
    kilos_despachados: Decimal | None = None
    cantidad: Decimal | None = None
    bins: Decimal | None = None
    cajas: Decimal | None = None
    turno: str | None = None
    linea: str | None = None
    guia: str | None = None
    recepcion_relacionada: str | None = None
    base_costeo: str | None = None
    observaciones: str | None = None
    datos_adicionales: dict | None = None


def _validar_base(db: Session, base: str | None) -> None:
    if base and base not in BASES_COSTEO and not base.startswith("extra."):
        raise ErrorNegocio("BASE_COSTEO", "Base de costeo no valida: use un campo de kilos o extra.<clave>.")


@router.get("/procesos")
def listar(estado: str | None = None, temporada_id: int | None = None, especie: str | None = None,
           productor: str | None = None, q: str | None = None, desde: date | None = None, hasta: date | None = None,
           pagina: int = Query(1, ge=1), tam: int = Query(50, le=500), db: Session = Depends(get_db),
           ctx: Contexto = Depends(requiere(VER))):
    c = select(Proceso).where(Proceso.empresa_id == ctx.empresa_id)
    for col, val in ((Proceso.estado, estado), (Proceso.temporada_id, temporada_id), (Proceso.especie, especie),
                     (Proceso.productor, productor)):
        if val:
            c = c.where(col == val)
    if q:
        patron = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Proceso.codigo).like(patron), func.lower(Proceso.productor).like(patron),
                        func.lower(Proceso.especie).like(patron), func.lower(Proceso.variedad).like(patron),
                        func.lower(Proceso.numero).like(patron), func.lower(Proceso.lote_productivo).like(patron)))
    if desde:
        c = c.where(Proceso.fecha >= desde)
    if hasta:
        c = c.where(Proceso.fecha <= hasta)
    return paginar(db, c.order_by(Proceso.fecha.desc(), Proceso.id.desc()), pagina, tam, lambda p: proceso_dict(db, p, ctx))


@router.get("/procesos/valores")
def valores(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    """Valores distintos de las dimensiones de proceso, para los filtros (no hay catalogos fijos de especies o productores)."""
    def distintos(col):
        return [v for (v,) in db.execute(select(col).where(Proceso.empresa_id == ctx.empresa_id, col.is_not(None)).distinct().order_by(col))]
    return {"especies": distintos(Proceso.especie), "productores": distintos(Proceso.productor),
            "variedades": distintos(Proceso.variedad), "exportadoras": distintos(Proceso.exportadora),
            "campos_proceso": CAMPOS_PROCESO, "bases_costeo": [{"codigo": b, "nombre": costeo.ETIQUETAS_BASE[b]} for b in BASES_COSTEO]}


@router.get("/procesos/{id_}")
def ver(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    return proceso_dict(db, obtener_proceso(db, ctx, id_), ctx, detalle=True)


@router.post("/procesos", status_code=201)
def crear(d: ProcesoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:abrir"))):
    """Proceso manual (sin origen externo), p. ej. una sanitizacion."""
    _validar_base(db, d.base_costeo)
    codigo = (d.codigo or "").strip().upper() or siguiente_numero(db, ctx.empresa_id, "proceso", "PROC", 6)
    if db.scalar(select(Proceso.id).where(Proceso.empresa_id == ctx.empresa_id, Proceso.codigo == codigo)):
        raise ErrorNegocio("DUPLICADO", f"Ya existe el proceso {codigo}.", 409)
    p = Proceso(empresa_id=ctx.empresa_id, codigo=codigo, estado="BORRADOR", **d.model_dump(exclude_unset=True, exclude={"codigo"}))
    if p.fecha is None:
        p.fecha = ahora().date()
    if p.temporada_id is None:
        t = db.scalar(select(Temporada).where(Temporada.empresa_id == ctx.empresa_id, Temporada.fecha_inicio <= p.fecha,
                                              Temporada.fecha_termino >= p.fecha))
        p.temporada_id = t.id if t else None
    db.add(p)
    db.flush()
    auditar(db, ctx, "proceso", p.id, "CREAR", nuevo={"codigo": p.codigo})
    return proceso_dict(db, p, ctx, True)


@router.put("/procesos/{id_}")
def editar(id_: int, d: ProcesoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:actualizar"))):
    """Edicion manual. Cada cambio queda en el historial con valor anterior y nuevo."""
    p = obtener_proceso(db, ctx, id_)
    if p.estado in ("CERRADO", "ANULADO"):
        raise ErrorNegocio("ESTADO", f"El proceso esta {p.estado}: no admite cambios.", 409)
    _validar_base(db, d.base_costeo)
    for campo, nuevo in d.model_dump(exclude_unset=True, exclude={"codigo"}).items():
        anterior = getattr(p, campo)
        if anterior == nuevo:
            continue
        setattr(p, campo, nuevo)
        if campo != "datos_adicionales":
            db.add(CambioProceso(proceso_id=p.id, campo=campo, valor_anterior=None if anterior is None else str(json_valor(anterior))[:300],
                                 valor_nuevo=None if nuevo is None else str(json_valor(nuevo))[:300], origen="MANUAL",
                                 usuario_id=ctx.usuario.id))
    auditar(db, ctx, "proceso", p.id, "EDITAR", nuevo=d.model_dump(exclude_unset=True))
    db.flush()
    return proceso_dict(db, p, ctx, True)


@router.post("/procesos/{id_}/abrir")
def abrir(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:abrir"))):
    p = obtener_proceso(db, ctx, id_)
    if p.estado != "BORRADOR":
        raise ErrorNegocio("ESTADO", f"Solo un proceso en BORRADOR puede abrirse (estado actual: {p.estado}).", 409)
    p.estado, p.abierto_en, p.abierto_por = "ABIERTO", ahora(), ctx.usuario.id
    auditar(db, ctx, "proceso", p.id, "ABRIR")
    return proceso_dict(db, p, ctx, True)


@router.post("/procesos/{id_}/actualizar")
def actualizar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:actualizar"))):
    """Consulta nuevamente la base productiva y actualiza los campos configurados."""
    p = obtener_proceso(db, ctx, id_)
    if p.estado in ("CERRADO", "ANULADO"):
        raise ErrorNegocio("ESTADO", f"El proceso esta {p.estado}: ya no se sincroniza con produccion.", 409)
    r = sincronizar_proceso(db, ctx, p, "ACTUALIZAR")
    auditar(db, ctx, "proceso", p.id, "ACTUALIZAR", nuevo=r)
    return {**proceso_dict(db, p, ctx, True), "sincronizacion": r}


class CierreEntrada(BaseModel):
    actualizar: bool = True  # opcion principal: ACTUALIZAR Y CERRAR
    kilos: Decimal | None = None  # kilos definitivos digitados (solo en cierre manual)
    observacion: str | None = None


@router.post("/procesos/{id_}/cerrar")
def cerrar(id_: int, d: CierreEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:cerrar"))):
    p = obtener_proceso(db, ctx, id_)
    # Toma el bloqueo de la fila: un consumo simultaneo ve el proceso abierto o cerrado, nunca a medias.
    r = db.execute(update(Proceso).where(Proceso.id == p.id, Proceso.estado == "ABIERTO").values(version=Proceso.version + 1))
    if r.rowcount == 0:
        raise ErrorNegocio("ESTADO", f"Solo un proceso ABIERTO puede cerrarse (estado actual: {p.estado}).", 409)
    db.refresh(p)
    sincronizado = None
    if p.fuente_id:
        if d.actualizar:
            sincronizar_proceso(db, ctx, p, "CIERRE")
            sincronizado = True
        else:
            ctx.exigir("procesos:cerrar_sin_sincronizar", "Cerrar sin actualizar desde produccion requiere un permiso especial.")
            sincronizado = False
    campo = costeo.campo_base(db, p)
    if d.kilos is not None:
        if sincronizado:
            raise ErrorNegocio("KILOS", "Un cierre sincronizado toma los kilos de produccion: no admite kilos digitados.")
        if d.kilos < 0:
            raise ErrorNegocio("KILOS", "Los kilos no pueden ser negativos.")
        if campo in BASES_COSTEO:
            anterior = getattr(p, campo)
            setattr(p, campo, d.kilos)
            db.add(CambioProceso(proceso_id=p.id, campo=campo, valor_anterior=None if anterior is None else f"{anterior.normalize():f}",
                                 valor_nuevo=f"{d.kilos.normalize():f}", origen="MANUAL", usuario_id=ctx.usuario.id))
    kilos = d.kilos if d.kilos is not None else costeo.kilos_base(db, p, campo)
    p.kilos_definitivos, p.estado_kilos = kilos, "DEFINITIVO"
    p.estado, p.cerrado_en, p.cerrado_por = "CERRADO", ahora(), ctx.usuario.id
    p.cerrado_sincronizado, p.modo_cierre = sincronizado, "SINCRONIZADO" if sincronizado else "MANUAL"
    p.base_costeo = campo  # se congela la base usada: un cambio posterior de configuracion no altera el costo historico
    if d.observacion:
        p.observaciones = ((p.observaciones or "") + f"\nCierre: {d.observacion}").strip()
    for res in db.scalars(select(ReservaStock).where(ReservaStock.proceso_id == p.id, ReservaStock.estado == "ACTIVA")).unique():
        res.estado, res.fecha_cierre, res.cerrada_por = "LIBERADA", ahora(), ctx.usuario.id
    if sincronizado is False:
        crear_alerta(db, p.empresa_id, "PROCESO_CERRADO_SIN_SINCRONIZACION", f"Proceso cerrado sin sincronizar: {p.codigo}",
                     f"Cerrado manualmente por {ctx.usuario.nombre}. Ultima sincronizacion: "
                     f"{p.ultima_sincronizacion:%d-%m-%Y %H:%M}." if p.ultima_sincronizacion else
                     f"Cerrado manualmente por {ctx.usuario.nombre} sin haber sincronizado nunca.",
                     entidad="proceso", entidad_id=p.id, usuario_id=ctx.usuario.id)
    auditar(db, ctx, "proceso", p.id, "CERRAR", nuevo={"modo_cierre": p.modo_cierre, "kilos_definitivos": json_valor(kilos),
                                                      "ultima_sincronizacion": json_valor(p.ultima_sincronizacion)},
            motivo=d.observacion)
    db.flush()
    return proceso_dict(db, p, ctx, True)


class Motivo(BaseModel):
    motivo: str


@router.post("/procesos/{id_}/reabrir")
def reabrir(id_: int, d: Motivo, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:reabrir"))):
    p = obtener_proceso(db, ctx, id_)
    if p.estado != "CERRADO":
        raise ErrorNegocio("ESTADO", "Solo un proceso CERRADO puede reabrirse.", 409)
    if not d.motivo.strip():
        raise ErrorNegocio("MOTIVO", "Debe indicar el motivo de la reapertura.")
    p.estado, p.estado_kilos, p.kilos_definitivos = "ABIERTO", "PROVISORIO", None
    p.cerrado_en = p.cerrado_por = p.modo_cierre = p.cerrado_sincronizado = None
    auditar(db, ctx, "proceso", p.id, "REABRIR", motivo=d.motivo)
    return proceso_dict(db, p, ctx, True)


@router.post("/procesos/{id_}/anular")
def anular(id_: int, d: Motivo, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:cerrar"))):
    p = obtener_proceso(db, ctx, id_)
    if p.estado in ("CERRADO", "ANULADO"):
        raise ErrorNegocio("ESTADO", f"El proceso esta {p.estado}.", 409)
    if costeo.costo_proceso(db, p.id) != 0 or db.scalar(select(func.coalesce(func.sum(MovimientoInventario.cantidad), 0)).where(
            MovimientoInventario.proceso_id == p.id)) != 0:
        raise ErrorNegocio("CON_CONSUMOS", "El proceso tiene consumos vigentes: anulelos antes de anular el proceso.", 409)
    p.estado = "ANULADO"
    for res in db.scalars(select(ReservaStock).where(ReservaStock.proceso_id == p.id, ReservaStock.estado == "ACTIVA")).unique():
        res.estado, res.fecha_cierre, res.cerrada_por = "LIBERADA", ahora(), ctx.usuario.id
    auditar(db, ctx, "proceso", p.id, "ANULAR", motivo=d.motivo)
    return proceso_dict(db, p, ctx, True)


@router.get("/procesos/{id_}/consumos")
def consumos(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    """Consumos asociados al proceso, con existencia QR, lote, costo, usuario, bodega y ubicacion."""
    from .inventario import movimiento_dict
    obtener_proceso(db, ctx, id_)
    filas = db.scalars(select(MovimientoInventario).where(MovimientoInventario.proceso_id == id_)
                       .order_by(MovimientoInventario.id.desc())).unique().all()
    salida = []
    for m in filas:
        d = movimiento_dict(db, m, True)
        d["ubicacion"] = m.existencia.ubicacion.codigo_completo if m.existencia.ubicacion else None
        salida.append(d)
    return ocultar_costos(salida, ctx.ver_costos)


@router.get("/procesos/{id_}/capturas")
def capturas(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    obtener_proceso(db, ctx, id_)
    return [a_dict(c) for c in db.scalars(select(CapturaProceso).where(CapturaProceso.proceso_id == id_)
                                          .order_by(CapturaProceso.id.desc()).limit(50))]


@router.get("/costos")
def analisis_costos(dimension: str = "especie", desde: date | None = None, hasta: date | None = None,
                    temporada_id: int | None = None, especie: str | None = None, productor: str | None = None,
                    proceso_id: int | None = None, bodega_id: int | None = None, familia_id: int | None = None,
                    subfamilia_id: int | None = None, producto_id: int | None = None, db: Session = Depends(get_db),
                    ctx: Contexto = Depends(requiere("costos:ver"))):
    """Costeo multidimensional: por proceso, especie, productor, variedad, temporada, semana, mes, producto, familia, bodega..."""
    if dimension not in costeo.DIMENSIONES:
        raise ErrorNegocio("DIMENSION", f"Dimension no valida. Opciones: {', '.join(costeo.DIMENSIONES)}")
    return costeo.analisis(db, ctx.empresa_id, dimension, desde=desde, hasta=hasta, temporada_id=temporada_id,
                           especie=especie, productor=productor, proceso_id=proceso_id, bodega_id=bodega_id,
                           familia_id=familia_id, subfamilia_id=subfamilia_id, producto_id=producto_id,
                           bodegas=ctx.bodegas, familias=ctx.familias)


__all__ = ["router", "obtener_proceso", "proceso_dict", "TipoMovimiento", "CAMPOS_NUMERICOS"]
