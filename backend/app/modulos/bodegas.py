"""Bodegas, ubicaciones jerarquicas configurables y plano 2D / visor 3D."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.crud import crear_crud, guardar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict, dia_local, hoy, ocultar_costos
from app.modelos import Bodega, ElementoPlano, Existencia, Lote, Producto, Ubicacion

router = APIRouter(prefix="/api", tags=["Bodegas"])
VER, ADM = "bodegas:ver", "bodegas:administrar"


def _alcance(q, ctx: Contexto):
    return q if ctx.bodegas is None else q.where(Bodega.id.in_(ctx.bodegas))


def _val_bodega(db, ctx, b: Bodega, antes):
    b.codigo = b.codigo.strip().upper()
    if antes and antes["codigo"] != b.codigo and db.scalar(select(Ubicacion.id).where(Ubicacion.bodega_id == b.id).limit(1)):
        raise ErrorNegocio("CODIGO_EN_USO", "No se puede cambiar el codigo: ya existen ubicaciones con ese prefijo.")


_obtener_bodega = crear_crud(router, "/bodegas", Bodega, entidad="bodega", ver=VER, editar=ADM, validar=_val_bodega,
                             alcance=_alcance)


def bodega_de(db: Session, ctx: Contexto, id_: int) -> Bodega:
    b = db.get(Bodega, id_)
    if not b or b.empresa_id != ctx.empresa_id:
        raise no_encontrado("Bodega")
    ctx.exigir_bodega(b.id)
    return b


# ---- ubicaciones ----

class UbicacionEntrada(BaseModel):
    bodega_id: int | None = None
    padre_id: int | None = None
    tipo: str | None = None
    codigo: str | None = None
    nombre: str | None = None
    capacidad: Decimal | None = None
    almacenable: bool | None = None
    activo: bool | None = None
    orden: int | None = None


def _codigo_completo(db: Session, bodega: Bodega, padre_id: int | None, codigo: str) -> tuple[str, int]:
    if padre_id:
        padre = db.get(Ubicacion, padre_id)
        if not padre or padre.bodega_id != bodega.id:
            raise ErrorNegocio("PADRE", "La ubicacion padre no pertenece a la bodega.")
        return f"{padre.codigo_completo}-{codigo}", padre.nivel + 1
    return f"{bodega.codigo}-{codigo}", 0


def crear_ubicacion(db: Session, bodega: Bodega, codigo: str, tipo: str = "UBICACION", padre_id: int | None = None,
                    nombre: str | None = None, capacidad=None, almacenable: bool = True, orden: int = 0) -> Ubicacion:
    codigo = codigo.strip().upper()
    if not codigo or "-" in codigo:
        raise ErrorNegocio("CODIGO", "El codigo de ubicacion es obligatorio y no puede contener guiones.")
    completo, nivel = _codigo_completo(db, bodega, padre_id, codigo)
    u = Ubicacion(bodega_id=bodega.id, padre_id=padre_id, tipo=tipo.upper(), nivel=nivel, orden=orden, codigo=codigo,
                  codigo_completo=completo, nombre=nombre, capacidad=capacidad, almacenable=almacenable)
    guardar(db, u)
    return u


@router.get("/ubicaciones")
def listar_ubicaciones(bodega_id: int, almacenable: bool | None = None, activo: bool | None = True, q: str | None = None,
                       db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    bodega_de(db, ctx, bodega_id)
    c = select(Ubicacion).where(Ubicacion.bodega_id == bodega_id)
    if almacenable is not None:
        c = c.where(Ubicacion.almacenable == almacenable)
    if activo is not None:
        c = c.where(Ubicacion.activo == activo)
    if q:
        c = c.where(func.lower(Ubicacion.codigo_completo).like(f"%{q.lower()}%"))
    return [a_dict(u) for u in db.scalars(c.order_by(Ubicacion.codigo_completo))]


@router.post("/ubicaciones", status_code=201)
def nueva_ubicacion(d: UbicacionEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    if not d.bodega_id or not d.codigo:
        raise ErrorNegocio("DATOS", "Bodega y codigo son obligatorios.")
    b = bodega_de(db, ctx, d.bodega_id)
    u = crear_ubicacion(db, b, d.codigo, d.tipo or "UBICACION", d.padre_id, d.nombre, d.capacidad,
                        True if d.almacenable is None else d.almacenable, d.orden or 0)
    auditar(db, ctx, "ubicacion", u.id, "CREAR", nuevo=u)
    return a_dict(u)


@router.put("/ubicaciones/{id_}")
def editar_ubicacion(id_: int, d: UbicacionEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    u = db.get(Ubicacion, id_)
    if not u:
        raise no_encontrado("Ubicacion")
    bodega_de(db, ctx, u.bodega_id)
    antes = a_dict(u)
    for campo in ("nombre", "capacidad", "almacenable", "tipo", "orden"):
        v = getattr(d, campo)
        if v is not None:
            setattr(u, campo, v)
    if d.activo is not None and d.activo != u.activo:
        if not d.activo and _con_stock(db, [u.id] + _descendientes(db, u.id)):
            raise ErrorNegocio("CON_STOCK", "La ubicacion (o sus posiciones) tiene stock: trasladelo antes de desactivarla.", 409)
        u.activo = d.activo
    auditar(db, ctx, "ubicacion", u.id, "EDITAR", anterior=antes, nuevo=u)
    return a_dict(u)


def _descendientes(db: Session, ubicacion_id: int) -> list[int]:
    todos, frontera = [], [ubicacion_id]
    while frontera:
        hijos = list(db.scalars(select(Ubicacion.id).where(Ubicacion.padre_id.in_(frontera))))
        todos += hijos
        frontera = hijos
    return todos


def _con_stock(db: Session, ids: list[int]) -> bool:
    return bool(ids) and db.scalar(select(Existencia.id).where(
        Existencia.ubicacion_id.in_(ids), Existencia.cantidad_fisica > 0).limit(1)) is not None


class RackEntrada(BaseModel):
    codigo: str
    nombre: str | None = None
    padre_id: int | None = None
    niveles: int = Field(ge=1, le=20)
    posiciones: int = Field(ge=1, le=60)
    prefijo_nivel: str = "N"
    prefijo_posicion: str = "P"
    capacidad_posicion: Decimal | None = None


def generar_rack(db: Session, bodega: Bodega, d: RackEntrada) -> Ubicacion:
    """Crea la jerarquia RACK -> NIVEL -> POSICION. Solo las posiciones almacenan stock."""
    rack = crear_ubicacion(db, bodega, d.codigo, "RACK", d.padre_id, d.nombre or f"Rack {d.codigo}", almacenable=False)
    for n in range(1, d.niveles + 1):
        nivel = crear_ubicacion(db, bodega, f"{d.prefijo_nivel}{n:02d}", "NIVEL", rack.id, almacenable=False, orden=n)
        for p in range(1, d.posiciones + 1):
            crear_ubicacion(db, bodega, f"{d.prefijo_posicion}{p:02d}", "POSICION", nivel.id,
                            capacidad=d.capacidad_posicion, orden=p)
    return rack


@router.post("/bodegas/{id_}/racks", status_code=201)
def nuevo_rack(id_: int, d: RackEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    b = bodega_de(db, ctx, id_)
    rack = generar_rack(db, b, d)
    auditar(db, ctx, "ubicacion", rack.id, "GENERAR_RACK", nuevo={"codigo": rack.codigo_completo, "niveles": d.niveles,
                                                                 "posiciones": d.posiciones})
    return a_dict(rack, ubicaciones_creadas=1 + d.niveles + d.niveles * d.posiciones)


# ---- plano 2D / 3D ----

class ElementoEntrada(BaseModel):
    id: int | None = None
    tipo: str
    nombre: str
    x: Decimal = Decimal(0)
    y: Decimal = Decimal(0)
    ancho: Decimal = Decimal(1)
    fondo: Decimal = Decimal(1)
    alto: Decimal = Decimal(1)
    rotacion: int = 0
    color: str | None = None
    parametros: dict | None = None
    ubicacion_id: int | None = None


class PlanoEntrada(BaseModel):
    largo: Decimal | None = None
    ancho: Decimal | None = None
    alto: Decimal | None = None
    elementos: list[ElementoEntrada]


def _plano(db: Session, bodega: Bodega) -> dict:
    elementos = db.scalars(select(ElementoPlano).where(ElementoPlano.bodega_id == bodega.id).order_by(ElementoPlano.id)).all()
    ubic = db.scalars(select(Ubicacion).where(Ubicacion.bodega_id == bodega.id, Ubicacion.activo.is_(True))
                      .order_by(Ubicacion.nivel, Ubicacion.orden, Ubicacion.codigo)).all()
    return {"bodega": a_dict(bodega), "elementos": [a_dict(e) for e in elementos],
            "ubicaciones": [{"id": u.id, "padre_id": u.padre_id, "tipo": u.tipo, "codigo": u.codigo, "orden": u.orden,
                             "codigo_completo": u.codigo_completo, "almacenable": u.almacenable,
                             "capacidad": float(u.capacidad) if u.capacidad is not None else None} for u in ubic]}


@router.get("/bodegas/{id_}/plano")
def ver_plano(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    return _plano(db, bodega_de(db, ctx, id_))


@router.put("/bodegas/{id_}/plano")
def guardar_plano(id_: int, d: PlanoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADM))):
    """Publica el plano editado. Los racks nuevos generan sus ubicaciones; los eliminados las desactivan."""
    b = bodega_de(db, ctx, id_)
    for campo in ("largo", "ancho", "alto"):
        if getattr(d, campo) is not None:
            setattr(b, campo, getattr(d, campo))
    actuales = {e.id: e for e in db.scalars(select(ElementoPlano).where(ElementoPlano.bodega_id == b.id))}
    conservados = set()
    for e in d.elementos:
        tipo = e.tipo.upper()
        if tipo not in ("RACK", "ZONA", "PISO", "PASILLO", "OBSTACULO"):
            raise ErrorNegocio("TIPO", f"Tipo de elemento no valido: {e.tipo}")
        if b.largo and b.ancho and (e.x < 0 or e.y < 0 or e.x > b.largo or e.y > b.ancho):
            raise ErrorNegocio("FUERA_DE_PLANO", f"El elemento {e.nombre} queda fuera de la bodega.")
        obj = actuales.get(e.id) if e.id else None
        if obj is None:
            obj = ElementoPlano(bodega_id=b.id, tipo=tipo, nombre=e.nombre)
            db.add(obj)
        for campo in ("nombre", "x", "y", "ancho", "fondo", "alto", "rotacion", "color", "parametros"):
            setattr(obj, campo, getattr(e, campo))
        obj.tipo = tipo
        if e.ubicacion_id:
            obj.ubicacion_id = e.ubicacion_id
        params = e.parametros or {}
        if tipo == "RACK" and not obj.ubicacion_id and params.get("niveles") and params.get("posiciones"):
            rack = generar_rack(db, b, RackEntrada(codigo=e.nombre, niveles=params["niveles"],
                                                   posiciones=params["posiciones"], padre_id=params.get("padre_id")))
            obj.ubicacion_id = rack.id
        elif tipo in ("ZONA", "PISO") and not obj.ubicacion_id and params.get("crear_ubicacion", True):
            obj.ubicacion_id = crear_ubicacion(db, b, e.nombre, tipo, nombre=e.nombre).id
        db.flush()
        conservados.add(obj.id)
    for eid, obj in actuales.items():
        if eid in conservados:
            continue
        if obj.ubicacion_id:
            ids = [obj.ubicacion_id] + _descendientes(db, obj.ubicacion_id)
            if _con_stock(db, ids):
                raise ErrorNegocio("CON_STOCK", f"No se puede eliminar {obj.nombre}: tiene stock almacenado.", 409)
            for u in db.scalars(select(Ubicacion).where(Ubicacion.id.in_(ids))):
                u.activo = False  # nunca se borran: pueden tener historia
        db.delete(obj)
    auditar(db, ctx, "bodega", b.id, "PUBLICAR_PLANO", nuevo={"elementos": len(d.elementos)})
    db.flush()
    return _plano(db, b)


@router.get("/bodegas/{id_}/ocupacion")
def ocupacion(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    """Resumen por ubicacion para colorear el visor: cantidad, valor, antiguedad y vencimiento."""
    bodega_de(db, ctx, id_)
    filas = db.execute(
        select(Existencia.ubicacion_id, func.count(Existencia.id), func.sum(Existencia.cantidad_fisica),
               func.sum(Existencia.cantidad_fisica * Existencia.costo_unitario), func.min(Existencia.fecha_ingreso),
               func.min(Lote.fecha_vencimiento))
        .outerjoin(Lote, Existencia.lote_id == Lote.id)
        .where(Existencia.bodega_id == id_, Existencia.cantidad_fisica > 0)
        .group_by(Existencia.ubicacion_id)).all()
    capacidades = dict(db.execute(select(Ubicacion.id, Ubicacion.capacidad).where(Ubicacion.bodega_id == id_)).all())
    hoy_ = hoy()
    salida = []
    for uid, n, cant, valor, ingreso, vence in filas:
        cap = capacidades.get(uid)
        salida.append({
            "ubicacion_id": uid, "existencias": n, "cantidad": float(cant or 0), "valor": float(valor or 0),
            "dias_antiguedad": (hoy_ - dia_local(ingreso)).days if ingreso else None,
            "dias_para_vencer": (vence - hoy_).days if vence else None,
            "ocupacion": float(min(Decimal(1), (cant or 0) / cap)) if cap else None})
    return ocultar_costos(salida, ctx.ver_costos)


@router.get("/ubicaciones/{id_}/contenido")
def contenido(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER, "inventario:ver"))):
    u = db.get(Ubicacion, id_)
    if not u:
        raise no_encontrado("Ubicacion")
    bodega_de(db, ctx, u.bodega_id)
    ids = [u.id] + _descendientes(db, u.id)
    existencias = db.scalars(select(Existencia).join(Producto, Existencia.producto_id == Producto.id).where(
        Existencia.ubicacion_id.in_(ids), Existencia.cantidad_fisica > 0).order_by(Existencia.fecha_ingreso)).unique().all()
    items = [{
        "id": e.id, "codigo_publico": e.codigo_publico, "producto": e.producto.nombre, "producto_codigo": e.producto.codigo,
        "lote": e.lote.codigo if e.lote else None, "cantidad": float(e.cantidad_fisica), "unidad": e.unidad.codigo,
        "fecha_ingreso": e.fecha_ingreso.isoformat() + "Z",
        "fecha_vencimiento": e.lote.fecha_vencimiento.isoformat() if e.lote and e.lote.fecha_vencimiento else None,
        "valor": float(e.cantidad_fisica * e.costo_unitario),
        "ubicacion": e.ubicacion.codigo_completo if e.ubicacion else None} for e in existencias]
    total = sum(Decimal(str(i["cantidad"])) for i in items)
    return ocultar_costos({
        "ubicacion": a_dict(u), "existencias": items, "cantidad_total": float(total),
        "valor": sum(i["valor"] for i in items),
        "capacidad_disponible": float(u.capacidad - total) if u.capacidad is not None else None}, ctx.ver_costos)
