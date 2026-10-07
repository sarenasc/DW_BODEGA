"""Usuarios, roles, permisos, auditoria, empresa y parametros generales."""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.crud import guardar, paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.parametros import fijar_parametro
from app.core.seguridad import hash_clave, validar_fortaleza
from app.core.util import a_dict, ahora
from app.modelos import Auditoria, Bodega, Configuracion, Empresa, Familia, Permiso, Rol, Sesion, Usuario

router = APIRouter(prefix="/api", tags=["Usuarios y configuracion"])
ADMIN = "usuarios:administrar"


def _usuario(u: Usuario) -> dict:
    return a_dict(u, excluir=("clave_hash",), roles=[r.id for r in u.roles], roles_nombres=[r.nombre for r in u.roles],
                  bodegas=[b.id for b in u.bodegas], familias=[f.id for f in u.familias])


class UsuarioEntrada(BaseModel):
    usuario: str | None = None
    nombre: str | None = None
    email: str | None = None
    clave: str | None = None
    activo: bool | None = None
    roles: list[int] | None = None
    todas_bodegas: bool | None = None
    bodegas: list[int] | None = None
    todas_familias: bool | None = None
    familias: list[int] | None = None
    debe_cambiar_clave: bool | None = None


def _aplicar(db: Session, ctx: Contexto, u: Usuario, d: UsuarioEntrada) -> None:
    for campo in ("usuario", "nombre", "email", "activo", "todas_bodegas", "todas_familias", "debe_cambiar_clave"):
        v = getattr(d, campo)
        if v is not None:
            setattr(u, campo, v.strip() if isinstance(v, str) else v)
    if d.clave:
        if (msg := validar_fortaleza(d.clave)):
            raise ErrorNegocio("CLAVE_DEBIL", msg)
        u.clave_hash = hash_clave(d.clave)
    if d.roles is not None:
        u.roles = list(db.scalars(select(Rol).where(Rol.id.in_(d.roles), Rol.empresa_id == ctx.empresa_id)))
    if d.bodegas is not None:
        u.bodegas = list(db.scalars(select(Bodega).where(Bodega.id.in_(d.bodegas), Bodega.empresa_id == ctx.empresa_id)))
    if d.familias is not None:
        u.familias = list(db.scalars(select(Familia).where(Familia.id.in_(d.familias), Familia.empresa_id == ctx.empresa_id)))


@router.get("/usuarios")
def listar_usuarios(q: str | None = None, pagina: int = 1, tam: int = 100, db: Session = Depends(get_db),
                    ctx: Contexto = Depends(requiere(ADMIN))):
    c = select(Usuario).where(Usuario.empresa_id == ctx.empresa_id).order_by(Usuario.nombre)
    if q:
        p = f"%{q.lower()}%"
        c = c.where(or_(func.lower(Usuario.usuario).like(p), func.lower(Usuario.nombre).like(p)))
    return paginar(db, c, pagina, tam, _usuario)


