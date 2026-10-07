"""Lectura de parametros generales: el valor de la empresa prevalece sobre el global."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Configuracion


def parametro(db: Session, clave: str, empresa_id: int | None = None, defecto=None):
    filas = db.scalars(select(Configuracion).where(Configuracion.clave == clave)).all()
    propio = next((f for f in filas if empresa_id is not None and f.empresa_id == empresa_id), None)
    general = next((f for f in filas if f.empresa_id is None), None)
    elegido = propio or general
    return defecto if elegido is None or elegido.valor is None else elegido.valor


def fijar_parametro(db: Session, clave: str, valor, empresa_id: int | None = None) -> Configuracion:
    fila = db.scalar(select(Configuracion).where(Configuracion.clave == clave, Configuracion.empresa_id == empresa_id)
                     if empresa_id is not None else
                     select(Configuracion).where(Configuracion.clave == clave, Configuracion.empresa_id.is_(None)))
    if fila is None:
        fila = Configuracion(empresa_id=empresa_id, clave=clave)
        db.add(fila)
    fila.valor = valor
    db.flush()
    return fila
