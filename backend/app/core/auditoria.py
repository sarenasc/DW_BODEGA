"""Registro de auditoria y correlativos de sistema."""
from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modelos import Auditoria, Secuencia

from .util import a_dict, json_valor


def _limpio(valor):
    if valor is None:
        return None
    if hasattr(valor, "__table__"):
        valor = a_dict(valor, excluir=("clave_hash", "clave_cifrada", "token_qr"))
    if isinstance(valor, dict):
        return {k: json_valor(v) for k, v in valor.items() if k not in ("clave", "clave_hash", "clave_cifrada")}
    return {"valor": json_valor(valor)}


def auditar(db: Session, ctx, entidad: str, entidad_id, accion: str, anterior=None, nuevo=None, motivo: str | None = None):
    """ctx puede ser un Contexto o None (tareas de sistema)."""
    db.add(Auditoria(
        empresa_id=getattr(ctx, "empresa_id", None) if ctx else None,
        usuario_id=ctx.usuario.id if ctx else None,
        ip=getattr(ctx, "ip", None), dispositivo=getattr(ctx, "dispositivo", None),
        entidad=entidad, entidad_id=None if entidad_id is None else str(entidad_id), accion=accion,
        valor_anterior=_limpio(anterior), valor_nuevo=_limpio(nuevo), motivo=motivo,
    ))


def incrementar(db: Session, tabla, filtro: dict, columna: str = "ultimo_valor") -> int:
    """Correlativo transaccional portable: el UPDATE toma el bloqueo de fila hasta el commit."""
    t = tabla.__table__
    cond = [t.c[k] == v for k, v in filtro.items()]
    for _ in range(3):
        r = db.execute(update(t).where(*cond).values({columna: t.c[columna] + 1}))
        if r.rowcount:
            return db.scalar(select(t.c[columna]).where(*cond))
        try:
            with db.begin_nested():
                db.execute(insert(t).values(**filtro, **{columna: 1}))
            return 1
        except IntegrityError:
            continue  # otra transaccion creo la fila: reintentar el UPDATE
    raise RuntimeError("No fue posible obtener el correlativo.")


def siguiente_numero(db: Session, empresa_id: int, clave: str, prefijo: str, largo: int = 9) -> str:
    n = incrementar(db, Secuencia, {"empresa_id": empresa_id, "clave": clave})
    return f"{prefijo}-{n:0{largo}d}"
