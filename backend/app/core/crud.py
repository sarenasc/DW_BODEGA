"""Fabrica de CRUD para maestros: listado con busqueda/filtros/paginacion, alta, edicion y baja logica."""
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, Numeric, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auditoria import auditar
from .db import get_db
from .dependencias import Contexto, requiere
from .errores import ErrorNegocio, no_encontrado
from .util import a_dict

NO_EDITABLES = {"id", "empresa_id", "creado_en", "actualizado_en", "version", "version_stock"}


def _tipo_py(col) -> Any:
    t = col.type
    if isinstance(t, Boolean):
        return bool
    if isinstance(t, Integer):
        return int
    if isinstance(t, Numeric):
        return Decimal
    if isinstance(t, DateTime):
        return datetime
    if isinstance(t, Date):
        return date
    if isinstance(t, JSON):
        return Any
    return str


def esquema_de(modelo, nombre: str, excluir: set[str] = frozenset(), parcial: bool = False) -> type[BaseModel]:
    """Genera el esquema Pydantic de entrada a partir de las columnas del modelo."""
    campos = {}
    for col in modelo.__table__.columns:
        if col.key in NO_EDITABLES or col.key in excluir:
            continue
        tipo = _tipo_py(col)
        opcional = parcial or col.nullable or col.default is not None or col.server_default is not None
        campos[col.key] = (tipo | None, None) if opcional else (tipo, ...)
    return create_model(nombre, __config__=ConfigDict(extra="forbid", str_strip_whitespace=True), **campos)


def paginar(db: Session, consulta, pagina: int, tam: int, serializar: Callable = a_dict) -> dict:
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    filas = db.scalars(consulta.limit(tam).offset((pagina - 1) * tam)).unique().all()
    return {"total": total, "pagina": pagina, "tam": tam, "items": [serializar(f) for f in filas]}


def guardar(db: Session, obj) -> None:
    try:
        db.add(obj)
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise ErrorNegocio("DUPLICADO", "Ya existe un registro con ese codigo o viola una restriccion.", 409) from e


def crear_crud(router: APIRouter, ruta: str, modelo, *, entidad: str, ver: str, editar: str,
               buscar: tuple[str, ...] = ("codigo", "nombre"), filtros: tuple[str, ...] = (),
               excluir: set[str] = frozenset(), orden: str | None = None, por_empresa: bool | None = None,
               serializar: Callable = a_dict, validar: Callable | None = None, alcance: Callable | None = None):
    """Registra GET lista, GET uno, POST, PUT y DELETE para un modelo simple."""
    cols = modelo.__table__.c
    por_empresa = ("empresa_id" in cols) if por_empresa is None else por_empresa
    Entrada = esquema_de(modelo, f"{modelo.__name__}Entrada", excluir)
    Parcial = esquema_de(modelo, f"{modelo.__name__}Parcial", excluir, parcial=True)

    def base(ctx: Contexto):
        q = select(modelo)
        if por_empresa:
            q = q.where(cols.empresa_id == ctx.empresa_id)
        if alcance:
            q = alcance(q, ctx)
        return q

    def obtener(db: Session, ctx: Contexto, id_: int):
        obj = db.scalars(base(ctx).where(cols.id == id_)).unique().first()
        if not obj:
            raise no_encontrado(entidad)
        return obj

    @router.get(ruta, name=f"listar_{entidad}")
    def listar(request: Request, q: str | None = None, activo: bool | None = None, pagina: int = Query(1, ge=1),
               tam: int = Query(50, ge=1, le=1000), db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ver))):
        c = base(ctx)
        if q:
            patron = f"%{q.strip().lower()}%"
            c = c.where(or_(*[func.lower(cols[b]).like(patron) for b in buscar if b in cols]))
        if activo is not None:
            for nombre in ("activo", "activa"):
                if nombre in cols:
                    c = c.where(cols[nombre] == activo)
        for f in filtros:
            v = request.query_params.get(f)
            if v not in (None, ""):
                c = c.where(cols[f] == (None if v == "null" else v))
        c = c.order_by(cols[orden] if orden else cols[buscar[0]] if buscar and buscar[0] in cols else cols.id)
        return paginar(db, c, pagina, tam, serializar)

    @router.get(ruta + "/{id_}", name=f"obtener_{entidad}")
    def uno(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ver))):
        return serializar(obtener(db, ctx, id_))

    @router.post(ruta, status_code=201, name=f"crear_{entidad}")
    def crear(datos: Entrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(editar))):  # type: ignore[valid-type]
        valores = datos.model_dump(exclude_unset=True)
        obj = modelo(**valores)
        if por_empresa:
            obj.empresa_id = ctx.empresa_id
        if validar:
            validar(db, ctx, obj, None)
        guardar(db, obj)
        auditar(db, ctx, entidad, obj.id, "CREAR", nuevo=obj)
        return serializar(obj)

    @router.put(ruta + "/{id_}", name=f"editar_{entidad}")
    def actualizar(id_: int, datos: Parcial, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(editar))):  # type: ignore[valid-type]
        obj = obtener(db, ctx, id_)
        antes = a_dict(obj)
        for k, v in datos.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        if validar:
            validar(db, ctx, obj, antes)
        guardar(db, obj)
        auditar(db, ctx, entidad, obj.id, "EDITAR", anterior=antes, nuevo=obj)
        return serializar(obj)

    @router.delete(ruta + "/{id_}", name=f"eliminar_{entidad}")
    def eliminar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(editar))):
        obj = obtener(db, ctx, id_)
        antes = a_dict(obj)
        if "activo" in cols or "activa" in cols:
            setattr(obj, "activo" if "activo" in cols else "activa", False)  # baja logica: se conserva la historia
            accion = "DESACTIVAR"
        else:
            try:
                with db.begin_nested():
                    db.delete(obj)
                    db.flush()
            except IntegrityError as e:
                raise ErrorNegocio("EN_USO", "No se puede eliminar: tiene registros asociados.", 409) from e
            accion = "ELIMINAR"
        auditar(db, ctx, entidad, id_, accion, anterior=antes)
        return {"ok": True}

    return obtener
