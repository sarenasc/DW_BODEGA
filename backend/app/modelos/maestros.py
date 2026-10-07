"""Maestros parametrizables: temporadas, unidades, familias, productos, bodegas, ubicaciones."""
from datetime import date
from decimal import Decimal

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, Cantidad, ConFechas, ConId, Costo

GRANULARIDADES = ("POR_ENVASE", "POR_LOTE", "CONSOLIDADA", "UNIDAD_LOGISTICA")
ESTRATEGIAS = ("FIFO", "FEFO", "FEFO_FIFO", "SIN_RECOMENDACION")
POLITICAS_FIFO = ("ADVERTIR", "BLOQUEAR", "JUSTIFICAR", "PERMISO")
CAMPOS_POLITICA = (
    "usa_lote", "usa_vencimiento", "usa_serie", "requiere_qr", "requiere_ubicacion", "granularidad",
    "estrategia_salida", "politica_fifo", "vida_util_meses", "prioridad_vencimiento", "vida_util_abierto_dias",
    "plantilla_lote_id", "permite_sublotes",
)
# Valores usados cuando ningun nivel (producto, subfamilia, familia) define la politica.
POLITICA_GLOBAL = {
    "usa_lote": True, "usa_vencimiento": False, "usa_serie": False, "requiere_qr": True, "requiere_ubicacion": False,
    "granularidad": "POR_ENVASE", "estrategia_salida": "FIFO", "politica_fifo": "ADVERTIR", "vida_util_meses": None,
    "prioridad_vencimiento": "MANUAL", "vida_util_abierto_dias": None, "plantilla_lote_id": None, "permite_sublotes": True,
}


class PoliticaMixin:
    """Configuracion heredable familia -> subfamilia -> producto. NULL significa heredar."""
    usa_lote: Mapped[bool | None] = mapped_column(Boolean)
    usa_vencimiento: Mapped[bool | None] = mapped_column(Boolean)
    usa_serie: Mapped[bool | None] = mapped_column(Boolean)
    requiere_qr: Mapped[bool | None] = mapped_column(Boolean)
    requiere_ubicacion: Mapped[bool | None] = mapped_column(Boolean)
    granularidad: Mapped[str | None] = mapped_column(String(20))
    estrategia_salida: Mapped[str | None] = mapped_column(String(20))
    politica_fifo: Mapped[str | None] = mapped_column(String(20))
    vida_util_meses: Mapped[int | None] = mapped_column(Integer)
    prioridad_vencimiento: Mapped[str | None] = mapped_column(String(12))  # MANUAL | CALCULADA
    vida_util_abierto_dias: Mapped[int | None] = mapped_column(Integer)
    plantilla_lote_id: Mapped[int | None] = mapped_column(Integer)  # FK logica a plantillas_lotes
    permite_sublotes: Mapped[bool | None] = mapped_column(Boolean)


class Temporada(Base, ConId, ConFechas):
    __tablename__ = "temporadas"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    fecha_inicio: Mapped[date] = mapped_column(Date)
    fecha_termino: Mapped[date] = mapped_column(Date)
    actual: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class UnidadMedida(Base, ConId):
    __tablename__ = "unidades_medida"
    codigo: Mapped[str] = mapped_column(String(15), unique=True)
    nombre: Mapped[str] = mapped_column(String(60))
    dimension: Mapped[str] = mapped_column(String(15), default="CONTEO")  # MASA VOLUMEN CONTEO LONGITUD ENVASE
    decimales: Mapped[int] = mapped_column(Integer, default=2)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class ConversionUnidad(Base, ConId):
    """1 unidad_origen = factor x unidad_destino. producto_id NULL = conversion universal."""
    __tablename__ = "conversiones_unidades"
    __table_args__ = (
        UniqueConstraint("producto_id", "unidad_origen_id", "unidad_destino_id"),
        CheckConstraint("factor > 0", name="factor_positivo"),
    )
    producto_id: Mapped[int | None] = mapped_column(ForeignKey("productos.id", ondelete="CASCADE"), index=True)
    unidad_origen_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    unidad_destino_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    factor: Mapped[Decimal] = mapped_column(Numeric(18, 8))


class Familia(Base, ConId, ConFechas, PoliticaMixin):
    __tablename__ = "familias"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Subfamilia(Base, ConId, ConFechas, PoliticaMixin):
    __tablename__ = "subfamilias"
    __table_args__ = (UniqueConstraint("familia_id", "codigo"),)
    familia_id: Mapped[int] = mapped_column(ForeignKey("familias.id"), index=True)
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(250))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    familia: Mapped[Familia] = relationship(lazy="joined")


class DefinicionAtributo(Base, ConId):
    __tablename__ = "definiciones_atributos"
    __table_args__ = (UniqueConstraint("familia_id", "clave"),)
    familia_id: Mapped[int] = mapped_column(ForeignKey("familias.id", ondelete="CASCADE"))
    clave: Mapped[str] = mapped_column(String(40))
    etiqueta: Mapped[str] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(15), default="TEXTO")  # TEXTO NUMERO FECHA LISTA BOOLEANO
    requerido: Mapped[bool] = mapped_column(Boolean, default=False)
    opciones: Mapped[list | None] = mapped_column(JSON)


