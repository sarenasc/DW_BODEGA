"""Generador de lotes internos: segmentos configurables, correlativo transaccional, validacion de plantillas."""
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import incrementar
from app.core.errores import ErrorNegocio
from app.core.util import ahora, hoy
from app.modelos import (ContadorLote, HistorialEstadoLote, Lote, PlantillaLote, Producto, VersionPlantillaLote)

from .catalogo import politica_efectiva

MESES = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE",
         "NOVIEMBRE", "DICIEMBRE"]
FORMATOS_FECHA = {"YYYYMMDD": "%Y%m%d", "DDMMYYYY": "%d%m%Y", "YYMMDD": "%y%m%d", "YYYY-MM-DD": "%Y-%m-%d",
                  "DD-MM-YYYY": "%d-%m-%Y"}
FORMATOS_FECHA_HORA = {"YYYYMMDDHHMM": "%Y%m%d%H%M", "YYMMDDHHMM": "%y%m%d%H%M", "YYYYMMDD-HHMM": "%Y%m%d-%H%M"}
TIPOS_CONTEXTO = ("PRODUCTO", "FAMILIA", "SUBFAMILIA", "BODEGA", "EMPRESA", "TEMPORADA", "USUARIO", "TURNO", "PROCESO")
TIPOS_SEGMENTO = ("TEXTO", "SEPARADOR", "ANIO", "MES", "DIA", "FECHA", "FECHA_HORA", "CORRELATIVO", "MANUAL") + TIPOS_CONTEXTO
DIMENSIONES_ALCANCE = ("EMPRESA", "BODEGA", "FAMILIA", "SUBFAMILIA", "PRODUCTO", "TEMPORADA", "PROCESO")
LARGO_MAXIMO = 60


@dataclass
class ContextoLote:
    fecha: datetime
    producto: str = ""
    familia: str = ""
    subfamilia: str = ""
    bodega: str = ""
    empresa: str = ""
    temporada: str = ""
    usuario: str = ""
    turno: str = ""
    proceso: str = ""
    manuales: dict = field(default_factory=dict)


def _texto_contexto(valor: str, cfg: dict) -> str:
    v = re.sub(r"[^A-Za-z0-9]", "", valor or "")
    if cfg.get("mayusculas", True):
        v = v.upper()
    return v[: int(cfg["largo"])] if cfg.get("largo") else v


def renderizar(segmentos: list, ctx: ContextoLote, correlativo: int | None) -> str:
    """Funcion pura: la vista previa y la generacion real usan exactamente este codigo."""
    partes = []
    for s in segmentos:
        tipo, cfg = (s["tipo"], s.get("configuracion") or {}) if isinstance(s, dict) else (s.tipo, s.configuracion or {})
        f = ctx.fecha
        if tipo in ("TEXTO", "SEPARADOR"):
            partes.append(str(cfg.get("valor", "-" if tipo == "SEPARADOR" else "")))
        elif tipo == "ANIO":
            partes.append(f.strftime("%y" if int(cfg.get("digitos", 4)) == 2 else "%Y"))
        elif tipo == "MES":
            fmt = cfg.get("formato", "NUMERO")
            partes.append(f"{f.month:02d}" if fmt == "NUMERO" else MESES[f.month - 1][:3] if fmt == "ABREV" else MESES[f.month - 1])
        elif tipo == "DIA":
            partes.append(f"{f.day:02d}")
        elif tipo == "FECHA":
            partes.append(f.strftime(FORMATOS_FECHA.get(cfg.get("formato", "YYYYMMDD"), "%Y%m%d")))
        elif tipo == "FECHA_HORA":
            partes.append(f.strftime(FORMATOS_FECHA_HORA.get(cfg.get("formato", "YYYYMMDDHHMM"), "%Y%m%d%H%M")))
        elif tipo == "CORRELATIVO":
            n = (correlativo or 1) + int(cfg.get("inicio", 1)) - 1
            partes.append(f"{n:0{int(cfg.get('largo', 4))}d}")
        elif tipo == "MANUAL":
            clave = cfg.get("clave") or cfg.get("etiqueta") or "manual"
            valor = str(ctx.manuales.get(clave, "") or "")
            if not valor and cfg.get("obligatorio", True):
                raise ErrorNegocio("CAMPO_MANUAL", f"Debe indicar el campo '{cfg.get('etiqueta', clave)}' del lote.",
                                   datos={"clave": clave})
            if valor and cfg.get("patron") and not re.fullmatch(cfg["patron"], valor):
                raise ErrorNegocio("CAMPO_MANUAL", f"El campo '{cfg.get('etiqueta', clave)}' no cumple el formato requerido.")
            partes.append(valor.upper() if cfg.get("mayusculas", True) else valor)
        elif tipo in TIPOS_CONTEXTO:
            partes.append(_texto_contexto(getattr(ctx, tipo.lower()), cfg))
        else:
            raise ErrorNegocio("SEGMENTO", f"Tipo de segmento desconocido: {tipo}")
    return "".join(partes)


