"""Documentos, existencias, libro de movimientos, reservas, conteos y prestamos."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.util import ahora

from .base import Base, Cantidad, ConFechas, ConId, Costo, Monto

ESTADOS_DOCUMENTO = ("BORRADOR", "CONFIRMADO", "ANULADO")
CLASES_DOCUMENTO = ("INGRESO", "SALIDA", "TRASLADO", "AJUSTE")
ESTADOS_EXISTENCIA = ("DISPONIBLE", "BLOQUEADA", "AGOTADA", "ANULADA")
ESTADOS_RESERVA = ("ACTIVA", "CONSUMIDA", "LIBERADA", "VENCIDA", "ANULADA")


class DocumentoInventario(Base, ConId, ConFechas):
    __tablename__ = "documentos_inventario"
    __table_args__ = (UniqueConstraint("empresa_id", "numero"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    numero: Mapped[str] = mapped_column(String(20))
    clase: Mapped[str] = mapped_column(String(10), index=True)
    motivo_id: Mapped[int | None] = mapped_column(ForeignKey("motivos_movimiento.id"))
    tipo_documento: Mapped[str | None] = mapped_column(String(20))  # FACTURA GUIA_DESPACHO GUIA_INTERNA OTRO
    numero_documento: Mapped[str | None] = mapped_column(String(40), index=True)
    fecha_documento: Mapped[date | None] = mapped_column(Date)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodegas.id"), index=True)
    bodega_destino_id: Mapped[int | None] = mapped_column(ForeignKey("bodegas.id"))
    proceso_id: Mapped[int | None] = mapped_column(ForeignKey("procesos.id"))
    temporada_id: Mapped[int | None] = mapped_column(ForeignKey("temporadas.id"))
    estado: Mapped[str] = mapped_column(String(10), default="BORRADOR", index=True)
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    observaciones: Mapped[str | None] = mapped_column(Text)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    confirmado_en: Mapped[datetime | None] = mapped_column(DateTime)
    confirmado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    anulado_en: Mapped[datetime | None] = mapped_column(DateTime)
    anulado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(300))
    detalles: Mapped[list["DetalleDocumentoInventario"]] = relationship(
        cascade="all, delete-orphan", order_by="DetalleDocumentoInventario.id", lazy="selectin")


class DetalleDocumentoInventario(Base, ConId):
    __tablename__ = "detalles_documentos_inventario"
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos_inventario.id", ondelete="CASCADE"), index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    # Cantidad tal como viene en el documento (p. ej. 2 bidones).
    cantidad: Mapped[Decimal] = mapped_column(Cantidad)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    precio_unitario: Mapped[Decimal | None] = mapped_column(Costo)
    # Equivalente en unidad base del producto (p. ej. 40 L).
    cantidad_base: Mapped[Decimal | None] = mapped_column(Cantidad)
    costo_unitario_base: Mapped[Decimal | None] = mapped_column(Costo)
    costo_total: Mapped[Decimal | None] = mapped_column(Monto)
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"))
    lote_manual: Mapped[str | None] = mapped_column(String(60))
    campos_lote: Mapped[str | None] = mapped_column(Text)  # JSON con valores de segmentos manuales
    referencia_externa: Mapped[str | None] = mapped_column(String(80))
    fecha_fabricacion: Mapped[date | None] = mapped_column(Date)
    fecha_vencimiento: Mapped[date | None] = mapped_column(Date)
    ubicacion_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    ubicacion_destino_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    existencia_id: Mapped[int | None] = mapped_column(ForeignKey("existencias.id", use_alter=True))  # salidas, traslados, ajustes
    # Cantidad de existencias (QR) a generar: envases en POR_ENVASE, unidades logisticas en UNIDAD_LOGISTICA.
    bultos: Mapped[int | None] = mapped_column(Integer)
    observaciones: Mapped[str | None] = mapped_column(String(300))


class Existencia(Base, ConId, ConFechas):
    """Cantidad fisica concreta de un producto/lote, con ubicacion, fecha de ingreso, costo y QR propios."""
    __tablename__ = "existencias"
    __table_args__ = (
        CheckConstraint("cantidad_fisica >= 0", name="fisica_no_negativa"),
        CheckConstraint("cantidad_inicial > 0", name="inicial_positiva"),
        CheckConstraint("costo_unitario >= 0", name="costo_no_negativo"),
        Index("ix_existencias_fifo", "producto_id", "bodega_id", "estado", "fecha_ingreso"),
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo_publico: Mapped[str] = mapped_column(String(20), unique=True)
    token_qr: Mapped[str] = mapped_column(String(40), unique=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"), index=True)
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodegas.id"))
    ubicacion_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"), index=True)
    detalle_origen_id: Mapped[int | None] = mapped_column(ForeignKey("detalles_documentos_inventario.id"))
    existencia_padre_id: Mapped[int | None] = mapped_column(ForeignKey("existencias.id"), index=True)
    granularidad: Mapped[str] = mapped_column(String(20), default="POR_ENVASE")
    envases: Mapped[int | None] = mapped_column(Integer)  # unidades fisicas que agrupa (consolidada / logistica)
    # Antiguedad para FIFO. Se hereda al dividir o trasladar.
    fecha_ingreso: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    cantidad_inicial: Mapped[Decimal] = mapped_column(Cantidad)
    cantidad_fisica: Mapped[Decimal] = mapped_column(Cantidad)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    costo_unitario: Mapped[Decimal] = mapped_column(Costo, default=0)  # inmutable
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    fecha_costo: Mapped[date | None] = mapped_column(Date)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    estado: Mapped[str] = mapped_column(String(12), default="DISPONIBLE")
    fecha_apertura: Mapped[datetime | None] = mapped_column(DateTime)
    abierta_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    vence_abierta: Mapped[date | None] = mapped_column(Date)
    etiquetas_impresas: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=0)
    producto = relationship("Producto", lazy="joined")
    lote = relationship("Lote", lazy="joined")
    bodega = relationship("Bodega", lazy="joined")
    ubicacion = relationship("Ubicacion", lazy="joined")
    unidad = relationship("UnidadMedida", lazy="joined")


class MovimientoInventario(Base, ConId):
    """Libro inmutable. Nunca se actualiza ni se borra: se corrige con un movimiento inverso."""
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        UniqueConstraint("movimiento_anulado_id"),
        UniqueConstraint("clave_idempotencia"),
        Index("ix_movimientos_producto_fecha", "producto_id", "fecha"),
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    tipo_movimiento_id: Mapped[int] = mapped_column(ForeignKey("tipos_movimiento.id"))
    motivo_id: Mapped[int | None] = mapped_column(ForeignKey("motivos_movimiento.id"))
    existencia_id: Mapped[int] = mapped_column(ForeignKey("existencias.id"), index=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"), index=True)
    cantidad: Mapped[Decimal] = mapped_column(Cantidad)  # con signo, en unidad base
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    cantidad_ingresada: Mapped[Decimal | None] = mapped_column(Cantidad)  # como la digito el usuario
    unidad_ingresada_id: Mapped[int | None] = mapped_column(ForeignKey("unidades_medida.id"))
    costo_unitario: Mapped[Decimal] = mapped_column(Costo, default=0)
    costo_total: Mapped[Decimal] = mapped_column(Monto, default=0)  # mismo signo que cantidad
    bodega_origen_id: Mapped[int | None] = mapped_column(ForeignKey("bodegas.id"), index=True)
    bodega_destino_id: Mapped[int | None] = mapped_column(ForeignKey("bodegas.id"), index=True)
    ubicacion_origen_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    ubicacion_destino_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    proceso_id: Mapped[int | None] = mapped_column(ForeignKey("procesos.id"), index=True)
    temporada_id: Mapped[int | None] = mapped_column(ForeignKey("temporadas.id"))
    documento_id: Mapped[int | None] = mapped_column(ForeignKey("documentos_inventario.id"), index=True)
    detalle_documento_id: Mapped[int | None] = mapped_column(ForeignKey("detalles_documentos_inventario.id"))
    reserva_id: Mapped[int | None] = mapped_column(ForeignKey("reservas_stock.id"))
    movimiento_anulado_id: Mapped[int | None] = mapped_column(ForeignKey("movimientos_inventario.id"))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo_texto: Mapped[str | None] = mapped_column(String(300))
    observacion: Mapped[str | None] = mapped_column(String(300))
    clave_idempotencia: Mapped[str | None] = mapped_column(String(64))
    tipo = relationship("TipoMovimiento", lazy="joined")
    existencia = relationship("Existencia", lazy="joined")


class ExcepcionFifo(Base, ConId):
    __tablename__ = "excepciones_fifo"
    movimiento_id: Mapped[int] = mapped_column(ForeignKey("movimientos_inventario.id"), unique=True)
    existencia_recomendada_id: Mapped[int] = mapped_column(ForeignKey("existencias.id"))
    estrategia: Mapped[str] = mapped_column(String(20))
    politica: Mapped[str] = mapped_column(String(20))
    justificacion: Mapped[str | None] = mapped_column(String(300))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)


class ReservaStock(Base, ConId, ConFechas):
    """Compromiso de stock previo al consumo. No genera movimiento ni descuenta stock fisico."""
    __tablename__ = "reservas_stock"
    __table_args__ = (
        UniqueConstraint("empresa_id", "numero"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("cantidad_consumida >= 0", name="consumida_no_negativa"),
    )
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    numero: Mapped[str] = mapped_column(String(20))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"), index=True)
    bodega_id: Mapped[int | None] = mapped_column(ForeignKey("bodegas.id"))
    lote_id: Mapped[int | None] = mapped_column(ForeignKey("lotes.id"))
    existencia_id: Mapped[int | None] = mapped_column(ForeignKey("existencias.id"))
    proceso_id: Mapped[int | None] = mapped_column(ForeignKey("procesos.id"), index=True)
    area: Mapped[str | None] = mapped_column(String(80))
    documento_referencia: Mapped[str | None] = mapped_column(String(60))
    motivo: Mapped[str | None] = mapped_column(String(300))
    cantidad: Mapped[Decimal] = mapped_column(Cantidad)
    cantidad_consumida: Mapped[Decimal] = mapped_column(Cantidad, default=0)
    unidad_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_vencimiento: Mapped[datetime | None] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(String(10), default="ACTIVA", index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    cerrada_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_cierre: Mapped[datetime | None] = mapped_column(DateTime)
    observacion: Mapped[str | None] = mapped_column(String(300))
    producto = relationship("Producto", lazy="joined")


class ConteoInventario(Base, ConId, ConFechas):
    __tablename__ = "conteos_inventario"
    __table_args__ = (UniqueConstraint("empresa_id", "numero"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    numero: Mapped[str] = mapped_column(String(20))
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodegas.id"))
    ubicacion_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    estado: Mapped[str] = mapped_column(String(12), default="ABIERTO")  # ABIERTO EN_REVISION AUTORIZADO ANULADO
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    autorizado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    fecha_autorizacion: Mapped[datetime | None] = mapped_column(DateTime)
    observaciones: Mapped[str | None] = mapped_column(Text)
    detalles: Mapped[list["DetalleConteoInventario"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class DetalleConteoInventario(Base, ConId):
    __tablename__ = "detalles_conteos_inventario"
    __table_args__ = (UniqueConstraint("conteo_id", "existencia_id"),)
    conteo_id: Mapped[int] = mapped_column(ForeignKey("conteos_inventario.id", ondelete="CASCADE"), index=True)
    existencia_id: Mapped[int] = mapped_column(ForeignKey("existencias.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad_sistema: Mapped[Decimal] = mapped_column(Cantidad)
    cantidad_contada: Mapped[Decimal | None] = mapped_column(Cantidad)
    diferencia: Mapped[Decimal | None] = mapped_column(Cantidad)
    movimiento_ajuste_id: Mapped[int | None] = mapped_column(ForeignKey("movimientos_inventario.id"))
    observacion: Mapped[str | None] = mapped_column(String(300))
    contado_en: Mapped[datetime | None] = mapped_column(DateTime)


class Prestamo(Base, ConId, ConFechas):
    __tablename__ = "prestamos"
    __table_args__ = (UniqueConstraint("empresa_id", "numero"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    numero: Mapped[str] = mapped_column(String(20))
    existencia_id: Mapped[int] = mapped_column(ForeignKey("existencias.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("productos.id"))
    cantidad: Mapped[Decimal] = mapped_column(Cantidad)
    cantidad_devuelta: Mapped[Decimal] = mapped_column(Cantidad, default=0)
    persona: Mapped[str] = mapped_column(String(120))
    area: Mapped[str | None] = mapped_column(String(80))
    fecha_prestamo: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    fecha_devolucion_esperada: Mapped[date | None] = mapped_column(Date)
    fecha_devolucion_real: Mapped[datetime | None] = mapped_column(DateTime)
    estado: Mapped[str] = mapped_column(String(10), default="ACTIVO")  # ACTIVO PARCIAL DEVUELTO ANULADO
    observacion: Mapped[str | None] = mapped_column(String(300))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    movimiento_salida_id: Mapped[int | None] = mapped_column(ForeignKey("movimientos_inventario.id"))
