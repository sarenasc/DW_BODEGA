"""Aplicacion FastAPI: API REST bajo /api y, si existe, el frontend estatico en /."""
import importlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.core.errores import ErrorNegocio, manejar_error_negocio

log = logging.getLogger("wms")

MODULOS = [
    "instalacion", "auth", "usuarios", "maestros", "bodegas", "lotes", "inventario", "consumo", "reservas",
    "procesos", "integraciones", "alertas", "dashboard", "reportes", "trazabilidad", "operaciones", "adjuntos",
]


@asynccontextmanager
async def ciclo(app: FastAPI):
    a = ajustes()
    a.secreto  # falla temprano si falta la clave secreta
    from app.arranque import al_iniciar, al_detener
    al_iniciar()
    yield
    al_detener()


def crear_app() -> FastAPI:
    a = ajustes()
    app = FastAPI(title="WMS Bodegas", version="1.0.0", lifespan=ciclo, docs_url="/api/docs",
                  openapi_url="/api/openapi.json", redoc_url=None,
                  description="Gestion de bodegas, inventario, lotes, QR, consumos y procesos productivos.")
    app.add_exception_handler(ErrorNegocio, manejar_error_negocio)

    @app.exception_handler(IntegrityError)
    async def _integridad(_: Request, exc: IntegrityError):
        return JSONResponse(status_code=409, content={
            "codigo": "INTEGRIDAD", "mensaje": "La operacion viola una restriccion de datos.", "datos": {}})

    @app.exception_handler(OperationalError)
    async def _operacional(_: Request, exc: OperationalError):
        log.exception("Error de base de datos")
        return JSONResponse(status_code=503, content={
            "codigo": "BD_NO_DISPONIBLE", "mensaje": "La base de datos no esta disponible. Reintente.", "datos": {}})

    if a.origenes_cors:
        app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in a.origenes_cors.split(",")],
                           allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def cabeceras(request: Request, call_next):
        r = await call_next(request)
        r.headers.setdefault("X-Content-Type-Options", "nosniff")
        r.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        r.headers.setdefault("Referrer-Policy", "same-origin")
        r.headers.setdefault("Permissions-Policy", "camera=(self)")
        if request.url.path.startswith("/api/"):
            r.headers.setdefault("Cache-Control", "no-store")
        return r

    for nombre in MODULOS:
        try:
            mod = importlib.import_module(f"app.modulos.{nombre}")
        except ModuleNotFoundError as e:
            if e.name != f"app.modulos.{nombre}":
                raise
            continue
        app.include_router(mod.router)

    @app.get("/api/salud", tags=["Sistema"])
    def salud():
        from app.modulos.instalacion import instalado
        return {"ok": True, "instalado": instalado(), "modo_demo": a.modo_demo}

    @app.get("/q/{token}", include_in_schema=False)
    def abrir_qr(token: str):
        """Destino de la URL impresa en el QR: abre la ficha de la existencia en el frontend."""
        return RedirectResponse(f"/existencia/?token={token}")

    if a.dir_frontend.exists():
        app.mount("/", StaticFiles(directory=a.dir_frontend, html=True), name="frontend")
    return app


app = crear_app()
