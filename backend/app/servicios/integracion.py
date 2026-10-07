"""Integracion con la base productiva: lectura de solo lectura, mapeo de columnas, snapshots y auditoria de cambios.

La base productiva es unicamente una fuente de sincronizacion: la operacion trabaja sobre la copia local.
Nada se asume del origen: vista o consulta, columna identificadora y mapeo los define el administrador.
"""
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import column, create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.core.errores import ErrorNegocio
from app.core.seguridad import descifrar
from app.core.util import ahora, json_valor
from app.modelos import (CAMPOS_NUMERICOS, CAMPOS_PROCESO, CambioProceso, CapturaProceso, ConexionIntegracion,
                         EjecucionSincronizacion, FuenteIntegracion, Proceso, Temporada)

PROHIBIDAS = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|merge|exec|execute|grant|revoke|call|into|"
                        r"attach|pragma|copy|backup|restore|shutdown|xp_\w+|sp_\w+)\b", re.I)
IDENTIFICADOR = re.compile(r"^[A-Za-z_\[\"`][\w.\[\]\"` ]{0,120}$")
LIMITE_FILAS = 500


def validar_origen(tipo: str, origen: str) -> str:
    """Solo se admite un SELECT unico (o el nombre de una vista). Segunda barrera: el usuario de BD debe ser de solo lectura."""
    origen = (origen or "").strip().rstrip(";").strip()
    if not origen:
        raise ErrorNegocio("ORIGEN", "Debe indicar la vista o la consulta.")
    if tipo == "VISTA":
        if not IDENTIFICADOR.match(origen) or PROHIBIDAS.search(origen):
            raise ErrorNegocio("ORIGEN", "Nombre de vista no valido.")
        return origen
    sin_comentarios = re.sub(r"--[^\n]*|/\*.*?\*/", " ", origen, flags=re.S)
    if ";" in sin_comentarios:
        raise ErrorNegocio("ORIGEN", "La consulta debe ser una sola sentencia SELECT (sin punto y coma).")
    if not re.match(r"^\s*(select|with)\b", sin_comentarios, re.I):
        raise ErrorNegocio("ORIGEN", "La consulta debe comenzar con SELECT.")
    if (m := PROHIBIDAS.search(sin_comentarios)):
        raise ErrorNegocio("ORIGEN", f"La consulta contiene una instruccion no permitida: {m.group(0).upper()}.")
    return sin_comentarios.strip()


def validar_columna(nombre: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][\w ]{0,79}", nombre or ""):
        raise ErrorNegocio("COLUMNA", f"Nombre de columna no valido: {nombre!r}")
    return nombre


def motor_externo(con: ConexionIntegracion) -> Engine:
    """Motor de corta vida hacia el origen. Nunca se reutiliza para escribir."""
    if con.motor == "demo":
        ruta = ajustes().dir_instancia / (con.base_datos or "produccion_demo.db")
        if not ruta.exists():
            raise ErrorNegocio("ORIGEN_NO_DISPONIBLE", "La base productiva de demostracion no existe.", 502)
        return create_engine(f"sqlite:///{ruta.as_uri()}?mode=ro&uri=true")
    clave = descifrar(con.clave_cifrada) if con.clave_cifrada else ""
    url = nucleo_db.construir_url(con.motor, con.servidor or "", con.puerto, con.usuario or "", clave,
                                  con.base_datos or "", con.parametros or {})
    args = {"postgresql": {"connect_timeout": 10, "options": "-c statement_timeout=30000 -c default_transaction_read_only=on"},
            "mysql": {"connect_timeout": 10, "read_timeout": 30}, "sqlserver": {"timeout": 10}}[con.motor]
    return create_engine(url, connect_args=args, pool_pre_ping=True)


def _base(fuente: FuenteIntegracion):
    origen = validar_origen(fuente.tipo, fuente.origen)
    return text(f"({origen}) AS origen") if fuente.tipo == "CONSULTA" else text(origen)


def _ejecutar(fuente: FuenteIntegracion, consulta) -> list[dict]:
    eng = motor_externo(fuente.conexion)
    try:
        with eng.connect() as c:
            return [dict(f._mapping) for f in c.execute(consulta)]
    except ErrorNegocio:
        raise
    except Exception as e:
        raise ErrorNegocio("ORIGEN_NO_DISPONIBLE", f"No fue posible leer la base productiva: {str(e).splitlines()[0][:250]}", 502) from e
    finally:
        eng.dispose()


