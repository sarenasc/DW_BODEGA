"""Maestros parametrizables: temporadas, unidades, conversiones, familias, subfamilias, productos, proveedores."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.crud import crear_crud
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict
from app.modelos import (ConversionUnidad, DefinicionAtributo, Familia, MotivoMovimiento, PlantillaEtiqueta, Producto,
                         Proveedor, Subfamilia, Temporada, TipoBodega, TipoMovimiento, UnidadMedida)
from app.servicios.catalogo import a_unidad_base, factor_conversion, politica_efectiva, validar_politica

router = APIRouter(prefix="/api", tags=["Maestros"])
VER, ADM, CFG = "catalogo:ver", "catalogo:administrar", "configuracion:editar"


def _val_temporada(db: Session, ctx: Contexto, t: Temporada, antes):
    if t.fecha_termino < t.fecha_inicio:
        raise ErrorNegocio("FECHAS", "La fecha de termino debe ser posterior al inicio.")
    if t.actual:  # una sola temporada actual por empresa
        for otra in db.scalars(select(Temporada).where(Temporada.empresa_id == ctx.empresa_id, Temporada.actual.is_(True))):
            if otra is not t:
                otra.actual = False


crear_crud(router, "/temporadas", Temporada, entidad="temporada", ver=VER, editar=CFG, validar=_val_temporada,
           orden="fecha_inicio")
crear_crud(router, "/unidades", UnidadMedida, entidad="unidad", ver=VER, editar=ADM)
crear_crud(router, "/proveedores", Proveedor, entidad="proveedor", ver=VER, editar=ADM, buscar=("nombre", "codigo", "rut"))
crear_crud(router, "/tipos-bodega", TipoBodega, entidad="tipo_bodega", ver=VER, editar=CFG)
crear_crud(router, "/tipos-movimiento", TipoMovimiento, entidad="tipo_movimiento", ver=VER, editar=CFG, excluir={"es_sistema"})
crear_crud(router, "/motivos-movimiento", MotivoMovimiento, entidad="motivo_movimiento", ver=VER, editar=CFG,
           filtros=("clase",), serializar=lambda m: a_dict(m, tipo_movimiento=m.tipo_movimiento.codigo))
crear_crud(router, "/plantillas-etiquetas", PlantillaEtiqueta, entidad="plantilla_etiqueta", ver=VER, editar=CFG,
           buscar=("nombre",))
crear_crud(router, "/definiciones-atributos", DefinicionAtributo, entidad="definicion_atributo", ver=VER, editar=ADM,
           buscar=("clave", "etiqueta"), filtros=("familia_id",))


# ---- conversiones ----

def _val_conversion(db: Session, ctx: Contexto, c: ConversionUnidad, antes):
    if c.unidad_origen_id == c.unidad_destino_id:
        raise ErrorNegocio("CONVERSION", "Origen y destino deben ser unidades distintas.")
    if c.factor is None or Decimal(c.factor) <= 0:
        raise ErrorNegocio("CONVERSION", "El factor debe ser mayor que cero.")


def _conversion(c: ConversionUnidad) -> dict:
    return a_dict(c)


crear_crud(router, "/conversiones", ConversionUnidad, entidad="conversion", ver=VER, editar=ADM, buscar=(),
           filtros=("producto_id",), validar=_val_conversion, orden="id", serializar=_conversion)


@router.get("/conversiones-calcular")
def calcular_conversion(cantidad: Decimal, unidad_origen_id: int, unidad_destino_id: int, producto_id: int | None = None,
                        db: Session = Depends(get_db), _: Contexto = Depends(requiere(VER))):
    f = factor_conversion(db, producto_id, unidad_origen_id, unidad_destino_id)
    return {"factor": float(f), "resultado": float(cantidad * f)}


# ---- familias y subfamilias ----

def _val_politica(db, ctx, obj, antes):
    validar_politica(obj)
    obj.codigo = obj.codigo.strip().upper()


def _alcance_familia(q, ctx: Contexto):
    return q if ctx.familias is None else q.where(Familia.id.in_(ctx.familias))


def _alcance_subfamilia(q, ctx: Contexto):
    q = q.join(Familia, Subfamilia.familia_id == Familia.id).where(Familia.empresa_id == ctx.empresa_id)
    return q if ctx.familias is None else q.where(Familia.id.in_(ctx.familias))


crear_crud(router, "/familias", Familia, entidad="familia", ver=VER, editar=ADM, validar=_val_politica,
           alcance=_alcance_familia)
crear_crud(router, "/subfamilias", Subfamilia, entidad="subfamilia", ver=VER, editar=ADM, validar=_val_politica,
           filtros=("familia_id",), alcance=_alcance_subfamilia, por_empresa=False,
           serializar=lambda s: a_dict(s, familia=s.familia.nombre, familia_codigo=s.familia.codigo))


# ---- productos ----

def producto_dict(p: Producto, unidades: dict[int, str] | None = None, detalle: bool = False) -> dict:
    d = a_dict(p, subfamilia=p.subfamilia.nombre, subfamilia_codigo=p.subfamilia.codigo,
               familia_id=p.subfamilia.familia_id, familia=p.subfamilia.familia.nombre,
               familia_codigo=p.subfamilia.familia.codigo, unidad_base=p.unidad_base.codigo)
    if unidades:
        d["unidad_compra"] = unidades.get(p.unidad_compra_id)
        d["unidad_consumo"] = unidades.get(p.unidad_consumo_id)
    if detalle:
        d["politica"] = politica_efectiva(p)
    return d


def _val_producto(db: Session, ctx: Contexto, p: Producto, antes):
    validar_politica(p)
    p.codigo = p.codigo.strip().upper()
    sub = db.get(Subfamilia, p.subfamilia_id)
    if not sub or sub.familia.empresa_id != ctx.empresa_id:
        raise ErrorNegocio("SUBFAMILIA", "La subfamilia indicada no existe.")
    ctx.exigir_familia(sub.familia_id)
    if p.stock_minimo is not None and p.stock_maximo is not None and p.stock_maximo < p.stock_minimo:
        raise ErrorNegocio("STOCK", "El stock maximo no puede ser menor que el minimo.")
    for uid in (p.unidad_compra_id, p.unidad_consumo_id):
        if uid and uid != p.unidad_base_id and p.id:
            factor_conversion(db, p.id, uid, p.unidad_base_id)  # exige conversion configurada
    if antes and antes["unidad_base_id"] != p.unidad_base_id:
        from app.modelos import Existencia
        if db.scalar(select(Existencia.id).where(Existencia.producto_id == p.id).limit(1)):
            raise ErrorNegocio("UNIDAD_BASE", "No se puede cambiar la unidad base de un producto con existencias.")
    p.subfamilia = sub


def _alcance_producto(q, ctx: Contexto):
    if ctx.familias is None:
        return q
    return q.join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).where(Subfamilia.familia_id.in_(ctx.familias))


def _unidades(db: Session) -> dict[int, str]:
    return dict(db.execute(select(UnidadMedida.id, UnidadMedida.codigo)).all())


_obtener_producto = crear_crud(
    router, "/productos", Producto, entidad="producto", ver=VER, editar=ADM, validar=_val_producto,
    buscar=("nombre", "codigo", "codigo_barras", "codigo_externo"), filtros=("subfamilia_id", "proveedor_id"),
    alcance=_alcance_producto, serializar=producto_dict)


@router.get("/productos/{id_}/detalle")
def detalle_producto(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    p = _obtener_producto(db, ctx, id_)
    d = producto_dict(p, _unidades(db), detalle=True)
    d["conversiones"] = [a_dict(c) for c in db.scalars(select(ConversionUnidad).where(ConversionUnidad.producto_id == p.id))]
    return d


@router.get("/productos/{id_}/convertir")
def convertir_producto(id_: int, cantidad: Decimal, unidad_id: int, db: Session = Depends(get_db),
                       ctx: Contexto = Depends(requiere(VER))):
    p = _obtener_producto(db, ctx, id_)
    base, factor = a_unidad_base(db, p, cantidad, unidad_id)
    return {"cantidad_base": float(base), "factor": float(factor), "unidad_base": p.unidad_base.codigo}


@router.get("/catalogos")
def catalogos(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(VER))):
    """Listas cortas para poblar selectores del frontend en una sola llamada."""
    from app.modelos import (BASES_COSTEO, ESTADOS_LOTE, ESTRATEGIAS, GRANULARIDADES, MODOS_LOTE, MOMENTOS_LOTE,
                             POLITICAS_FIFO, REINICIOS, Bodega)
    fam = select(Familia).where(Familia.empresa_id == ctx.empresa_id, Familia.activo.is_(True)).order_by(Familia.nombre)
    if ctx.familias is not None:
        fam = fam.where(Familia.id.in_(ctx.familias))
    familias = db.scalars(fam).all()
    bod = select(Bodega).where(Bodega.empresa_id == ctx.empresa_id, Bodega.activo.is_(True)).order_by(Bodega.nombre)
    if ctx.bodegas is not None:
        bod = bod.where(Bodega.id.in_(ctx.bodegas))
    simple = lambda filas: [{"id": f.id, "codigo": f.codigo, "nombre": f.nombre} for f in filas]  # noqa: E731
    return {
        "unidades": [a_dict(u) for u in db.scalars(select(UnidadMedida).where(UnidadMedida.activo.is_(True)).order_by(UnidadMedida.codigo))],
        "familias": simple(familias),
        "subfamilias": [{"id": s.id, "codigo": s.codigo, "nombre": s.nombre, "familia_id": s.familia_id}
                        for s in db.scalars(select(Subfamilia).where(Subfamilia.familia_id.in_([f.id for f in familias]),
                                                                    Subfamilia.activo.is_(True)).order_by(Subfamilia.nombre))],
        "bodegas": simple(db.scalars(bod).all()),
        "proveedores": simple(db.scalars(select(Proveedor).where(Proveedor.empresa_id == ctx.empresa_id, Proveedor.activo.is_(True)).order_by(Proveedor.nombre))),
        "temporadas": [a_dict(t) for t in db.scalars(select(Temporada).where(Temporada.empresa_id == ctx.empresa_id).order_by(Temporada.fecha_inicio.desc()))],
        "motivos": [a_dict(m, tipo_movimiento=m.tipo_movimiento.codigo) for m in db.scalars(select(MotivoMovimiento).where(MotivoMovimiento.activo.is_(True)))],
        "tipos_bodega": simple(db.scalars(select(TipoBodega)).all()),
        "enumeraciones": {
            "granularidad": GRANULARIDADES, "estrategia_salida": ESTRATEGIAS, "politica_fifo": POLITICAS_FIFO,
            "modos_lote": MODOS_LOTE, "momentos_lote": MOMENTOS_LOTE, "reinicios": REINICIOS,
            "estados_lote": ESTADOS_LOTE, "bases_costeo": BASES_COSTEO,
            "tipos_documento": ("FACTURA", "GUIA_DESPACHO", "GUIA_INTERNA", "OTRO"),
        },
    }


def obtener_producto(db: Session, ctx: Contexto, id_: int) -> Producto:
    p = db.get(Producto, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Producto")
    ctx.exigir_familia(p.subfamilia.familia_id)
    return p
