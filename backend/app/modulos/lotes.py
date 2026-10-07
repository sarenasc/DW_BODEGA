"""Creador de lotes: plantillas versionadas, vista previa, validacion, activacion; consulta y estado de lotes."""
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.crud import guardar, paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict, ahora, dec
from app.modelos import (ESTADOS_LOTE, MODOS_LOTE, MOMENTOS_LOTE, REINICIOS, Existencia, Familia, HistorialEstadoLote,
                         Lote, PlantillaLote, Producto, SegmentoPlantillaLote, Subfamilia, VersionPlantillaLote)
from app.servicios.lotes import (DIMENSIONES_ALCANCE, FORMATOS_FECHA, FORMATOS_FECHA_HORA, TIPOS_SEGMENTO, ContextoLote,
                                 cambiar_estado_lote, clave_alcance, renderizar, validar_plantilla, version_vigente)

router = APIRouter(prefix="/api", tags=["Lotes"])
VER, ADM = "lotes:ver", "lotes:administrar"


class Segmento(BaseModel):
    tipo: str
    configuracion: dict = Field(default_factory=dict)


class PlantillaEntrada(BaseModel):
    codigo: str | None = None
    nombre: str | None = None
    descripcion: str | None = None
    modo: str | None = None
    momento_creacion: str | None = None
    segmentos: list[Segmento] | None = None
    alcance: list[str] | None = None
    reinicio: str | None = None


def _version(v: VersionPlantillaLote) -> dict:
    return a_dict(v, segmentos=[{"tipo": s.tipo, "configuracion": s.configuracion or {}} for s in v.segmentos])


def _plantilla(db: Session, p: PlantillaLote) -> dict:
    vig = version_vigente(p)
    ultima = p.versiones[-1] if p.versiones else None
    asignada = {
        "familias": [f.nombre for f in db.scalars(select(Familia).where(Familia.plantilla_lote_id == p.id))],
        "subfamilias": [s.nombre for s in db.scalars(select(Subfamilia).where(Subfamilia.plantilla_lote_id == p.id)).unique()],
        "productos": [x.nombre for x in db.scalars(select(Producto).where(Producto.plantilla_lote_id == p.id)).unique()],
    }
    return a_dict(p, versiones=[_version(v) for v in p.versiones], version_vigente=vig.version if vig else None,
                  borrador=_version(ultima) if ultima and ultima.estado == "BORRADOR" else None,
                  vigente=_version(vig) if vig else None, asignada_a=asignada)


