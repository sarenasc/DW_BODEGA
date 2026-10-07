"""Inicio de sesion: token de acceso corto + sesion renovable en cookie httpOnly."""
import time
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.config import ajustes
from app.core.db import get_db
from app.core.dependencias import Contexto, contexto, ip_cliente
from app.core.errores import ErrorNegocio
from app.core.seguridad import (crear_token_acceso, hash_clave, huella, token_aleatorio, validar_fortaleza,
                                verificar_clave)
from app.core.util import a_dict, ahora
from app.modelos import Empresa, Sesion, Usuario

router = APIRouter(prefix="/api/auth", tags=["Autenticacion"])
COOKIE = "wms_sesion"
GRACIA_ROTACION = 20  # segundos
_intentos: dict[str, list[float]] = defaultdict(list)


def _limitar(clave: str) -> None:
    a = ajustes()
    ahora_ = time.time()
    recientes = [t for t in _intentos[clave] if ahora_ - t < a.ventana_login_segundos]
    _intentos[clave] = recientes
    if len(recientes) >= a.intentos_login:
        raise ErrorNegocio("DEMASIADOS_INTENTOS", "Demasiados intentos. Espere unos minutos.", 429)
    recientes.append(ahora_)


def perfil(db: Session, u: Usuario) -> dict:
    emp = db.get(Empresa, u.empresa_id)
    return {
        "id": u.id, "usuario": u.usuario, "nombre": u.nombre, "email": u.email,
        "debe_cambiar_clave": u.debe_cambiar_clave,
        "roles": [r.nombre for r in u.roles], "permisos": sorted(u.permisos),
        "todas_bodegas": u.todas_bodegas, "bodegas": [b.id for b in u.bodegas],
        "todas_familias": u.todas_familias, "familias": [f.id for f in u.familias],
        "empresa": a_dict(emp), "modo_demo": ajustes().modo_demo,
    }


def _emitir(db: Session, u: Usuario, request: Request, response: Response) -> dict:
    a = ajustes()
    crudo = token_aleatorio()
    s = Sesion(usuario_id=u.id, token_hash=huella(crudo), expira_en=ahora() + timedelta(days=a.dias_sesion),
               ip=ip_cliente(request), dispositivo=(request.headers.get("user-agent") or "")[:250])
    db.add(s)
    db.flush()
    response.set_cookie(COOKIE, crudo, max_age=a.dias_sesion * 86400, httponly=True, samesite="strict",
                        secure=a.cookie_segura, path="/api/auth")
    return {"token": crear_token_acceso(u.id, s.id), "expira_minutos": a.minutos_token_acceso, "usuario": perfil(db, u)}


class Credenciales(BaseModel):
    usuario: str
    clave: str


@router.post("/login")
def login(datos: Credenciales, request: Request, response: Response, db: Session = Depends(get_db)):
    nombre = datos.usuario.strip().lower()
    _limitar(f"{ip_cliente(request)}|{nombre}")
    u = db.scalar(select(Usuario).where(func.lower(Usuario.usuario) == nombre))
    if not u or not u.activo or not verificar_clave(datos.clave, u.clave_hash):
        raise ErrorNegocio("CREDENCIALES", "Usuario o clave incorrectos.", 401)
    u.ultimo_acceso = ahora()
    _intentos.pop(f"{ip_cliente(request)}|{nombre}", None)
    resultado = _emitir(db, u, request, response)
    ctx = Contexto(u, u.permisos, ip_cliente(request), (request.headers.get("user-agent") or "")[:250])
    auditar(db, ctx, "sesion", u.id, "LOGIN")
    return resultado


@router.post("/refrescar")
def refrescar(request: Request, response: Response, db: Session = Depends(get_db)):
    crudo = request.cookies.get(COOKIE)
    s = db.scalar(select(Sesion).where(Sesion.token_hash == huella(crudo))) if crudo else None
    # Rotacion: cada sesion renovable se usa una sola vez. Se tolera su reutilizacion durante unos segundos
    # porque dos pestanas (o una recarga rapida) pueden renovar a la vez con la misma cookie.
    recien_rotada = bool(s and s.revocada_en and s.motivo_revocacion == "ROTACION"
                         and (ahora() - s.revocada_en).total_seconds() <= GRACIA_ROTACION)
    if not s or s.expira_en < ahora() or (s.revocada_en is not None and not recien_rotada):
        raise ErrorNegocio("SESION_EXPIRADA", "Debe iniciar sesion.", 401)
    u = db.get(Usuario, s.usuario_id)
    if not u or not u.activo:
        raise ErrorNegocio("SESION_EXPIRADA", "Debe iniciar sesion.", 401)
    if s.revocada_en is None:
        s.revocada_en, s.motivo_revocacion = ahora(), "ROTACION"
    return _emitir(db, u, request, response)


@router.post("/salir")
def salir(request: Request, response: Response, db: Session = Depends(get_db)):
    crudo = request.cookies.get(COOKIE)
    if crudo:
        s = db.scalar(select(Sesion).where(Sesion.token_hash == huella(crudo)))
        if s:
            s.revocada_en, s.motivo_revocacion = ahora(), "SALIDA"  # un cierre de sesion anula tambien la gracia
    response.delete_cookie(COOKIE, path="/api/auth")
    return {"ok": True}


@router.get("/yo")
def yo(ctx: Contexto = Depends(contexto), db: Session = Depends(get_db)):
    return perfil(db, ctx.usuario)


class CambioClave(BaseModel):
    clave_actual: str
    clave_nueva: str


@router.post("/cambiar-clave")
def cambiar_clave(datos: CambioClave, ctx: Contexto = Depends(contexto), db: Session = Depends(get_db)):
    u = db.get(Usuario, ctx.usuario.id)
    if not verificar_clave(datos.clave_actual, u.clave_hash):
        raise ErrorNegocio("CLAVE_INCORRECTA", "La clave actual no coincide.")
    if (msg := validar_fortaleza(datos.clave_nueva)):
        raise ErrorNegocio("CLAVE_DEBIL", msg)
    u.clave_hash, u.debe_cambiar_clave = hash_clave(datos.clave_nueva), False
    auditar(db, ctx, "usuario", u.id, "CAMBIAR_CLAVE")
    return {"ok": True}
