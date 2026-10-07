"""Errores de negocio con codigo estable para el frontend."""
from fastapi import Request
from fastapi.responses import JSONResponse


class ErrorNegocio(Exception):
    def __init__(self, codigo: str, mensaje: str, http: int = 400, datos: dict | None = None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.http, self.datos = codigo, mensaje, http, datos or {}


def no_encontrado(que: str = "Registro") -> ErrorNegocio:
    return ErrorNegocio("NO_ENCONTRADO", f"{que} no encontrado.", 404)


def sin_permiso(msg: str = "No tiene permiso para esta accion.") -> ErrorNegocio:
    return ErrorNegocio("SIN_PERMISO", msg, 403)


async def manejar_error_negocio(_: Request, exc: ErrorNegocio):
    return JSONResponse(status_code=exc.http, content={"codigo": exc.codigo, "mensaje": exc.mensaje, "datos": exc.datos})
