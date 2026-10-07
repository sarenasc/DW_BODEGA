"""Empresa, usuarios, RBAC, sesiones, auditoria, configuracion, adjuntos, secuencias."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.util import ahora

from .base import Base, ConFechas, ConId


class Empresa(Base, ConId, ConFechas):
    __tablename__ = "empresas"
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    rut: Mapped[str | None] = mapped_column(String(20))
    moneda: Mapped[str] = mapped_column(String(3), default="CLP")
    zona_horaria: Mapped[str] = mapped_column(String(50), default="America/Santiago")
    idioma: Mapped[str] = mapped_column(String(5), default="es")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)


roles_permisos = Table(
    "roles_permisos", Base.metadata,
    Column("rol_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permiso_id", ForeignKey("permisos.id", ondelete="CASCADE"), primary_key=True),
)
usuarios_roles = Table(
    "usuarios_roles", Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("rol_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
usuarios_bodegas = Table(
    "usuarios_bodegas", Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("bodega_id", ForeignKey("bodegas.id", ondelete="CASCADE"), primary_key=True),
)
usuarios_familias = Table(
    "usuarios_familias", Base.metadata,
    Column("usuario_id", ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
    Column("familia_id", ForeignKey("familias.id", ondelete="CASCADE"), primary_key=True),
)


class Permiso(Base, ConId):
    __tablename__ = "permisos"
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    modulo: Mapped[str] = mapped_column(String(30))
    accion: Mapped[str] = mapped_column(String(30))
    descripcion: Mapped[str] = mapped_column(String(200), default="")
    especial: Mapped[bool] = mapped_column(Boolean, default=False)


class Rol(Base, ConId, ConFechas):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("empresa_id", "codigo"),)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    codigo: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(100))
    descripcion: Mapped[str | None] = mapped_column(String(250))
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False)
    permisos: Mapped[list[Permiso]] = relationship(secondary=roles_permisos, lazy="selectin")


class Usuario(Base, ConId, ConFechas):
    __tablename__ = "usuarios"
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    usuario: Mapped[str] = mapped_column(String(60), unique=True)
    nombre: Mapped[str] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(150))
    clave_hash: Mapped[str] = mapped_column(String(255))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    # Alcance: si es True no se restringe; si es False aplica la tabla de asociacion.
    todas_bodegas: Mapped[bool] = mapped_column(Boolean, default=True)
    todas_familias: Mapped[bool] = mapped_column(Boolean, default=True)
    debe_cambiar_clave: Mapped[bool] = mapped_column(Boolean, default=False)
    ultimo_acceso: Mapped[datetime | None] = mapped_column(DateTime)
    roles: Mapped[list[Rol]] = relationship(secondary=usuarios_roles, lazy="selectin")
    bodegas = relationship("Bodega", secondary=usuarios_bodegas, lazy="selectin")
    familias = relationship("Familia", secondary=usuarios_familias, lazy="selectin")

    @property
    def permisos(self) -> set[str]:
        return {p.codigo for r in self.roles for p in r.permisos}


class Sesion(Base, ConId):
    __tablename__ = "sesiones"
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    creada_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    expira_en: Mapped[datetime] = mapped_column(DateTime)
    revocada_en: Mapped[datetime | None] = mapped_column(DateTime)
    motivo_revocacion: Mapped[str | None] = mapped_column(String(10))  # ROTACION | SALIDA | ADMIN
    ip: Mapped[str | None] = mapped_column(String(45))
    dispositivo: Mapped[str | None] = mapped_column(String(250))


class Auditoria(Base, ConId):
    __tablename__ = "auditoria"
    empresa_id: Mapped[int | None] = mapped_column(Integer, index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), index=True)
    fecha: Mapped[datetime] = mapped_column(DateTime, default=ahora, index=True)
    ip: Mapped[str | None] = mapped_column(String(45))
    dispositivo: Mapped[str | None] = mapped_column(String(250))
    entidad: Mapped[str] = mapped_column(String(60), index=True)
    entidad_id: Mapped[str | None] = mapped_column(String(60), index=True)
    accion: Mapped[str] = mapped_column(String(40))
    valor_anterior: Mapped[dict | None] = mapped_column(JSON)
    valor_nuevo: Mapped[dict | None] = mapped_column(JSON)
    motivo: Mapped[str | None] = mapped_column(String(500))


class Configuracion(Base, ConId, ConFechas):
    __tablename__ = "configuraciones"
    __table_args__ = (UniqueConstraint("empresa_id", "clave"),)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    clave: Mapped[str] = mapped_column(String(80))
    valor: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    descripcion: Mapped[str | None] = mapped_column(String(250))


class Adjunto(Base, ConId):
    __tablename__ = "adjuntos"
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    entidad: Mapped[str] = mapped_column(String(60), index=True)
    entidad_id: Mapped[int] = mapped_column(Integer, index=True)
    tipo: Mapped[str] = mapped_column(String(30), default="OTRO")
    nombre_archivo: Mapped[str] = mapped_column(String(255))
    ruta: Mapped[str] = mapped_column(String(500))
    mime: Mapped[str | None] = mapped_column(String(100))
    tamano: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = mapped_column(DateTime, default=ahora)
    descripcion: Mapped[str | None] = mapped_column(Text)


class Secuencia(Base, ConId):
    """Correlativos de sistema (existencias, documentos). Se incrementa con UPDATE atomico."""
    __tablename__ = "secuencias"
    __table_args__ = (UniqueConstraint("empresa_id", "clave"),)
    empresa_id: Mapped[int] = mapped_column(Integer)
    clave: Mapped[str] = mapped_column(String(60))
    ultimo_valor: Mapped[int] = mapped_column(Integer, default=0)