def clave_alcance(alcance: list, reinicio: str, epoca: int, ctx: ContextoLote) -> str:
    """Identifica el contador. Al cambiar el periodo cambia la clave, por lo que el reinicio es implicito."""
    partes = [f"{d}={getattr(ctx, d.lower()) or '-'}" for d in DIMENSIONES_ALCANCE if d in (alcance or [])]
    f = ctx.fecha
    if reinicio == "DIARIO":
        partes.append(f"D={f:%Y%m%d}")
    elif reinicio == "MENSUAL":
        partes.append(f"M={f:%Y%m}")
    elif reinicio == "ANUAL":
        partes.append(f"A={f:%Y}")
    elif reinicio == "TEMPORADA":
        partes.append(f"T={ctx.temporada or '-'}")
    if epoca:
        partes.append(f"E={epoca}")
    return "|".join(partes) or "GLOBAL"


def _tiene(segmentos, tipo: str) -> bool:
    return any((s["tipo"] if isinstance(s, dict) else s.tipo) == tipo for s in segmentos)


def validar_plantilla(modo: str, segmentos: list[dict], alcance: list, reinicio: str) -> dict:
    """Genera ejemplos y detecta colisiones simulando productos, bodegas y cruces de periodo."""
    errores, advertencias, ejemplos = [], [], []
    tipos = [s["tipo"] for s in segmentos]
    if not segmentos:
        errores.append("La plantilla no tiene segmentos.")
    for t in tipos:
        if t not in TIPOS_SEGMENTO:
            errores.append(f"Tipo de segmento desconocido: {t}.")
    for d in alcance or []:
        if d not in DIMENSIONES_ALCANCE:
            errores.append(f"Dimension de alcance desconocida: {d}.")
    n_corr = tipos.count("CORRELATIVO")
    if n_corr > 1:
        errores.append("Solo se admite un segmento correlativo por plantilla.")
    if modo == "AUTOMATICO":
        if "MANUAL" in tipos:
            errores.append("El modo automatico no admite campos manuales: use el modo semiautomatico.")
        if n_corr == 0 and "FECHA_HORA" not in tipos:
            errores.append("El modo automatico requiere un correlativo (o fecha/hora) para garantizar unicidad.")
    if modo == "MANUAL" and not segmentos:
        errores.clear()  # una plantilla manual puede no tener formato: el usuario digita el lote
        return {"errores": [], "advertencias": ["Lote digitado libremente: la unicidad se valida al guardar."], "ejemplos": []}
    if errores:
        return {"errores": errores, "advertencias": advertencias, "ejemplos": ejemplos}

    base = datetime(hoy().year, 3, 14, 10, 30)
    fechas = [base, base + timedelta(minutes=1), base + timedelta(days=1), base.replace(month=4),
              base.replace(month=12, day=31), base.replace(year=base.year + 1, month=1, day=1), base.replace(year=base.year + 1)]
    variantes = [
        dict(producto="FUNGX", familia="FITO", subfamilia="FUNG", bodega="FIT", proceso="PROC0001", usuario="jperez"),
        dict(producto="INSEY", familia="FITO", subfamilia="INSE", bodega="FIT", proceso="PROC0001", usuario="jperez"),
        dict(producto="ROD6204", familia="MANT", subfamilia="RODA", bodega="MAN", proceso="PROC0002", usuario="mrojas"),
        dict(producto="FUNGX", familia="FITO", subfamilia="FUNG", bodega="MAN", proceso="PROC0002", usuario="mrojas"),
    ]
    contadores: dict[str, int] = {}
    vistos: dict[str, tuple] = {}
    colision = None
    for f in fechas:
        for v in variantes:
            temporada = f"{f.year}-{f.year + 1}" if f.month >= 7 else f"{f.year - 1}-{f.year}"
            ctx = ContextoLote(fecha=f, empresa="EMP", temporada=temporada, turno="A",
                               manuales={(s.get("configuracion") or {}).get("clave") or (s.get("configuracion") or {}).get("etiqueta") or "manual": "X1"
                                         for s in segmentos if s["tipo"] == "MANUAL"}, **v)
            clave = clave_alcance(alcance, reinicio, 0, ctx)
            for _ in range(2):
                n = contadores[clave] = contadores.get(clave, 0) + 1 if n_corr else 1
                try:
                    codigo = renderizar(segmentos, ctx, n)
                except ErrorNegocio as e:
                    return {"errores": [e.mensaje], "advertencias": advertencias, "ejemplos": ejemplos}
                if len(ejemplos) < 6 and codigo not in ejemplos:
                    ejemplos.append(codigo)
                identidad = (clave, n) if n_corr else (clave, f, tuple(v.items()))
                if codigo in vistos and vistos[codigo] != identidad and colision is None and n_corr:
                    colision = codigo
                vistos.setdefault(codigo, identidad)
                if not n_corr:
                    break
    if colision:
        causa = []
        if reinicio != "NUNCA":
            causa.append(f"el correlativo se reinicia ({reinicio.lower()}) pero el codigo no incluye ese periodo")
        if alcance:
            causa.append("el alcance separa correlativos por " + ", ".join(a.lower() for a in alcance) +
                         " y el codigo no refleja todas esas dimensiones")
        errores.append(f"Colision detectada: el codigo {colision} se generaria mas de una vez"
                       + (" porque " + " o ".join(causa) if causa else "") + ".")
    if any(len(e) > LARGO_MAXIMO for e in ejemplos):
        errores.append(f"El codigo supera los {LARGO_MAXIMO} caracteres.")
    for s in segmentos:
        cfg = s.get("configuracion") or {}
        if s["tipo"] == "CORRELATIVO" and int(cfg.get("largo", 4)) < 4:
            advertencias.append(f"Correlativo de {cfg.get('largo')} digitos: se desborda tras "
                                f"{10 ** int(cfg.get('largo', 4)) - 1} lotes por periodo.")
        if s["tipo"] == "MANUAL" and not cfg.get("patron"):
            advertencias.append(f"El campo manual '{cfg.get('etiqueta', 'manual')}' no tiene validacion de formato.")
    if modo != "AUTOMATICO" and n_corr == 0:
        advertencias.append("Sin correlativo: la unicidad depende de lo que digite el usuario.")
    return {"errores": errores, "advertencias": advertencias, "ejemplos": ejemplos}