def probar_conexion(con: ConexionIntegracion) -> None:
    eng = motor_externo(con)
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:
        raise ErrorNegocio("ORIGEN_NO_DISPONIBLE", f"No fue posible conectar: {str(e).splitlines()[0][:250]}", 502) from e
    finally:
        eng.dispose()


def listar_origen(fuente: FuenteIntegracion, desde: date | None = None, limite: int = 200) -> list[dict]:
    c = select(text("*")).select_from(_base(fuente))
    if desde and fuente.columna_fecha:
        c = c.where(column(validar_columna(fuente.columna_fecha)) >= desde)
    if fuente.columna_fecha:
        c = c.order_by(column(validar_columna(fuente.columna_fecha)).desc())
    return _ejecutar(fuente, c.limit(min(limite, LIMITE_FILAS)))


def leer_origen(fuente: FuenteIntegracion, id_externo: str) -> dict | None:
    """El identificador viaja siempre como parametro enlazado."""
    col = column(validar_columna(fuente.columna_id))
    filas = _ejecutar(fuente, select(text("*")).select_from(_base(fuente)).where(col == id_externo).limit(2))
    if not filas:  # el identificador puede ser numerico en el origen
        try:
            filas = _ejecutar(fuente, select(text("*")).select_from(_base(fuente)).where(col == int(id_externo)).limit(2))
        except (ValueError, ErrorNegocio):
            filas = []
    return filas[0] if filas else None


def columnas_origen(fuente: FuenteIntegracion) -> list[str]:
    filas = _ejecutar(fuente, select(text("*")).select_from(_base(fuente)).limit(1))
    return list(filas[0].keys()) if filas else []


# ---------------------------------------------------------------- transformacion

def _numero(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, (int, float, Decimal)):
        return Decimal(str(valor))
    s = str(valor).strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ErrorNegocio("TRANSFORMACION", f"El valor {valor!r} no es numerico.") from e


def _fecha(valor) -> date | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    s = str(valor).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ErrorNegocio("TRANSFORMACION", f"El valor {valor!r} no es una fecha reconocible.")


def transformar(valor, campo: str, transformacion: str | None, factor) -> object:
    if isinstance(valor, str):
        valor = valor.strip()
    if campo in CAMPOS_NUMERICOS or transformacion == "NUMERO":
        n = _numero(valor)
        return n * Decimal(str(factor)) if n is not None and factor else n
    if campo == "fecha" or transformacion == "FECHA":
        return _fecha(valor)
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        valor = valor.isoformat()
    valor = str(valor)
    if transformacion == "MAYUSCULAS":
        valor = valor.upper()
    return valor


def mapear_fila(fuente: FuenteIntegracion, fila: dict) -> tuple[dict, dict, dict]:
    """Devuelve (campos del proceso, datos adicionales, politica por campo)."""
    por_minuscula = {k.lower(): k for k in fila}
    campos, extra, politicas = {}, {}, {}
    usadas = set()
    for m in fuente.mapeos:
        real = por_minuscula.get(m.columna_externa.lower())
        if real is None:
            continue
        usadas.add(real)
        if m.campo_interno.startswith("extra."):
            clave = m.campo_interno[6:]
            extra[clave] = json_valor(transformar(fila[real], clave, m.transformacion, m.factor))
            politicas[m.campo_interno] = m.politica_actualizacion
        elif m.campo_interno in CAMPOS_PROCESO:
            campos[m.campo_interno] = transformar(fila[real], m.campo_interno, m.transformacion, m.factor)
            politicas[m.campo_interno] = m.politica_actualizacion
    if fuente.guardar_no_mapeadas:
        for k, v in fila.items():
            if k not in usadas and k != fuente.columna_id:
                extra.setdefault(k, json_valor(v) if not isinstance(v, (bytes, bytearray)) else None)
    return campos, extra, politicas