def _obtener(db: Session, ctx: Contexto, id_: int) -> PlantillaLote:
    p = db.get(PlantillaLote, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Plantilla de lote")
    return p


def _validar_enums(d: PlantillaEntrada) -> None:
    if d.modo and d.modo not in MODOS_LOTE:
        raise ErrorNegocio("MODO", f"Modo no valido. Opciones: {', '.join(MODOS_LOTE)}")
    if d.momento_creacion and d.momento_creacion not in MOMENTOS_LOTE:
        raise ErrorNegocio("MOMENTO", f"Momento no valido. Opciones: {', '.join(MOMENTOS_LOTE)}")
    if d.reinicio and d.reinicio not in REINICIOS:
        raise ErrorNegocio("REINICIO", f"Reinicio no valido. Opciones: {', '.join(REINICIOS)}")


def _escribir_borrador(db: Session, p: PlantillaLote, d: PlantillaEntrada) -> None:
    """Editar nunca toca una version vigente: se trabaja sobre un borrador (nuevo si hace falta)."""
    if d.segmentos is None and d.alcance is None and d.reinicio is None:
        return
    ultima = p.versiones[-1] if p.versiones else None
    if ultima is None or ultima.estado != "BORRADOR":
        nueva = VersionPlantillaLote(plantilla_id=p.id, version=(ultima.version + 1) if ultima else 1,
                                     alcance=list(ultima.alcance) if ultima else [], reinicio=ultima.reinicio if ultima else "NUNCA",
                                     epoca=ultima.epoca if ultima else 0)
        if ultima:
            nueva.segmentos = [SegmentoPlantillaLote(posicion=s.posicion, tipo=s.tipo, configuracion=dict(s.configuracion or {}))
                               for s in ultima.segmentos]
        p.versiones.append(nueva)
        ultima = nueva
    if d.alcance is not None:
        ultima.alcance = [a.upper() for a in d.alcance]
    if d.reinicio is not None:
        ultima.reinicio = d.reinicio
    if d.segmentos is not None:
        ultima.segmentos = [SegmentoPlantillaLote(posicion=i, tipo=s.tipo.upper(), configuracion=s.configuracion)
                            for i, s in enumerate(d.segmentos)]
    db.flush()


@router.get("/plantillas-lotes/opciones")
def opciones(_: Contexto = Depends(requiere(VER))):
    return {"tipos_segmento": TIPOS_SEGMENTO, "dimensiones_alcance": DIMENSIONES_ALCANCE, "reinicios": REINICIOS,
            "modos": MODOS_LOTE, "momentos": MOMENTOS_LOTE, "formatos_fecha": list(FORMATOS_FECHA),
            "formatos_fecha_hora": list(FORMATOS_FECHA_HORA), "formatos_mes": ["NUMERO", "ABREV", "NOMBRE"]}


@router.get("/plantillas-lotes")
def listar(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    return [_plantilla(db, p) for p in db.scalars(select(PlantillaLote).where(PlantillaLote.empresa_id == ctx.empresa_id)
                                                  .order_by(PlantillaLote.nombre)).unique()]


@router.get("/plantillas-lotes/{id_}")
def ver(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    return _plantilla(db, _obtener(db, ctx, id_))


@router.post("/plantillas-lotes", status_code=201)
def crear(d: PlantillaEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    if not d.codigo or not d.nombre:
        raise ErrorNegocio("DATOS", "Codigo y nombre son obligatorios.")
    _validar_enums(d)
    p = PlantillaLote(empresa_id=ctx.empresa_id, codigo=d.codigo.strip().upper(), nombre=d.nombre, descripcion=d.descripcion,
                      modo=d.modo or "AUTOMATICO", momento_creacion=d.momento_creacion or "AL_CONFIRMAR_RECEPCION")
    guardar(db, p)
    _escribir_borrador(db, p, d if d.segmentos is not None else d.model_copy(update={"segmentos": []}))
    auditar(db, ctx, "plantilla_lote", p.id, "CREAR", nuevo={"codigo": p.codigo})
    db.refresh(p)
    return _plantilla(db, p)


@router.put("/plantillas-lotes/{id_}")
def editar(id_: int, d: PlantillaEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    p = _obtener(db, ctx, id_)
    _validar_enums(d)
    for campo in ("nombre", "descripcion", "modo", "momento_creacion"):
        if getattr(d, campo) is not None:
            setattr(p, campo, getattr(d, campo))
    _escribir_borrador(db, p, d)
    auditar(db, ctx, "plantilla_lote", p.id, "EDITAR", nuevo=d.model_dump(exclude_unset=True))
    db.refresh(p)
    return _plantilla(db, p)


class VistaPrevia(BaseModel):
    modo: str = "AUTOMATICO"
    segmentos: list[Segmento]
    alcance: list[str] = Field(default_factory=list)
    reinicio: str = "NUNCA"


@router.post("/plantillas-lotes/vista-previa")
def vista_previa(d: VistaPrevia, _: Contexto = Depends(requiere(VER))):
    """Usa el mismo motor que la generacion real: lo que se ve es lo que se generara."""
    segmentos = [s.model_dump() for s in d.segmentos]
    resultado = validar_plantilla(d.modo, segmentos, [a.upper() for a in d.alcance], d.reinicio)
    ctx = ContextoLote(fecha=ahora(), producto="FUNGX", familia="FITO", subfamilia="FUNG", bodega="FIT", empresa="EMP",
                       temporada="2026-2027", usuario="usuario", turno="A", proceso="PROC0001",
                       manuales={(s.configuracion.get("clave") or s.configuracion.get("etiqueta") or "manual"): "X1"
                                 for s in d.segmentos if s.tipo == "MANUAL"})
    try:
        resultado["vista_previa"] = renderizar(segmentos, ctx, 1) if segmentos else ""
    except ErrorNegocio as e:
        resultado["vista_previa"] = ""
        resultado["errores"].append(e.mensaje)
    resultado["clave_contador"] = clave_alcance([a.upper() for a in d.alcance], d.reinicio, 0, ctx)
    return resultado


@router.post("/plantillas-lotes/{id_}/activar")
def activar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """Publica el borrador como nueva version vigente. Los lotes historicos conservan su version."""
    p = _obtener(db, ctx, id_)
    ultima = p.versiones[-1] if p.versiones else None
    if ultima is None:
        raise ErrorNegocio("SIN_VERSION", "La plantilla no tiene formato definido.")
    if ultima.estado == "BORRADOR":
        segmentos = [{"tipo": s.tipo, "configuracion": s.configuracion or {}} for s in ultima.segmentos]
        r = validar_plantilla(p.modo, segmentos, ultima.alcance, ultima.reinicio)
        if r["errores"]:
            raise ErrorNegocio("PLANTILLA_INVALIDA", "La plantilla no puede activarse: " + " ".join(r["errores"]), datos=r)
        anterior = version_vigente(p)
        if anterior:
            anterior.estado, anterior.vigente_hasta = "RETIRADA", ahora()
        ultima.estado, ultima.vigente_desde = "VIGENTE", ahora()
    p.activa = True
    auditar(db, ctx, "plantilla_lote", p.id, "ACTIVAR", nuevo={"version": ultima.version})
    db.flush()
    return _plantilla(db, p)


@router.post("/plantillas-lotes/{id_}/desactivar")
def desactivar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    p = _obtener(db, ctx, id_)
    p.activa = False
    auditar(db, ctx, "plantilla_lote", p.id, "DESACTIVAR")
    return _plantilla(db, p)


@router.post("/plantillas-lotes/{id_}/reiniciar-correlativo")
def reiniciar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """Reinicio manual: cambia la epoca del contador. Requiere que el codigo siga siendo unico."""
    p = _obtener(db, ctx, id_)
    v = version_vigente(p)
    if not v:
        raise ErrorNegocio("SIN_VERSION", "La plantilla no tiene una version vigente.")
    if v.reinicio != "MANUAL":
        raise ErrorNegocio("REINICIO", "Solo las plantillas con reinicio MANUAL admiten esta accion.")
    v.epoca += 1
    auditar(db, ctx, "plantilla_lote", p.id, "REINICIAR_CORRELATIVO", nuevo={"epoca": v.epoca})
    return {"ok": True, "epoca": v.epoca}


# ---------------------------------------------------------------- lotes

def lote_dict(db: Session, lote: Lote, con_stock: bool = True) -> dict:
    d = a_dict(lote, producto=lote.producto.nombre, producto_codigo=lote.producto.codigo,
               unidad=lote.producto.unidad_base.codigo)
    if con_stock:
        fila = db.execute(select(func.coalesce(func.sum(Existencia.cantidad_fisica), 0),
                                 func.coalesce(func.sum(Existencia.cantidad_fisica * Existencia.costo_unitario), 0),
                                 func.count(Existencia.id)).where(Existencia.lote_id == lote.id)).one()
        d.update(cantidad_disponible=float(dec(fila[0])), valor_disponible=float(dec(fila[1])), existencias=fila[2])
        # Cantidad y valor iniciales: solo existencias nacidas de un ingreso (las hijas de traslados duplicarian).
        ini = db.execute(select(func.coalesce(func.sum(Existencia.cantidad_inicial), 0),
                                func.coalesce(func.sum(Existencia.cantidad_inicial * Existencia.costo_unitario), 0))
                         .where(Existencia.lote_id == lote.id, Existencia.existencia_padre_id.is_(None))).one()
        d.update(cantidad_inicial=float(dec(ini[0])), valor_inicial=float(dec(ini[1])))
    return d


@router.get("/lotes")
def listar_lotes(q: str | None = None, estado: str | None = None, producto_id: int | None = None,
                 vence_antes: date | None = None, con_stock: bool | None = None, pagina: int = Query(1, ge=1),
                 tam: int = Query(50, le=500), db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    from app.core.util import ocultar_costos
    c = select(Lote).join(Producto, Lote.producto_id == Producto.id).where(Lote.empresa_id == ctx.empresa_id)
    if ctx.familias is not None:
        c = c.join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).where(Subfamilia.familia_id.in_(ctx.familias))
    if q:
        patron = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Lote.codigo).like(patron), func.lower(Producto.nombre).like(patron),
                        func.lower(Lote.referencia_externa).like(patron)))
    if estado:
        c = c.where(Lote.estado == estado)
    if producto_id:
        c = c.where(Lote.producto_id == producto_id)
    if vence_antes:
        c = c.where(Lote.fecha_vencimiento <= vence_antes)
    if con_stock:
        c = c.where(Lote.id.in_(select(Existencia.lote_id).where(Existencia.cantidad_fisica > 0)))
    r = paginar(db, c.order_by(Lote.id.desc()), pagina, tam, lambda lote: lote_dict(db, lote))
    return ocultar_costos(r, ctx.ver_costos)


@router.get("/lotes/{id_}")
def ver_lote(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    from app.core.util import ocultar_costos
    lote = db.get(Lote, id_)
    if not lote or lote.empresa_id != ctx.empresa_id:
        raise no_encontrado("Lote")
    d = lote_dict(db, lote)
    d["historial"] = [a_dict(h) for h in db.scalars(select(HistorialEstadoLote).where(HistorialEstadoLote.lote_id == id_)
                                                    .order_by(HistorialEstadoLote.id))]
    d["sublotes"] = [{"id": s.id, "codigo": s.codigo, "estado": s.estado}
                     for s in db.scalars(select(Lote).where(Lote.lote_padre_id == id_)).unique()]
    return ocultar_costos(d, ctx.ver_costos)


class CambioEstado(BaseModel):
    estado: str
    motivo: str


@router.post("/lotes/{id_}/estado")
def cambiar_estado(id_: int, d: CambioEstado, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("lotes:bloquear"))):
    lote = db.get(Lote, id_)
    if not lote or lote.empresa_id != ctx.empresa_id:
        raise no_encontrado("Lote")
    if d.estado not in ESTADOS_LOTE:
        raise ErrorNegocio("ESTADO", f"Estado no valido. Opciones: {', '.join(ESTADOS_LOTE)}")
    if d.estado in ("AGOTADO", "ANULADO"):
        raise ErrorNegocio("ESTADO", "Ese estado lo asigna el sistema segun el stock y las anulaciones.")
    if lote.estado == "ANULADO":
        raise ErrorNegocio("ESTADO", "Un lote anulado no cambia de estado.")
    if not d.motivo.strip():
        raise ErrorNegocio("MOTIVO", "Debe indicar el motivo.")
    antes = lote.estado
    cambiar_estado_lote(db, ctx, lote, d.estado, d.motivo)
    auditar(db, ctx, "lote", lote.id, "CAMBIAR_ESTADO", anterior={"estado": antes}, nuevo={"estado": d.estado}, motivo=d.motivo)
    return lote_dict(db, lote)


class EdicionLote(BaseModel):
    fecha_vencimiento: date | None = None
    fecha_fabricacion: date | None = None
    referencia_externa: str | None = None
    observaciones: str | None = None


@router.put("/lotes/{id_}")
def editar_lote(id_: int, d: EdicionLote, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """El codigo del lote es inmutable. Solo se corrigen datos descriptivos, con auditoria."""
    lote = db.get(Lote, id_)
    if not lote or lote.empresa_id != ctx.empresa_id:
        raise no_encontrado("Lote")
    antes = a_dict(lote)
    for k, v in d.model_dump(exclude_unset=True).items():
        setattr(lote, k, v)
    auditar(db, ctx, "lote", lote.id, "EDITAR", anterior=antes, nuevo=lote)
    return lote_dict(db, lote)


__all__ = ["router", "lote_dict", "datetime"]
