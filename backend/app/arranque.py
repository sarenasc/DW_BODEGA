"""Tareas de arranque: migraciones, preparacion del modo demo y planificador interno."""
import logging

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.core.migraciones import migrar

log = logging.getLogger("wms")
_planificador = None


def preparar_demo() -> None:
    """Crea la base SQLite del demo con datos ficticios si aun no existe."""
    from app.modelos import Empresa
    from app.semilla.demo import crear_demo
    url = nucleo_db.url_activa()
    migrar(url)
    with nucleo_db.nueva_sesion() as s, s.begin():
        if s.scalar(select(Empresa.id).limit(1)) is None:
            log.info("Cargando datos de demostracion...")
            crear_demo(s)


def al_iniciar() -> None:
    a = ajustes()
    url = nucleo_db.url_activa()
    if not url:
        log.warning("Sistema sin instalar: abra el asistente de instalacion.")
        return
    try:
        if a.modo_demo and not nucleo_db.leer_config_instancia() and not a.url_bd:
            preparar_demo()
        elif inspect(nucleo_db.motor()).has_table("empresas"):
            migrar(url)  # aplica migraciones pendientes tras una actualizacion
    except Exception:
        log.exception("No fue posible preparar la base de datos")
        return
    if a.planificador:
        iniciar_planificador()


def iniciar_planificador() -> None:
    """APScheduler en proceso: alertas, vencimientos y sincronizacion de procesos abiertos."""
    global _planificador
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        from app.tareas import tarea_alertas, tarea_sincronizacion
    except ModuleNotFoundError:
        return
    _planificador = BackgroundScheduler(timezone="UTC")
    _planificador.add_job(tarea_alertas, "interval", minutes=30, id="alertas", max_instances=1, coalesce=True)
    _planificador.add_job(tarea_sincronizacion, "interval", minutes=5, id="sincronizacion", max_instances=1, coalesce=True)
    _planificador.start()


def al_detener() -> None:
    if _planificador:
        _planificador.shutdown(wait=False)
    nucleo_db.reiniciar_motor()


__all__ = ["al_iniciar", "al_detener", "preparar_demo", "Session"]