@router.post("/usuarios", status_code=201)
def crear_usuario(d: UsuarioEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    if not d.usuario or not d.nombre or not d.clave:
        raise ErrorNegocio("DATOS", "Usuario, nombre y clave son obligatorios.")
    u = Usuario(empresa_id=ctx.empresa_id, usuario="", nombre="", clave_hash="")
    _aplicar(db, ctx, u, d)
    guardar(db, u)
    auditar(db, ctx, "usuario", u.id, "CREAR", nuevo=_usuario(u))
    return _usuario(u)


@router.put("/usuarios/{id_}")
def editar_usuario(id_: int, d: UsuarioEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    u = db.get(Usuario, id_)
    if not u or u.empresa_id != ctx.empresa_id:
        raise no_encontrado("Usuario")
    antes = _usuario(u)
    if u.id == ctx.usuario.id and d.activo is False:
        raise ErrorNegocio("AUTO_BLOQUEO", "No puede desactivar su propio usuario.")
    _aplicar(db, ctx, u, d)
    guardar(db, u)
    if d.activo is False or d.clave:
        for s in db.scalars(select(Sesion).where(Sesion.usuario_id == u.id, Sesion.revocada_en.is_(None))):
            s.revocada_en, s.motivo_revocacion = ahora(), "ADMIN"
    auditar(db, ctx, "usuario", u.id, "EDITAR", anterior=antes, nuevo=_usuario(u))
    return _usuario(u)


# ---- roles y permisos ----

def _rol(r: Rol) -> dict:
    return a_dict(r, permisos=sorted(p.codigo for p in r.permisos))


class RolEntrada(BaseModel):
    codigo: str | None = None
    nombre: str | None = None
    descripcion: str | None = None
    permisos: list[str] | None = None


@router.get("/permisos")
def listar_permisos(db: Session = Depends(get_db), _: Contexto = Depends(requiere(ADMIN))):
    return [a_dict(p) for p in db.scalars(select(Permiso).order_by(Permiso.modulo, Permiso.accion))]


@router.get("/roles")
def listar_roles(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    return [_rol(r) for r in db.scalars(select(Rol).where(Rol.empresa_id == ctx.empresa_id).order_by(Rol.nombre))]


def _guardar_rol(db: Session, ctx: Contexto, r: Rol, d: RolEntrada) -> dict:
    antes = _rol(r) if r.id else None
    if d.nombre is not None:
        r.nombre = d.nombre
    if d.descripcion is not None:
        r.descripcion = d.descripcion
    if d.codigo and not r.es_sistema:
        r.codigo = d.codigo.upper().replace(" ", "_")
    if d.permisos is not None:
        if r.codigo == "ADMINISTRADOR" and ADMIN not in d.permisos:
            raise ErrorNegocio("ROL_PROTEGIDO", "El rol Administrador debe conservar la administracion de usuarios.")
        r.permisos = list(db.scalars(select(Permiso).where(Permiso.codigo.in_(d.permisos))))
    guardar(db, r)
    auditar(db, ctx, "rol", r.id, "EDITAR" if antes else "CREAR", anterior=antes, nuevo=_rol(r))
    return _rol(r)


@router.post("/roles", status_code=201)
def crear_rol(d: RolEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    if not d.codigo or not d.nombre:
        raise ErrorNegocio("DATOS", "Codigo y nombre son obligatorios.")
    return _guardar_rol(db, ctx, Rol(empresa_id=ctx.empresa_id, codigo=d.codigo.upper().replace(" ", "_"), nombre=d.nombre), d)


@router.put("/roles/{id_}")
def editar_rol(id_: int, d: RolEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    r = db.get(Rol, id_)
    if not r or r.empresa_id != ctx.empresa_id:
        raise no_encontrado("Rol")
    return _guardar_rol(db, ctx, r, d)


@router.delete("/roles/{id_}")
def eliminar_rol(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere(ADMIN))):
    r = db.get(Rol, id_)
    if not r or r.empresa_id != ctx.empresa_id:
        raise no_encontrado("Rol")
    if r.es_sistema:
        raise ErrorNegocio("ROL_PROTEGIDO", "Los roles iniciales no se eliminan; puede editar sus permisos.")
    auditar(db, ctx, "rol", r.id, "ELIMINAR", anterior=_rol(r))
    db.delete(r)
    return {"ok": True}


# ---- auditoria ----

@router.get("/auditoria")
def listar_auditoria(entidad: str | None = None, entidad_id: str | None = None, usuario_id: int | None = None,
                     accion: str | None = None, desde: datetime | None = None, hasta: datetime | None = None,
                     pagina: int = Query(1, ge=1), tam: int = Query(50, le=500), db: Session = Depends(get_db),
                     ctx: Contexto = Depends(requiere("auditoria:ver"))):
    c = select(Auditoria).where(or_(Auditoria.empresa_id == ctx.empresa_id, Auditoria.empresa_id.is_(None)))
    for col, val in ((Auditoria.entidad, entidad), (Auditoria.entidad_id, entidad_id), (Auditoria.usuario_id, usuario_id),
                     (Auditoria.accion, accion)):
        if val not in (None, ""):
            c = c.where(col == val)
    if desde:
        c = c.where(Auditoria.fecha >= desde)
    if hasta:
        c = c.where(Auditoria.fecha <= hasta)
    nombres = dict(db.execute(select(Usuario.id, Usuario.nombre)).all())
    return paginar(db, c.order_by(Auditoria.id.desc()), pagina, tam,
                   lambda a: a_dict(a, usuario=nombres.get(a.usuario_id)))


# ---- empresa y parametros ----

class EmpresaEntrada(BaseModel):
    nombre: str | None = None
    rut: str | None = None
    moneda: str | None = None
    zona_horaria: str | None = None
    idioma: str | None = None


@router.get("/empresa")
def ver_empresa(db: Session = Depends(get_db), ctx: Contexto = Depends(contexto)):
    return a_dict(db.get(Empresa, ctx.empresa_id))


@router.put("/empresa")
def editar_empresa(d: EmpresaEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("configuracion:editar"))):
    e = db.get(Empresa, ctx.empresa_id)
    antes = a_dict(e)
    for k, v in d.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(e, k, v)
    auditar(db, ctx, "empresa", e.id, "EDITAR", anterior=antes, nuevo=e)
    return a_dict(e)


@router.get("/configuraciones")
def listar_config(db: Session = Depends(get_db), ctx: Contexto = Depends(contexto)):
    filas = db.scalars(select(Configuracion).where(
        or_(Configuracion.empresa_id.is_(None), Configuracion.empresa_id == ctx.empresa_id)).order_by(Configuracion.clave)).all()
    salida: dict[str, dict] = {}
    for f in sorted(filas, key=lambda f: f.empresa_id is not None):  # el valor de la empresa pisa al global
        salida[f.clave] = {"clave": f.clave, "valor": f.valor,
                           "descripcion": f.descripcion or salida.get(f.clave, {}).get("descripcion")}
    return list(salida.values())


class ValorConfig(BaseModel):
    valor: Any = None


@router.put("/configuraciones/{clave}")
def fijar_config(clave: str, d: ValorConfig, db: Session = Depends(get_db),
                 ctx: Contexto = Depends(requiere("configuracion:editar"))):
    f = fijar_parametro(db, clave, d.valor, ctx.empresa_id)
    auditar(db, ctx, "configuracion", clave, "EDITAR", nuevo={"valor": d.valor})
    return {"clave": f.clave, "valor": f.valor}