def version_vigente(plantilla: PlantillaLote) -> VersionPlantillaLote | None:
    return next((v for v in reversed(plantilla.versiones) if v.estado == "VIGENTE"), None)


def generar_codigo(db: Session, version: VersionPlantillaLote, ctx: ContextoLote) -> str:
    """Obtiene el correlativo dentro de la transaccion en curso y arma el codigo."""
    n = None
    if _tiene(version.segmentos, "CORRELATIVO"):
        clave = clave_alcance(version.alcance, version.reinicio, version.epoca, ctx)
        n = incrementar(db, ContadorLote, {"plantilla_id": version.plantilla_id, "clave_alcance": clave})
    return renderizar(version.segmentos, ctx, n)


def calcular_vencimiento(politica: dict, manual: date | None, fabricacion: date | None) -> date | None:
    calculada = None
    if fabricacion and politica.get("vida_util_meses"):
        m = fabricacion.month - 1 + int(politica["vida_util_meses"])
        anio, mes = fabricacion.year + m // 12, m % 12 + 1
        dia = min(fabricacion.day, [31, 29 if anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0) else 28, 31, 30, 31,
                                    30, 31, 31, 30, 31, 30, 31][mes - 1])
        calculada = date(anio, mes, dia)
    if politica.get("prioridad_vencimiento") == "CALCULADA":
        return calculada or manual
    return manual or calculada


