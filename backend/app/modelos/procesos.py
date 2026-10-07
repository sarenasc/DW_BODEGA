"""Procesos productivos (copia local), integracion con la base productiva y alertas."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.util import ahora

from .base import Base, Cantidad, ConFechas, ConId

ESTADOS_PROCESO = ("BORRADOR", "ABIERTO", "CERRADO", "ANULADO")
BASES_COSTEO = ("kilos_procesados", "kilos_recepcionados", "kilos_producidos", "kilos_despachados")
# Campos internos disponibles como destino de un mapeo de integracion.
CAMPOS_PROCESO = (
    "codigo", "numero", "tipo", "fecha", "hora_inicio", "hora_termino", "temporada", "estado_externo", "exportadora",
    "productor", "codigo_productor", "campo", "predio", "especie", "variedad", "lote_productivo", "numero_lote",
    "kilos_recepcionados", "kilos_procesados", "kilos_producidos", "kilos_despachados", "cantidad", "bins", "cajas",
    "turno", "linea", "guia", "recepcion_relacionada",
)
CAMPOS_NUMERICOS = ("kilos_recepcionados", "kilos_procesados", "kilos_producidos", "kilos_despachados", "cantidad",
                    "bins", "cajas")


class Proceso(Base, ConId, ConFechas):
    __tablename__ = "procesos"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"), UniqueConstraint("fuente_id", "id_externo"))
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    fuente_id: Mapped[int | None] = mapped_column(ForeignKey("fuentes_integracion.id"))
    id_externo: Mapped[str | None] = mapped_column(String(80))
    codigo: Mapped[str] = mapped_column(String(40), index=True)
    numero: Mapped[str | None] = mapped_column(String(40))
    tipo: Mapped[str | None] = mapped_column(String(40))
    fecha: Mapped[date | None] = mapped_column(Date, index=True)
    hora_inicio: Mapped[str | None] = mapped_column(String(20))
    hora_termino: Mapped[str | None] = mapped_column(String(20))
    temporada_id: Mapped[int | None] = mapped_column(ForeignKey("temporadas.id"), index=True)
    temporada: Mapped[str | None] = mapped_column(String(20))  # texto tal como llega del origen
    estado: Mapped[str] = mapped_column(String(10), default="BORRADOR", index=True)
    estado_externo: Mapped[str | None] = mapped_column(String(40))
    exportadora: Mapped[str | None] = mapped_column(String(120), index=True)
    productor: Mapped[str | None] = mapped_column(String(150), index=True)
    codigo_productor: Mapped[str | None] = mapped_column(String(40))
    campo: Mapped[str | None] = mapped_column(String(120))
    predio: Mapped[str | None] = mapped_column(String(120))
    especie: Mapped[str | None] = mapped_column(String(80), index=True)
    variedad: Mapped[str | None] = mapped_column(String(80))
    lote_productivo: Mapped[str | None] = mapped_column(String(80))
    numero_lote: Mapped[str | None] = mapped_column(String(40))
    kilos_recepcionados: Mapped[Decimal | None] = mapped_column(Cantidad)
    kilos_procesados: Mapped[Decimal | None] = mapped_column(Cantidad)
    kilos_producidos: Mapped[Decimal | None] = mapped_column(Cantidad)
    kilos_despachados: Mapped[Decimal | None] = mapped_column(Cantidad)
    cantidad: Mapped[Decimal | None] = mapped_column(Cantidad)
    bins: Mapped[Decimal | None] = mapped_column(Cantidad)
    cajas: Mapped[Decimal | None] = mapped_column(Cantidad)
    turno: Mapped[str | None] = mapped_column(String(40))
    linea: Mapped[str | None] = mapped_column(String(40))
    guia: Mapped[str | None] = mapped_column(String(40))
    recepcion_relacionada: Mapped[str | None] = mapped_column(String(60))
    datos_adicionales: Mapped[dict | None] = mapped_column(JSON)
    # Base de costeo propia; NULL = usar la configuracion general.
    base_costeo: Mapped[str | None] = mapped_column(String(40))
    estado_kilos: Mapped[str] = mapped_column(String(12), default="PROVISORIO")  # PROVISORIO | DEFINITIVO
    kilos_definitivos: Mapped[Decimal | None] = mapped_column(Cantidad)
    ultima_sincronizacion: Mapped[datetime | None] = mapped_column(DateTime)
    abierto_en: Mapped[datetime | None] = mapped_column(DateTime)
    abierto_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cerrado_en: Mapped[datetime | None] = mapped_column(DateTime)
    cerrado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    modo_cierre: Mapped[str | None] = mapped_column(String(15))  # SINCRONIZADO | MANUAL
    cerrado_sincronizado: Mapped[bool | None] = mapped_column(Boolean)
    observaciones: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0)


class CapturaProceso(Base, ConId):
    """Snapshot crudo de cada lectura del origen, para auditoria."""
    __tablename__ = "capturas_procesos"
    proceso_id: Mapped[int] = mapped_column(ForeignKey("procesos.id", ondelete="CASCADE"), index=True)
    ejecucion_id: Mapped[int | None] = mapped_column(ForeignKey("ejecuciones_sincronizacion.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    datos: Mapped[dict] = mapped_column(JSON)


class CambioProceso(Base, ConId):
    __tablename__ = "cambios_procesos"
    proceso_id: Mapped[int] = mapped_column(ForeignKey("procesos.id", ondelete="CASCADE"), index=True)
    campo: Mapped[str] = mapped_column(String(60))
    valor_anterior: Mapped[str | None] = mapped_column(String(300))
    valor_nuevo: Mapped[str | None] = mapped_column(String(300))
    origen: Mapped[str] = mapped_column(String(15), default="SINCRONIZACION")  # SINCRONIZACION | MANUAL
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    ejecucion_id: Mapped[int | None] = mapped_column(ForeignKey("ejecuciones_sincronizacion.id"))


class ConexionIntegracion(Base, ConId, ConFechas):
    __tablename__ = "conexiones_integracion"
    __table_args__ = (UniqueConstraint("empresa_id", "nombre"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    nombre: Mapped[str] = mapped_column(String(80))
    motor: Mapped[str] = mapped_column(String(15))  # sqlserver | postgresql | mysql | demo
    servidor: Mapped[str | None] = mapped_column(String(150))
    puerto: Mapped[int | None] = mapped_column(Integer)
    base_datos: Mapped[str | None] = mapped_column(String(100))
    usuario: Mapped[str | None] = mapped_column(String(100))
    clave_cifrada: Mapped[str | None] = mapped_column(Text)  # nunca se devuelve por la API
    parametros: Mapped[dict | None] = mapped_column(JSON)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)


class FuenteIntegracion(Base, ConId, ConFechas):
    __tablename__ = "fuentes_integracion"
    conexion_id: Mapped[int] = mapped_column(ForeignKey("conexiones_integracion.id", ondelete="CASCADE"))
    nombre: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(10), default="CONSULTA")  # VISTA | CONSULTA
    # Para VISTA: nombre de la vista. Para CONSULTA: un SELECT.
    origen: Mapped[str] = mapped_column(Text)
    columna_id: Mapped[str] = mapped_column(String(80))
    columna_fecha: Mapped[str | None] = mapped_column(String(80))
    intervalo_minutos: Mapped[int | None] = mapped_column(Integer)  # sincronizacion automatica de procesos abiertos
    guardar_no_mapeadas: Mapped[bool] = mapped_column(Boolean, default=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    conexion: Mapped[ConexionIntegracion] = relationship(lazy="joined")
    mapeos: Mapped[list["MapeoIntegracion"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class MapeoIntegracion(Base, ConId):
    __tablename__ = "mapeos_integracion"
    __table_args__ = (UniqueConstraint("fuente_id", "campo_interno"),)
    fuente_id: Mapped[int] = mapped_column(ForeignKey("fuentes_integracion.id", ondelete="CASCADE"), index=True)
    columna_externa: Mapped[str] = mapped_column(String(80))
    # Campo conocido del proceso o "extra.<clave>" para datos adicionales.
    campo_interno: Mapped[str] = mapped_column(String(80))
    transformacion: Mapped[str | None] = mapped_column(String(30))  # RECORTAR MAYUSCULAS NUMERO FECHA
    factor: Mapped[Decimal | None] = mapped_column(Cantidad)
    politica_actualizacion: Mapped[str] = mapped_column(String(15), default="SIEMPRE")  # SIEMPRE SOLO_IMPORTAR MANUAL


class EjecucionSincronizacion(Base, ConId):
    __tablename__ = "ejecuciones_sincronizacion"
    fuente_id: Mapped[int | None] = mapped_column(ForeignKey("fuentes_integracion.id", ondelete="SET NULL"))
    proceso_id: Mapped[int | None] = mapped_column(Integer)
    accion: Mapped[str] = mapped_column(String(15), default="ACTUALIZAR")  # LISTAR IMPORTAR ACTUALIZAR CIERRE
    inicio: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    termino: Mapped[datetime | None] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(String(10), default="OK")  # OK | ERROR
    filas: Mapped[int] = mapped_column(Integer, default=0)
    cambios: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))


TIPOS_ALERTA = (
    "STOCK_BAJO", "STOCK_CRITICO", "STOCK_AGOTADO", "PRODUCTO_VENCIDO", "PROXIMO_A_VENCER", "STOCK_ANTIGUO",
    "CONSUMO_FUERA_FIFO", "LOTE_BLOQUEADO", "LOTE_CUARENTENA", "PROCESO_SIN_SINCRONIZAR",
    "PROCESO_CERRADO_SIN_SINCRONIZACION", "PRESTAMO_VENCIDO", "RESERVA_VENCIDA", "DIFERENCIA_INVENTARIO",
    "ERROR_SINCRONIZACION", "OTRA",
)
SEVERIDADES = ("INFORMATIVA", "BAJA", "MEDIA", "ALTA", "CRITICA")
ESTADOS_ALERTA = ("NUEVA", "LEIDA", "EN_GESTION", "RESUELTA", "DESCARTADA")


class ReglaAlerta(Base, ConId, ConFechas):
    __tablename__ = "reglas_alertas"
    __table_args__ = (UniqueConstraint("empresa_id", "tipo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    tipo: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(100))
    activa: Mapped[bool] = mapped_column(Boolean, default=True)
    severidad: Mapped[str] = mapped_column(String(12), default="MEDIA")
    parametros: Mapped[dict | None] = mapped_column(JSON)  # p. ej. {"dias": 30}
    canales: Mapped[list | None] = mapped_column(JSON)  # reservado: EMAIL TEAMS TELEGRAM WHATSAPP


class Alerta(Base, ConId):
    __tablename__ = "alertas"
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    severidad: Mapped[str] = mapped_column(String(12), default="MEDIA")
    titulo: Mapped[str] = mapped_column(String(200))
    descripcion: Mapped[str | None] = mapped_column(Text)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime)
    entidad: Mapped[str | None] = mapped_column(String(40))
    entidad_id: Mapped[int | None] = mapped_column(Integer)
    # Evita duplicar la misma alerta mientras siga abierta.
    clave: Mapped[str] = mapped_column(String(120), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    bodega_id: Mapped[int | None] = mapped_column(ForeignKey("bodegas.id"))
    estado: Mapped[str] = mapped_column(String(12), default="NUEVA", index=True)
    resuelta_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_resolucion: Mapped[datetime | None] = mapped_column(DateTime)
    observacion: Mapped[str | None] = mapped_column(String(500))
    notificada: Mapped[bool] = mapped_column(Boolean, default=False)