def _texto(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return f"{v.normalize():f}"
    return str(json_valor(v))[:300]


def _iguales(a, b) -> bool:
    if isinstance(a, Decimal) or isinstance(b, Decimal):
        try:
            return (a is None and b is None) or (a is not None and b is not None and Decimal(str(a)) == Decimal(str(b)))
        except InvalidOperation:
            return False
    return (a if a != "" else None) == (b if b != "" else None)


def aplicar_fila(db: Session, proceso: Proceso, fuente: FuenteIntegracion, fila: dict, *, importando: bool, usuario_id,
                 ejecucion_id) -> int:
    """Actualiza los campos configurados y registra valor anterior y nuevo de cada cambio."""
    campos, extra, politicas = mapear_fila(fuente, fila)
    cambios = 0
    for campo, nuevo in campos.items():
        pol = politicas.get(campo, "SIEMPRE")
        if not importando and pol != "SIEMPRE":
            continue  # SOLO_IMPORTAR y MANUAL no se sobrescriben al actualizar
        anterior = getattr(proceso, campo)
        if campo in ("codigo",) and not importando:
            continue
        if _iguales(anterior, nuevo):
            continue
        if isinstance(nuevo, str):
            largo = Proceso.__table__.c[campo].type.length
            nuevo = nuevo[:largo] if largo else nuevo
        setattr(proceso, campo, nuevo)
        if not importando:
            db.add(CambioProceso(proceso_id=proceso.id, campo=campo, valor_anterior=_texto(anterior), valor_nuevo=_texto(nuevo),
                                 origen="SINCRONIZACION", usuario_id=usuario_id, ejecucion_id=ejecucion_id))
        cambios += 1
    previos = dict(proceso.datos_adicionales or {})
    nuevos = dict(previos)
    for clave, valor in extra.items():
        pol = politicas.get(f"extra.{clave}", "SIEMPRE")
        if not importando and pol != "SIEMPRE":
            continue
        if previos.get(clave) != valor:
            if not importando and f"extra.{clave}" in politicas:
                db.add(CambioProceso(proceso_id=proceso.id, campo=f"extra.{clave}", valor_anterior=_texto(previos.get(clave)),
                                     valor_nuevo=_texto(valor), origen="SINCRONIZACION", usuario_id=usuario_id,
                                     ejecucion_id=ejecucion_id))
                cambios += 1
            nuevos[clave] = valor
    proceso.datos_adicionales = nuevos
    # Temporada local: por codigo informado o por la fecha del proceso.
    if proceso.temporada_id is None or importando:
        t = None
        if proceso.temporada:
            t = db.scalar(select(Temporada).where(Temporada.empresa_id == proceso.empresa_id, Temporada.codigo == proceso.temporada))
        if t is None and proceso.fecha:
            t = db.scalar(select(Temporada).where(Temporada.empresa_id == proceso.empresa_id,
                                                  Temporada.fecha_inicio <= proceso.fecha, Temporada.fecha_termino >= proceso.fecha))
        if t is not None:
            proceso.temporada_id = t.id
    return cambios


def _registrar_fallo(db: Session, fuente_id: int, proceso: Proceso | None, accion: str, mensaje: str, usuario_id,
                     empresa_id: int) -> None:
    """Descarta lo hecho en la peticion y confirma solo el registro del fallo, para que sobreviva al error."""
    from .alertas import crear_alerta
    pid, codigo = (proceso.id, proceso.codigo) if proceso else (None, None)
    db.rollback()
    db.add(EjecucionSincronizacion(fuente_id=fuente_id, proceso_id=pid, accion=accion, termino=ahora(), estado="ERROR",
                                   error=mensaje[:1000], usuario_id=usuario_id))
    crear_alerta(db, empresa_id, "ERROR_SINCRONIZACION", f"Error de sincronizacion{': ' + codigo if codigo else ''}",
                 mensaje[:500], entidad="proceso" if pid else "fuente", entidad_id=pid or fuente_id,
                 clave=f"ERROR_SINCRONIZACION:{'proceso' if pid else 'fuente'}:{pid or fuente_id}")
    db.commit()


def sincronizar_proceso(db: Session, ctx, proceso: Proceso, accion: str = "ACTUALIZAR") -> dict:
    """Relee el proceso en el origen, guarda el snapshot crudo y aplica los cambios con auditoria."""
    if not proceso.fuente_id or not proceso.id_externo:
        raise ErrorNegocio("SIN_FUENTE", "El proceso fue creado manualmente: no tiene origen que sincronizar.")
    fuente = db.get(FuenteIntegracion, proceso.fuente_id)
    usuario_id, empresa_id = ctx.usuario.id if ctx else None, proceso.empresa_id
    try:
        fila = leer_origen(fuente, proceso.id_externo)
    except ErrorNegocio as e:
        _registrar_fallo(db, fuente.id, proceso, accion, e.mensaje, usuario_id, empresa_id)
        raise
    if fila is None:
        mensaje = f"El proceso {proceso.id_externo} ya no existe en la base productiva. La copia local se conserva."
        _registrar_fallo(db, fuente.id, proceso, accion, mensaje, usuario_id, empresa_id)
        raise ErrorNegocio("NO_EXISTE_EN_ORIGEN", mensaje, 409)
    ej = EjecucionSincronizacion(fuente_id=fuente.id, proceso_id=proceso.id, accion=accion, usuario_id=usuario_id, filas=1)
    db.add(ej)
    db.flush()
    db.add(CapturaProceso(proceso_id=proceso.id, ejecucion_id=ej.id,
                          datos={k: (json_valor(v) if not isinstance(v, (bytes, bytearray)) else None) for k, v in fila.items()}))
    ej.cambios = aplicar_fila(db, proceso, fuente, fila, importando=False, usuario_id=usuario_id, ejecucion_id=ej.id)
    ej.termino = proceso.ultima_sincronizacion = ahora()
    db.flush()
    # Una sincronizacion correcta resuelve los avisos pendientes del proceso.
    from app.modelos import Alerta
    for a in db.scalars(select(Alerta).where(Alerta.entidad == "proceso", Alerta.entidad_id == proceso.id,
                                             Alerta.tipo.in_(("ERROR_SINCRONIZACION", "PROCESO_SIN_SINCRONIZAR")),
                                             Alerta.estado.in_(("NUEVA", "LEIDA", "EN_GESTION")))):
        a.estado, a.fecha_resolucion, a.observacion = "RESUELTA", ahora(), "Sincronizacion correcta."
    return {"ejecucion_id": ej.id, "cambios": ej.cambios}


def importar_proceso(db: Session, ctx, fuente: FuenteIntegracion, id_externo: str, empresa_id: int) -> Proceso:
    """Copia el proceso a la base local. Desde aqui la operacion no depende del origen."""
    id_externo = str(id_externo).strip()
    existente = db.scalar(select(Proceso).where(Proceso.fuente_id == fuente.id, Proceso.id_externo == id_externo))
    if existente:
        raise ErrorNegocio("YA_IMPORTADO", f"El proceso {id_externo} ya fue importado como {existente.codigo}.", 409)
    fila = leer_origen(fuente, id_externo)
    if fila is None:
        raise ErrorNegocio("NO_EXISTE_EN_ORIGEN", f"El proceso {id_externo} no existe en la base productiva.", 404)
    usuario_id = ctx.usuario.id if ctx else None
    p = Proceso(empresa_id=empresa_id, fuente_id=fuente.id, id_externo=id_externo, codigo=f"EXT-{id_externo}"[:40], estado="BORRADOR")
    db.add(p)
    db.flush()
    ej = EjecucionSincronizacion(fuente_id=fuente.id, proceso_id=p.id, accion="IMPORTAR", usuario_id=usuario_id, filas=1)
    db.add(ej)
    db.flush()
    db.add(CapturaProceso(proceso_id=p.id, ejecucion_id=ej.id,
                          datos={k: (json_valor(v) if not isinstance(v, (bytes, bytearray)) else None) for k, v in fila.items()}))
    ej.cambios = aplicar_fila(db, p, fuente, fila, importando=True, usuario_id=usuario_id, ejecucion_id=ej.id)
    if db.scalar(select(Proceso.id).where(Proceso.empresa_id == empresa_id, Proceso.codigo == p.codigo, Proceso.id != p.id)):
        p.codigo = f"{p.codigo}-{p.id}"[:40]
    ej.termino = p.ultima_sincronizacion = ahora()
    db.flush()
    return p