def crear_lote(db: Session, ctx, producto: Producto, *, bodega=None, fecha: datetime | None = None,
               codigo_manual: str | None = None, manuales: dict | None = None, fecha_fabricacion: date | None = None,
               fecha_vencimiento: date | None = None, referencia_externa: str | None = None, proceso_codigo: str = "",
               temporada: str = "", documento_id: int | None = None, lote_padre: Lote | None = None,
               politica: dict | None = None) -> Lote:
    """Crea el lote interno segun la plantilla asociada (producto -> subfamilia -> familia)."""
    from app.modelos import Empresa
    politica = politica or politica_efectiva(producto)
    fecha = fecha or ahora()
    codigo_manual = (codigo_manual or "").strip().upper() or None
    version = None
    plantilla = db.get(PlantillaLote, politica["plantilla_lote_id"]) if politica.get("plantilla_lote_id") else None
    if plantilla and plantilla.activa:
        version = version_vigente(plantilla)

    if lote_padre is not None:
        hermanos = db.scalars(select(Lote.codigo).where(Lote.lote_padre_id == lote_padre.id)).all()
        codigo = f"{lote_padre.codigo}-{len(hermanos) + 1:02d}"
        version = None
    elif version is None or plantilla.modo == "MANUAL" or (plantilla.modo == "SEMIAUTOMATICO" and codigo_manual):
        if not codigo_manual:
            raise ErrorNegocio("LOTE_REQUERIDO", f"Debe indicar el lote interno de {producto.nombre}: "
                                                 "el producto no tiene una plantilla de lote automatica.")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/\-]{0,59}", codigo_manual):
            raise ErrorNegocio("LOTE_INVALIDO", "El lote solo admite letras, numeros, punto, guion y barra.")
        codigo = codigo_manual
    else:
        sub = producto.subfamilia
        emp = db.get(Empresa, producto.empresa_id)
        cl = ContextoLote(fecha=fecha, producto=producto.codigo, familia=sub.familia.codigo, subfamilia=sub.codigo,
                          bodega=bodega.codigo if bodega else "", empresa=emp.codigo, temporada=temporada,
                          usuario=ctx.usuario.usuario if ctx else "", proceso=proceso_codigo, manuales=manuales or {})
        codigo = None
        for _ in range(20):  # si un lote manual ocupo el codigo, se avanza al siguiente correlativo
            candidato = generar_codigo(db, version, cl)
            if not db.scalar(select(Lote.id).where(Lote.empresa_id == producto.empresa_id, Lote.codigo == candidato)):
                codigo = candidato
                break
            if not _tiene(version.segmentos, "CORRELATIVO"):
                break
        if codigo is None:
            raise ErrorNegocio("LOTE_DUPLICADO", "No fue posible generar un lote unico con la plantilla vigente.", 409)

    if db.scalar(select(Lote.id).where(Lote.empresa_id == producto.empresa_id, Lote.codigo == codigo)):
        raise ErrorNegocio("LOTE_DUPLICADO", f"El lote {codigo} ya existe.", 409)
    vence = calcular_vencimiento(politica, fecha_vencimiento, fecha_fabricacion)
    if politica.get("usa_vencimiento") and vence is None:
        raise ErrorNegocio("VENCIMIENTO_REQUERIDO", f"{producto.nombre} requiere fecha de vencimiento "
                                                    "(o fecha de fabricacion y vida util configurada).")
    lote = Lote(empresa_id=producto.empresa_id, codigo=codigo, producto_id=producto.id,
                version_plantilla_id=version.id if version else None, lote_padre_id=lote_padre.id if lote_padre else None,
                fecha_creacion=ahora(), fecha_ingreso=fecha, fecha_fabricacion=fecha_fabricacion, fecha_vencimiento=vence,
                referencia_externa=referencia_externa, documento_origen_id=documento_id,
                usuario_id=ctx.usuario.id if ctx else None)
    lote.producto = producto
    db.add(lote)
    db.flush()
    db.add(HistorialEstadoLote(lote_id=lote.id, estado_nuevo="DISPONIBLE", usuario_id=lote.usuario_id, motivo="Creacion"))
    return lote


def cambiar_estado_lote(db: Session, ctx, lote: Lote, nuevo: str, motivo: str | None = None) -> None:
    if lote.estado == nuevo:
        return
    db.add(HistorialEstadoLote(lote_id=lote.id, estado_anterior=lote.estado, estado_nuevo=nuevo,
                               usuario_id=ctx.usuario.id if ctx else None, motivo=motivo))
    lote.estado = nuevo
