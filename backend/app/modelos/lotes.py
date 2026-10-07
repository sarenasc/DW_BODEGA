"""Plantillas de lote versionadas, contadores y lotes internos."""
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.util import ahora

from .base import Base, ConFechas, ConId

MODOS_LOTE = ("AUTOMATICO", "SEMIAUTOMATICO", "MANUAL")
MOMENTOS_LOTE = ("AL_CREAR_RECEPCION", "AL_CONFIRMAR_RECEPCION", "AL_INGRESAR_BODEGA", "AL_IMPRIMIR_QR",
                 "AL_CREAR_PROCESO", "MANUAL")
REINICIOS = ("NUNCA", "DIARIO", "MENSUAL", "ANUAL", "TEMPORADA", "MANUAL")
ESTADOS_LOTE = ("DISPONIBLE", "BLOQUEADO", "CUARENTENA", "VENCIDO", "AGOTADO", "ANULADO")


class PlantillaLote(Base, ConId, ConFechas):
    __tablename__ = "plantillas_lotes"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(30))
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(250))
    modo: Mapped[str] = mapped_column(String(15), default="AUTOMATICO")
    momento_creacion: Mapped[str] = mapped_column(String(25), default="AL_CONFIRMAR_RECEPCION")
    activa: Mapped[bool] = mapped_column(Boolean, default=False)
    versiones: Mapped[list["VersionPlantillaLote"]] = relationship(
        back_populates="plantilla", order_by="VersionPlantillaLote.version", lazy="selectin")


class VersionPlantillaLote(Base, ConId):
    __tablename__ = "versiones_plantillas_lotes"
    __table_args__ = (UniqueConstraint("plantilla_id", "version"),)
    plantilla_id: Mapped[int] = mapped_column(ForeignKey("plantillas_lotes.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(String(10), default="BORRADOR")  # BORRADOR | VIGENTE | RETIRADA
    vigente_desde: Mapped[datetime | None] = mapped_column(DateTime)
    vigente_hasta: Mapped[datetime | None] = mapped_column(DateTime)
    # Dimensiones que separan correlativos: EMPRESA BODEGA FAMILIA SUBFAMILIA PRODUCTO TEMPORADA PROCESO
    alcance: Mapped[list] = mapped_column(JSON, default=list)
    reinicio: Mapped[str] = mapped_column(String(10), default="NUNCA")
    epoca: Mapped[int] = mapped_column(Integer, default=0)  # reinicio manual
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    plantilla: Mapped[PlantillaLote] = relationship(back_populates="versiones")
    segmentos: Mapped[list["SegmentoPlantillaLote"]] = relationship(
        order_by="SegmentoPlantillaLote.posicion", cascade="all, delete-orphan", lazy="selectin")


class SegmentoPlantillaLote(Base, ConId):
    __tablename__ = "segmentos_plantillas_lotes"
    version_id: Mapped[int] = mapped_column(ForeignKey("versiones_plantillas_lotes.id", ondelete="CASCADE"), index=True)
    posicion: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(25))
    configuracion: Mapped[dict] = mapped_column(JSON, default=dict)


class ContadorLote(Base, ConId):
    __tablename__ = "contadores_lotes"
    __table_args__ = (UniqueConstraint("plantilla_id", "clave_alcance"),)
    plantilla_id: Mapped[int] = mapped_column(ForeignKey("plantillas_lotes.id", ondelete="CASCADE"))
    clave_alcance: Mapped[str] = mapped_column(String(200))
    ultimo_valor: Mapped[int] = mapped_column(Integer, default=0)


class Lote(Base, ConId, ConFechas):
    __tablename__ = "lotes"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(60), index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    version_plantilla_id: Mapped[int | None] = mapped_column(ForeignKey("versiones_plantillas_lotes.id"))
    lote_padre_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"), index=True)
    fecha_creacion: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_ingreso: Mapped[datetime | None] = mapped_column(DateTime)
    fecha_fabricacion: Mapped[date | None] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date, index=True)
    estado: Mapped[str] = mapped_column(String(12), default="DISPONIBLE", index=True)
    # Dato documental opcional: no participa en FIFO, QR ni trazabilidad principal.
    referencia_externa: Mapped[str | None] = mapped_column(String(80))
    documento_origen_id: Mapped[int | None] = mapped_column(Integer)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    observaciones: Mapped[str | None] = mapped_column(Text)
    producto = relationship("Producto", lazy="joined")


class HistorialEstadoLote(Base, ConId):
    __tablename__ = "historial_estados_lotes"
    lote_id: Mapped[int] = mapped_column(ForeignKey("lotes.id", ondelete="CASCADE"), index=True)
    estado_anterior: Mapped[str | None] = mapped_column(String(12))
    estado_nuevo: Mapped[str] = mapped_column(String(12))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    motivo: Mapped[str | None] = mapped_column(String(300))