class Proveedor(Base, ConId, ConFechas):
    __tablename__ = "proveedores"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(150))
    rut: Mapped[str | None] = mapped_column(String(20))
    contacto: Mapped[str | None] = mapped_column(String(150))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Producto(Base, ConId, ConFechas, PoliticaMixin):
    __tablename__ = "productos"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(30))
    codigo_externo: Mapped[str | None] = mapped_column(String(50))
    nombre: Mapped[str] = mapped_column(String(150), index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    subfamilia_id: Mapped[int] = mapped_column(ForeignKey("subfamilias.id"), index=True)
    categoria: Mapped[str | None] = mapped_column(String(60))
    marca: Mapped[str | None] = mapped_column(String(60))
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedores.id"))
    unidad_base_id: Mapped[int] = mapped_column(ForeignKey("unidades_medida.id"))
    unidad_compra_id: Mapped[int | None] = mapped_column(ForeignKey("unidades_medida.id"))
    unidad_consumo_id: Mapped[int | None] = mapped_column(ForeignKey("unidades_medida.id"))
    costo_referencial: Mapped[Decimal | None] = mapped_column(Costo)
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    stock_minimo: Mapped[Decimal | None] = mapped_column(Cantidad)
    stock_critico: Mapped[Decimal | None] = mapped_column(Cantidad)
    stock_maximo: Mapped[Decimal | None] = mapped_column(Cantidad)
    punto_reposicion: Mapped[Decimal | None] = mapped_column(Cantidad)
    codigo_barras: Mapped[str | None] = mapped_column(String(60), index=True)
    atributos: Mapped[dict | None] = mapped_column(JSON)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Se incrementa para serializar reservas y salidas del mismo producto (bloqueo de fila portable).
    version_stock: Mapped[int] = mapped_column(Integer, default=0)
    subfamilia: Mapped[Subfamilia] = relationship(lazy="joined")
    unidad_base: Mapped[UnidadMedida] = relationship(foreign_keys=[unidad_base_id], lazy="joined")


class TipoBodega(Base, ConId):
    __tablename__ = "tipos_bodega"
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))


class Bodega(Base, ConId, ConFechas):
    __tablename__ = "bodegas"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(10))
    nombre: Mapped[str] = mapped_column(String(100))
    tipo_bodega_id: Mapped[int | None] = mapped_column(ForeignKey("tipos_bodega.id"))
    largo: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # metros (eje X del plano)
    ancho: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # metros (eje Y del plano)
    alto: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    # Jerarquia opcional y configurable, p. ej. ["Pasillo","Rack","Nivel","Posicion"].
    niveles: Mapped[list | None] = mapped_column(JSON)
    direccion: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class Ubicacion(Base, ConId, ConFechas):
    __tablename__ = "ubicaciones"
    __table_args__ = (UniqueConstraint("bodega_id", "codigo_completo"),)
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodegas.id"), index=True)
    padre_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(20), default="UBICACION")  # ZONA SECTOR PASILLO RACK NIVEL POSICION PISO...
    nivel: Mapped[int] = mapped_column(Integer, default=0)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    codigo: Mapped[str] = mapped_column(String(20))
    codigo_completo: Mapped[str] = mapped_column(String(80), index=True)
    nombre: Mapped[str | None] = mapped_column(String(100))
    capacidad: Mapped[Decimal | None] = mapped_column(Cantidad)
    almacenable: Mapped[bool] = mapped_column(Boolean, default=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class ElementoPlano(Base, ConId, ConFechas):
    """Geometria del plano 2D / visor 3D. Coordenadas en metros desde la esquina de la bodega."""
    __tablename__ = "elementos_plano"
    bodega_id: Mapped[int] = mapped_column(ForeignKey("bodegas.id", ondelete="CASCADE"), index=True)
    ubicacion_id: Mapped[int | None] = mapped_column(ForeignKey("ubicaciones.id"))
    tipo: Mapped[str] = mapped_column(String(15))  # RACK ZONA PISO PASILLO OBSTACULO
    nombre: Mapped[str] = mapped_column(String(60))
    x: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    y: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=0)
    ancho: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    fondo: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    alto: Mapped[Decimal] = mapped_column(Numeric(8, 2), default=1)
    rotacion: Mapped[int] = mapped_column(Integer, default=0)
    color: Mapped[str | None] = mapped_column(String(9))
    parametros: Mapped[dict | None] = mapped_column(JSON)  # rack: {"niveles": n, "posiciones": m}


class TipoMovimiento(Base, ConId):
    __tablename__ = "tipos_movimiento"
    codigo: Mapped[str] = mapped_column(String(25), unique=True)
    nombre: Mapped[str] = mapped_column(String(80))
    signo: Mapped[int] = mapped_column(Integer)  # +1 entrada, -1 salida
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


class MotivoMovimiento(Base, ConId):
    """Tipos de ingreso y de salida configurables (compra, traslado, proceso, merma...)."""
    __tablename__ = "motivos_movimiento"
    __table_args__ = (UniqueConstraint("clase", "codigo"),)
    clase: Mapped[str] = mapped_column(String(10))  # INGRESO | SALIDA
    codigo: Mapped[str] = mapped_column(String(25))
    nombre: Mapped[str] = mapped_column(String(80))
    tipo_movimiento_id: Mapped[int] = mapped_column(ForeignKey("tipos_movimiento.id"))
    requiere_proceso: Mapped[bool] = mapped_column(Boolean, default=False)
    requiere_documento: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    tipo_movimiento: Mapped[TipoMovimiento] = relationship(lazy="joined")


class PlantillaEtiqueta(Base, ConId):
    __tablename__ = "plantillas_etiquetas"
    nombre: Mapped[str] = mapped_column(String(60), unique=True)
    ancho_mm: Mapped[int] = mapped_column(Integer, default=100)
    alto_mm: Mapped[int] = mapped_column(Integer, default=60)
    campos: Mapped[list] = mapped_column(JSON, default=list)
    predeterminada: Mapped[bool] = mapped_column(Boolean, default=False)
