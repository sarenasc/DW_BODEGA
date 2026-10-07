"""Tareas internas (APScheduler): evaluacion de alertas y sincronizacion automatica de procesos abiertos."""
import logging
from datetime import timedelta

from sqlalchemy import select

from app.core import db as nucleo_db
from app.core.errores import ErrorNegocio
from app.core.util import ahora
from app.modelos import Empresa, FuenteIntegracion, Proceso

log = logging.getLogger("wms.tareas")


def tarea_alertas() -> dict:
    from app.servicios.alertas import evaluar_reglas
    totales = {"creadas": 0, "resueltas": 0}
    try:
        with nucleo_db.nueva_sesion() as s:
            empresas = list(s.scalars(select(Empresa.id).where(Empresa.activo.is_(True))))
        for empresa_id in empresas:
            with nucleo_db.nueva_sesion() as s, s.begin():
                r = evaluar_reglas(s, empresa_id)
            for k in totales:
                totales[k] += r[k]
    except Exception:
        log.exception("Fallo la evaluacion de alertas")
    return totales


def tarea_sincronizacion() -> int:
    """Actualiza los procesos ABIERTOS de las fuentes que definieron un intervalo. Una falla no detiene al resto."""
    from app.servicios.integracion import sincronizar_proceso
    hechos = 0
    try:
        with nucleo_db.nueva_sesion() as s:
            fuentes = [(f.id, f.intervalo_minutos) for f in s.scalars(select(FuenteIntegracion).where(
                FuenteIntegracion.activa.is_(True), FuenteIntegracion.intervalo_minutos > 0)).unique()]
            pendientes = []
            for fuente_id, minutos in fuentes:
                limite = ahora() - timedelta(minutes=minutos)
                pendientes += list(s.scalars(select(Proceso.id).where(
                    Proceso.fuente_id == fuente_id, Proceso.estado == "ABIERTO",
                    (Proceso.ultima_sincronizacion.is_(None)) | (Proceso.ultima_sincronizacion < limite))))
        for proceso_id in pendientes:
            with nucleo_db.nueva_sesion() as s:
                try:
                    sincronizar_proceso(s, None, s.get(Proceso, proceso_id), "ACTUALIZAR")
                    s.commit()
                    hechos += 1
                except ErrorNegocio:
                    pass  # el fallo ya quedo registrado como ejecucion con error y alerta
                except Exception:
                    s.rollback()
                    log.exception("Fallo la sincronizacion del proceso %s", proceso_id)
    except Exception:
        log.exception("Fallo la tarea de sincronizacion")
    return hechos
