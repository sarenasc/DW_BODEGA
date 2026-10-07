"""Autenticacion, permisos (RBAC) y alcance por bodega / familia."""
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Sesion, Usuario

from .db import get_db
from .errores import ErrorNegocio, sin_permiso
from .seguridad import leer_token_acceso


@dataclass
class Contexto:
    """Usuario autenticado y datos de la peticion, disponibles para servicios y auditoria."""
    usuario: Usuario
    permisos: set[str]
    ip: str | None = None
    dispositivo: str | None = None

    @property
    def empresa_id(self) -> int:
        return self.usuario.empresa_id

    def puede(self, permiso: str) -> bool:
        return permiso in self.permisos

    def exigir(self, permiso: str, mensaje: str | None = None) -> None:
        if permiso not in self.permisos:
            raise sin_permiso(mensaje or f"Requiere el permiso {permiso}.")

    @property
    def ver_costos(self) -> bool:
        return "costos:ver" in self.permisos

    # Alcance: None significa sin restriccion.
    @property
    def bodegas(self) -> set[int] | None:
        return None if self.usuario.todas_bodegas else {b.id for b in self.usuario.bodegas}

    @property
    def familias(self) -> set[int] | None:
        return None if self.usuario.todas_familias else {f.id for f in self.usuario.familias}

    def exigir_bodega(self, bodega_id: int | None) -> None:
        b = self.bodegas
        if b is not None and bodega_id is not None and bodega_id not in b:
            raise sin_permiso("No tiene acceso a esta bodega.")

    def exigir_familia(self, familia_id: int | None) -> None:
        f = self.familias
        if f is not None and familia_id is not None and familia_id not in f:
            raise sin_permiso("No tiene acceso a esta familia de productos.")


def ip_cliente(request: Request) -> str | None:
    reenviada = request.headers.get("x-forwarded-for")
    if reenviada:
        return reenviada.split(",")[0].strip()[:45]
    return request.client.host if request.client else None


def contexto(request: Request, db: Session = Depends(get_db)) -> Contexto:
    cab = request.headers.get("authorization", "")
    if not cab.lower().startswith("bearer "):
        raise ErrorNegocio("NO_AUTENTICADO", "Debe iniciar sesion.", 401)
    carga = leer_token_acceso(cab[7:])
    if not carga:
        raise ErrorNegocio("TOKEN_INVALIDO", "La sesion expiro.", 401)
    usuario = db.get(Usuario, int(carga["sub"]))
    sesion = db.scalar(select(Sesion).where(Sesion.id == carga.get("sid")))
    if not usuario or not usuario.activo or not sesion or sesion.revocada_en is not None:
        raise ErrorNegocio("TOKEN_INVALIDO", "La sesion ya no es valida.", 401)
    return Contexto(usuario, usuario.permisos, ip_cliente(request), (request.headers.get("user-agent") or "")[:250])


def requiere(*permisos: str):
    """Dependencia: exige todos los permisos indicados. Devuelve el contexto."""
    def dep(ctx: Contexto = Depends(contexto)) -> Contexto:
        for p in permisos:
            ctx.exigir(p)
        return ctx
    return dep


def requiere_alguno(*permisos: str):
    def dep(ctx: Contexto = Depends(contexto)) -> Contexto:
        if not any(p in ctx.permisos for p in permisos):
            raise sin_permiso()
        return ctx
    return dep
