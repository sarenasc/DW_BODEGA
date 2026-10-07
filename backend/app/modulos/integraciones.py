"""Integraciones con la base productiva: conexiones (solo lectura), fuentes, mapeo visual e importacion de procesos."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.crud import guardar, paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.seguridad import cifrar
from app.core.util import a_dict, ahora, json_valor
from app.modelos import (CAMPOS_PROCESO, ConexionIntegracion, EjecucionSincronizacion, FuenteIntegracion,
                         MapeoIntegracion, Proceso, Usuario)
from app.servicios import integracion as svc

router = APIRouter(prefix="/api/integraciones", tags=["Integraciones"])
ADM = "integraciones:administrar"
MOTORES = ("sqlserver", "postgresql", "mysql", "demo")
TRANSFORMACIONES = ("RECORTAR", "MAYUSCULAS", "NUMERO", "FECHA")
POLITICAS = ("SIEMPRE", "SOLO_IMPORTAR", "MANUAL")


# ---------------------------------------------------------------- conexiones

class ConexionEntrada(BaseModel):
    nombre: str | None = None
    motor: str | None = None
    servidor: str | None = None
    puerto: int | None = None
    base_datos: str | None = None
    usuario: str | None = None
    clave: str | None = None  # se cifra al guardar; nunca se devuelve
    parametros: dict[str, str] | None = None
    activa: bool | None = None


def _conexion(c: ConexionIntegracion) -> dict:
    return a_dict(c, excluir=("clave_cifrada",), tiene_clave=bool(c.clave_cifrada))


def _obtener_conexion(db: Session, ctx: Contexto, id_: int) -> ConexionIntegracion:
    c = db.get(ConexionIntegracion, id_)
    if not c or c.empresa_id != ctx.empresa_id:
        raise no_encontrado("Conexion")
    return c


def _aplicar_conexion(c: ConexionIntegracion, d: ConexionEntrada) -> None:
    if d.motor is not None and d.motor not in MOTORES:
        raise ErrorNegocio("MOTOR", f"Motor no soportado. Opciones: {', '.join(MOTORES)}")
    for campo in ("nombre", "motor", "servidor", "puerto", "base_datos", "usuario", "parametros", "activa"):
        if campo in d.model_fields_set:
            setattr(c, campo, getattr(d, campo))
    if d.clave:
        c.clave_cifrada = cifrar(d.clave)


@router.get("/opciones")
def opciones(_: Contexto = Depends(requiere(ADM))):
    return {"motores": MOTORES, "transformaciones": TRANSFORMACIONES, "politicas": POLITICAS, "campos_proceso": CAMPOS_PROCESO}


@router.get("/conexiones")
def listar_conexiones(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    return [_conexion(c) for c in db.scalars(select(ConexionIntegracion).where(ConexionIntegracion.empresa_id == ctx.empresa_id)
                                             .order_by(ConexionIntegracion.nombre))]


@router.post("/conexiones", status_code=201)
def crear_conexion(d: ConexionEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    if not d.nombre or not d.motor:
        raise ErrorNegocio("DATOS", "Nombre y motor son obligatorios.")
    c = ConexionIntegracion(empresa_id=ctx.empresa_id, nombre=d.nombre, motor=d.motor)
    _aplicar_conexion(c, d)
    guardar(db, c)
    auditar(db, ctx, "conexion_integracion", c.id, "CREAR", nuevo=_conexion(c))
    return _conexion(c)


@router.put("/conexiones/{id_}")
def editar_conexion(id_: int, d: ConexionEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    c = _obtener_conexion(db, ctx, id_)
    antes = _conexion(c)
    _aplicar_conexion(c, d)
    guardar(db, c)
    auditar(db, ctx, "conexion_integracion", c.id, "EDITAR", anterior=antes, nuevo=_conexion(c))
    return _conexion(c)


@router.delete("/conexiones/{id_}")
def eliminar_conexion(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    c = _obtener_conexion(db, ctx, id_)
    if db.scalar(select(Proceso.id).join(FuenteIntegracion, Proceso.fuente_id == FuenteIntegracion.id)
                 .where(FuenteIntegracion.conexion_id == c.id).limit(1)):
        c.activa = False  # hay procesos importados: se conserva la referencia
    else:
        db.delete(c)
    auditar(db, ctx, "conexion_integracion", id_, "ELIMINAR")
    return {"ok": True}


@router.post("/conexiones/{id_}/probar")
def probar_conexion(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    c = _obtener_conexion(db, ctx, id_)
    try:
        svc.probar_conexion(c)
        return {"ok": True, "mensaje": "Conexion correcta."}
    except ErrorNegocio as e:
        return {"ok": False, "mensaje": e.mensaje}


# ---------------------------------------------------------------- fuentes y mapeo

class MapeoEntrada(BaseModel):
    columna_externa: str
    campo_interno: str
    transformacion: str | None = None
    factor: float | None = None
    politica_actualizacion: str = "SIEMPRE"


class FuenteEntrada(BaseModel):
    conexion_id: int | None = None
    nombre: str | None = None
    tipo: str | None = None
    origen: str | None = None
    columna_id: str | None = None
    columna_fecha: str | None = None
    intervalo_minutos: int | None = Field(default=None, ge=0, le=1440)
    guardar_no_mapeadas: bool | None = None
    activa: bool | None = None
    mapeos: list[MapeoEntrada] | None = None


def _fuente(f: FuenteIntegracion) -> dict:
    return a_dict(f, conexion=f.conexion.nombre, motor=f.conexion.motor,
                  mapeos=[a_dict(m, excluir=("fuente_id",)) for m in sorted(f.mapeos, key=lambda m: m.id or 0)])


def _obtener_fuente(db: Session, ctx: Contexto, id_: int) -> FuenteIntegracion:
    f = db.get(FuenteIntegracion, id_)
    if not f or f.conexion.empresa_id != ctx.empresa_id:
        raise no_encontrado("Fuente")
    return f


def _aplicar_fuente(db: Session, ctx: Contexto, f: FuenteIntegracion, d: FuenteEntrada) -> None:
    for campo in ("nombre", "tipo", "origen", "columna_id", "columna_fecha", "intervalo_minutos", "guardar_no_mapeadas", "activa"):
        if campo in d.model_fields_set and (getattr(d, campo) is not None or campo in ("columna_fecha", "intervalo_minutos")):
            setattr(f, campo, getattr(d, campo))
    if d.conexion_id:
        f.conexion = _obtener_conexion(db, ctx, d.conexion_id)
        f.conexion_id = d.conexion_id
    f.tipo = (f.tipo or "CONSULTA").upper()
    if f.tipo not in ("VISTA", "CONSULTA"):
        raise ErrorNegocio("TIPO", "El tipo debe ser VISTA o CONSULTA.")
    f.origen = svc.validar_origen(f.tipo, f.origen)
    svc.validar_columna(f.columna_id)
    if f.columna_fecha:
        svc.validar_columna(f.columna_fecha)
    if d.mapeos is not None:
        vistos = set()
        nuevos = []
        for m in d.mapeos:
            campo = m.campo_interno.strip()
            if campo not in CAMPOS_PROCESO and not (campo.startswith("extra.") and len(campo) > 6):
                raise ErrorNegocio("MAPEO", f"Campo interno desconocido: {campo}. Use un campo del proceso o extra.<clave>.")
            if campo in vistos:
                raise ErrorNegocio("MAPEO", f"El campo interno {campo} esta mapeado mas de una vez.")
            if m.transformacion and m.transformacion not in TRANSFORMACIONES:
                raise ErrorNegocio("MAPEO", f"Transformacion no valida: {m.transformacion}")
            if m.politica_actualizacion not in POLITICAS:
                raise ErrorNegocio("MAPEO", f"Politica no valida: {m.politica_actualizacion}")
            vistos.add(campo)
            nuevos.append(MapeoIntegracion(columna_externa=svc.validar_columna(m.columna_externa.strip()), campo_interno=campo,
                                           transformacion=m.transformacion, factor=m.factor,
                                           politica_actualizacion=m.politica_actualizacion))
        f.mapeos.clear()
        db.flush()
        f.mapeos.extend(nuevos)


@router.get("/fuentes")
def listar_fuentes(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:ver"))):
    filas = db.scalars(select(FuenteIntegracion).join(ConexionIntegracion).where(ConexionIntegracion.empresa_id == ctx.empresa_id)
                       .order_by(FuenteIntegracion.nombre)).unique()
    if not ctx.puede(ADM):  # quien solo importa procesos ve el nombre, no la consulta
        return [{"id": f.id, "nombre": f.nombre, "activa": f.activa} for f in filas]
    return [_fuente(f) for f in filas]


@router.post("/fuentes", status_code=201)
def crear_fuente(d: FuenteEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    if not d.conexion_id or not d.nombre or not d.origen or not d.columna_id:
        raise ErrorNegocio("DATOS", "Conexion, nombre, vista o consulta y columna identificadora son obligatorios.")
    f = FuenteIntegracion(nombre=d.nombre, origen=d.origen, columna_id=d.columna_id, conexion_id=d.conexion_id)
    f.conexion = _obtener_conexion(db, ctx, d.conexion_id)
    db.add(f)
    _aplicar_fuente(db, ctx, f, d)
    guardar(db, f)
    auditar(db, ctx, "fuente_integracion", f.id, "CREAR", nuevo={"nombre": f.nombre})
    return _fuente(f)


@router.put("/fuentes/{id_}")
def editar_fuente(id_: int, d: FuenteEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    f = _obtener_fuente(db, ctx, id_)
    _aplicar_fuente(db, ctx, f, d)
    guardar(db, f)
    auditar(db, ctx, "fuente_integracion", f.id, "EDITAR", nuevo=d.model_dump(exclude_unset=True, exclude={"mapeos"}))
    db.refresh(f)
    return _fuente(f)


@router.delete("/fuentes/{id_}")
def eliminar_fuente(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    f = _obtener_fuente(db, ctx, id_)
    if db.scalar(select(Proceso.id).where(Proceso.fuente_id == f.id).limit(1)):
        f.activa = False
    else:
        db.delete(f)
    auditar(db, ctx, "fuente_integracion", id_, "ELIMINAR")
    return {"ok": True}


@router.get("/fuentes/{id_}/columnas")
def columnas(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """Columnas reales del origen, para ofrecerlas en el mapeo visual. Nada se asume de la base productiva."""
    return {"columnas": svc.columnas_origen(_obtener_fuente(db, ctx, id_))}


@router.get("/fuentes/{id_}/vista-previa")
def vista_previa(id_: int, limite: int = Query(5, le=50), db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """Filas de ejemplo: crudas y ya transformadas por el mapeo."""
    f = _obtener_fuente(db, ctx, id_)
    filas = svc.listar_origen(f, limite=limite)
    salida = []
    for fila in filas:
        try:
            campos, extra, _ = svc.mapear_fila(f, fila)
            salida.append({"origen": {k: json_valor(v) if not isinstance(v, (bytes, bytearray)) else None for k, v in fila.items()},
                           "mapeado": {k: json_valor(v) for k, v in campos.items()}, "adicionales": extra, "error": None})
        except ErrorNegocio as e:
            salida.append({"origen": {k: str(v) for k, v in fila.items()}, "mapeado": {}, "adicionales": {}, "error": e.mensaje})
    return {"columnas": list(filas[0].keys()) if filas else [], "filas": salida}


@router.get("/fuentes/{id_}/disponibles")
def disponibles(id_: int, desde: date | None = None, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:abrir"))):
    """Procesos existentes en produccion, indicando cuales ya fueron importados."""
    f = _obtener_fuente(db, ctx, id_)
    filas = svc.listar_origen(f, desde=desde)
    importados = dict(db.execute(select(Proceso.id_externo, Proceso.id).where(Proceso.fuente_id == f.id)).all())
    por_minuscula = lambda fila: {k.lower(): k for k in fila}  # noqa: E731
    salida = []
    for fila in filas:
        real = por_minuscula(fila).get(f.columna_id.lower())
        if real is None:
            raise ErrorNegocio("COLUMNA", f"La columna identificadora {f.columna_id} no existe en el origen.")
        id_ext = str(fila[real]).strip()
        try:
            campos, _, _ = svc.mapear_fila(f, fila)
        except ErrorNegocio:
            campos = {}
        salida.append({"id_externo": id_ext, "importado": id_ext in importados, "proceso_id": importados.get(id_ext),
                       "datos": {k: json_valor(v) for k, v in campos.items()}})
    return salida


class Importacion(BaseModel):
    ids: list[str]
    abrir: bool = False


@router.post("/fuentes/{id_}/importar")
def importar(id_: int, d: Importacion, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:abrir"))):
    f = _obtener_fuente(db, ctx, id_)
    if not f.activa:
        raise ErrorNegocio("FUENTE_INACTIVA", "La fuente esta inactiva.")
    creados, omitidos = [], []
    for id_ext in d.ids[:100]:
        try:
            with db.begin_nested():
                p = svc.importar_proceso(db, ctx, f, id_ext, ctx.empresa_id)
                if d.abrir:
                    p.estado, p.abierto_en, p.abierto_por = "ABIERTO", ahora(), ctx.usuario.id
                auditar(db, ctx, "proceso", p.id, "IMPORTAR", nuevo={"id_externo": id_ext, "codigo": p.codigo})
                creados.append({"id": p.id, "codigo": p.codigo, "id_externo": id_ext})
        except ErrorNegocio as e:
            omitidos.append({"id_externo": id_ext, "motivo": e.mensaje})
    return {"importados": creados, "omitidos": omitidos}


@router.get("/ejecuciones")
def ejecuciones(proceso_id: int | None = None, estado: str | None = None, pagina: int = 1, tam: int = Query(50, le=200),
                db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("procesos:ver"))):
    c = select(EjecucionSincronizacion).join(FuenteIntegracion, EjecucionSincronizacion.fuente_id == FuenteIntegracion.id) \
        .join(ConexionIntegracion).where(ConexionIntegracion.empresa_id == ctx.empresa_id)
    if proceso_id:
        c = c.where(EjecucionSincronizacion.proceso_id == proceso_id)
    if estado:
        c = c.where(EjecucionSincronizacion.estado == estado)
    nombres = dict(db.execute(select(Usuario.id, Usuario.nombre)).all())
    return paginar(db, c.order_by(EjecucionSincronizacion.id.desc()), pagina, tam, lambda e: a_dict(e, usuario=nombres.get(e.usuario_id)))
