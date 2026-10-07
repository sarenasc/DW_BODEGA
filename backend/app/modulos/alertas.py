"""Centro de alertas: bandeja persistente, gestion de estados y reglas configurables."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.crud import paginar
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict, ahora
from app.modelos import ESTADOS_ALERTA, SEVERIDADES, TIPOS_ALERTA, Alerta, Bodega, ReglaAlerta, Usuario
from app.servicios.alertas import ABIERTAS, CANALES, crear_alerta, evaluar_reglas

router = APIRouter(prefix="/api", tags=["Alertas"])
# Hacia donde navegar desde la alerta: entidad -> ruta del frontend.
RUTAS = {"producto": "/productos/detalle/?id=", "lote": "/lotes/detalle/?id=", "existencia": "/existencia/?id=",
         "proceso": "/procesos/detalle/?id=", "prestamo": "/prestamos/?id=", "reserva": "/reservas/?id=",
         "movimiento": "/movimientos/?id=", "conteo": "/conteos/detalle/?id=", "fuente": "/integraciones/"}


def _alcance(c, ctx: Contexto):
    c = c.where(Alerta.empresa_id == ctx.empresa_id)
    if ctx.bodegas is not None:
        c = c.where((Alerta.bodega_id.is_(None)) | (Alerta.bodega_id.in_(ctx.bodegas)))
    return c


def alerta_dict(db: Session, a: Alerta, nombres: dict | None = None) -> dict:
    nombres = nombres or {}
    return a_dict(a, excluir=("clave",), enlace=(RUTAS[a.entidad] + str(a.entidad_id)) if a.entidad in RUTAS and a.entidad_id else None,
                  bodega=db.get(Bodega, a.bodega_id).nombre if a.bodega_id else None,
                  resuelta_por_nombre=nombres.get(a.resuelta_por), abierta=a.estado in ABIERTAS)


@router.get("/alertas")
def listar(estado: str | None = None, tipo: str | None = None, severidad: str | None = None, abiertas: bool | None = None,
           bodega_id: int | None = None, entidad: str | None = None, entidad_id: int | None = None,
           pagina: int = Query(1, ge=1), tam: int = Query(50, le=500), db: Session = Depends(get_db),
           ctx: Contexto = Depends(requiere("alertas:ver"))):
    c = _alcance(select(Alerta), ctx)
    for col, val in ((Alerta.estado, estado), (Alerta.tipo, tipo), (Alerta.severidad, severidad), (Alerta.bodega_id, bodega_id),
                     (Alerta.entidad, entidad), (Alerta.entidad_id, entidad_id)):
        if val:
            c = c.where(col == val)
    if abiertas is True:
        c = c.where(Alerta.estado.in_(ABIERTAS))
    elif abiertas is False:
        c = c.where(Alerta.estado.not_in(ABIERTAS))
    nombres = dict(db.execute(select(Usuario.id, Usuario.nombre)).all())
    return paginar(db, c.order_by(Alerta.id.desc()), pagina, tam, lambda a: alerta_dict(db, a, nombres))


def resumen_alertas(db: Session, ctx: Contexto) -> dict:
    """Contadores para el dashboard y la campana de la barra superior."""
    base = _alcance(select(Alerta.tipo, Alerta.severidad, Alerta.estado, func.count()), ctx).where(Alerta.estado.in_(ABIERTAS)) \
        .group_by(Alerta.tipo, Alerta.severidad, Alerta.estado)
    por_tipo, por_severidad, nuevas, total = {}, {}, 0, 0
    for tipo, sev, estado, n in db.execute(base):
        por_tipo[tipo] = por_tipo.get(tipo, 0) + n
        por_severidad[sev] = por_severidad.get(sev, 0) + n
        total += n
        nuevas += n if estado == "NUEVA" else 0
    return {"abiertas": total, "nuevas": nuevas, "criticas": por_severidad.get("CRITICA", 0), "por_tipo": por_tipo,
            "por_severidad": por_severidad,
            "stock_bajo": por_tipo.get("STOCK_BAJO", 0) + por_tipo.get("STOCK_CRITICO", 0) + por_tipo.get("STOCK_AGOTADO", 0),
            "proximos_a_vencer": por_tipo.get("PROXIMO_A_VENCER", 0), "vencidos": por_tipo.get("PRODUCTO_VENCIDO", 0),
            "fuera_de_fifo": por_tipo.get("CONSUMO_FUERA_FIFO", 0), "reservas_vencidas": por_tipo.get("RESERVA_VENCIDA", 0),
            "procesos_sin_sincronizar": por_tipo.get("PROCESO_SIN_SINCRONIZAR", 0) + por_tipo.get("PROCESO_CERRADO_SIN_SINCRONIZACION", 0)}


@router.get("/alertas/resumen")
def resumen(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:ver"))):
    return resumen_alertas(db, ctx)


@router.get("/alertas/opciones")
def opciones(_: Contexto = Depends(requiere("alertas:ver"))):
    return {"tipos": TIPOS_ALERTA, "severidades": SEVERIDADES, "estados": ESTADOS_ALERTA, "canales_disponibles": sorted(CANALES)}


class CambioEstado(BaseModel):
    estado: str
    observacion: str | None = None


@router.post("/alertas/{id_}/estado")
def cambiar_estado(id_: int, d: CambioEstado, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:ver"))):
    a = db.scalar(_alcance(select(Alerta), ctx).where(Alerta.id == id_))
    if not a:
        raise no_encontrado("Alerta")
    if d.estado not in ESTADOS_ALERTA:
        raise ErrorNegocio("ESTADO", f"Estado no valido. Opciones: {', '.join(ESTADOS_ALERTA)}")
    if d.estado != "LEIDA":  # marcar como leida solo requiere poder verla
        ctx.exigir("alertas:gestionar")
    if d.estado in ("RESUELTA", "DESCARTADA") and not (d.observacion or "").strip():
        raise ErrorNegocio("OBSERVACION", "Indique una observacion al resolver o descartar.")
    antes = a.estado
    if antes == "NUEVA" or d.estado != "LEIDA":
        a.estado = d.estado
    if d.observacion:
        a.observacion = d.observacion[:500]
    if d.estado in ("RESUELTA", "DESCARTADA"):
        a.resuelta_por, a.fecha_resolucion = ctx.usuario.id, ahora()
    else:
        a.resuelta_por = a.fecha_resolucion = None
    auditar(db, ctx, "alerta", a.id, "CAMBIAR_ESTADO", anterior={"estado": antes}, nuevo={"estado": a.estado}, motivo=d.observacion)
    return alerta_dict(db, a)


class AlertaManual(BaseModel):
    titulo: str
    descripcion: str | None = None
    severidad: str = "MEDIA"
    bodega_id: int | None = None
    entidad: str | None = None
    entidad_id: int | None = None


@router.post("/alertas", status_code=201)
def crear(d: AlertaManual, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:gestionar"))):
    if d.severidad not in SEVERIDADES:
        raise ErrorNegocio("SEVERIDAD", "Severidad no valida.")
    a = crear_alerta(db, ctx.empresa_id, "OTRA", d.titulo, d.descripcion, entidad=d.entidad, entidad_id=d.entidad_id,
                     clave=f"OTRA:{ahora().timestamp()}", bodega_id=d.bodega_id, usuario_id=ctx.usuario.id, severidad=d.severidad)
    return alerta_dict(db, a)


@router.post("/alertas/evaluar")
def evaluar(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:gestionar"))):
    """Ejecuta ahora la evaluacion de reglas (el planificador la corre periodicamente)."""
    return evaluar_reglas(db, ctx.empresa_id)


# ---- reglas

class ReglaEntrada(BaseModel):
    activa: bool | None = None
    severidad: str | None = None
    parametros: dict | None = None
    canales: list[str] | None = None
    nombre: str | None = None


@router.get("/reglas-alertas")
def reglas(db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:ver"))):
    return [a_dict(r) for r in db.scalars(select(ReglaAlerta).where(ReglaAlerta.empresa_id == ctx.empresa_id).order_by(ReglaAlerta.id))]


@router.put("/reglas-alertas/{id_}")
def editar_regla(id_: int, d: ReglaEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("alertas:configurar"))):
    r = db.get(ReglaAlerta, id_)
    if not r or r.empresa_id != ctx.empresa_id:
        raise no_encontrado("Regla")
    if d.severidad and d.severidad not in SEVERIDADES:
        raise ErrorNegocio("SEVERIDAD", "Severidad no valida.")
    for clave, valor in (d.parametros or {}).items():
        if not isinstance(valor, (int, float)) or valor < 0:
            raise ErrorNegocio("PARAMETRO", f"El parametro {clave} debe ser un numero mayor o igual a cero.")
    antes = a_dict(r)
    for k, v in d.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(r, k, v)
    auditar(db, ctx, "regla_alerta", r.id, "EDITAR", anterior=antes, nuevo=r)
    return a_dict(r)
