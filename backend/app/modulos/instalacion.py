"""Asistente de instalacion. Solo opera mientras el sistema no esta instalado."""
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.core.errores import ErrorNegocio
from app.core.migraciones import migrar
from app.core.seguridad import hash_clave, validar_fortaleza
from app.modelos import Empresa, Temporada, Usuario
from app.semilla.base import sembrar_base, sembrar_empresa

router = APIRouter(prefix="/api/instalacion", tags=["Instalacion"])


class DatosBD(BaseModel):
    motor: str  # sqlserver | postgresql | mysql | demo
    servidor: str = ""
    puerto: int | None = None
    usuario: str = ""
    clave: str = ""
    base_datos: str = ""
    parametros: dict[str, str] = Field(default_factory=dict)

    def url(self):
        return nucleo_db.construir_url(self.motor, self.servidor, self.puerto, self.usuario, self.clave,
                                       self.base_datos, self.parametros)


class DatosEmpresa(BaseModel):
    codigo: str = "EMP"
    nombre: str
    rut: str | None = None
    moneda: str = "CLP"
    zona_horaria: str = "America/Santiago"


class DatosAdmin(BaseModel):
    usuario: str
    nombre: str
    email: str | None = None
    clave: str


class DatosInstalacion(BaseModel):
    idioma: str = "es"
    empresa: DatosEmpresa
    bd: DatosBD
    admin: DatosAdmin
    temporada: str | None = None  # p. ej. "2026-2027"
    datos_demo: bool = False


def instalado() -> bool:
    url = nucleo_db.url_activa()
    if not url:
        return False
    try:
        eng = nucleo_db.motor()
        if not inspect(eng).has_table("empresas"):
            return False
        with Session(eng) as s:
            return s.scalar(select(Empresa.id).limit(1)) is not None
    except Exception:
        return False


def _exigir_no_instalado() -> None:
    if instalado():
        raise ErrorNegocio("YA_INSTALADO", "El sistema ya esta instalado.", 409)


@router.get("/estado")
def estado():
    return {"instalado": instalado(), "modo_demo": ajustes().modo_demo,
            "motores": [{"codigo": "sqlserver", "nombre": "SQL Server", "puerto": 1433},
                        {"codigo": "postgresql", "nombre": "PostgreSQL", "puerto": 5432},
                        {"codigo": "mysql", "nombre": "MySQL", "puerto": 3306},
                        {"codigo": "demo", "nombre": "Modo Demo (SQLite, sin infraestructura)", "puerto": None}]}


@router.post("/probar-conexion")
def probar(bd: DatosBD):
    _exigir_no_instalado()
    if bd.motor == "demo":
        return {"ok": True, "existe_base": True, "mensaje": "El modo demo usa una base local SQLite."}
    try:
        nucleo_db.probar_conexion(bd.url())
        return {"ok": True, "existe_base": True, "mensaje": "Conexion correcta."}
    except Exception as e:
        primer = str(e).splitlines()[0][:300]
    # La base puede no existir aun: se prueba contra la base de mantenimiento del motor.
    try:
        mant = nucleo_db.MOTORES[bd.motor]["mantenimiento"]
        nucleo_db.probar_conexion(bd.url().set(database=mant))
        return {"ok": True, "existe_base": False,
                "mensaje": "Servidor accesible. La base no existe: se intentara crear durante la instalacion."}
    except Exception:
        return {"ok": False, "existe_base": False, "mensaje": f"No fue posible conectar: {primer}"}


@router.post("/crear-estructura")
def crear_estructura(bd: DatosBD):
    """Paso 5 del asistente: crea la base si falta y ejecuta las migraciones (tablas, indices, relaciones)."""
    _exigir_no_instalado()
    url = bd.url()
    pasos = []
    try:
        if nucleo_db.crear_base_si_falta(bd.motor, url):
            pasos.append("Base de datos creada")
        nucleo_db.probar_conexion(url)
        migrar(url)
        from sqlalchemy import create_engine
        eng = create_engine(url)
        tablas = len(inspect(eng).get_table_names())
        eng.dispose()
        pasos += ["Migraciones ejecutadas", f"{tablas} tablas con sus indices y relaciones"]
    except ErrorNegocio:
        raise
    except Exception as e:
        raise ErrorNegocio("ERROR_BD", f"No fue posible crear la estructura: {str(e).splitlines()[0][:300]}") from e
    return {"ok": True, "pasos": pasos}


def instalar(d: DatosInstalacion) -> dict:
    if (msg := validar_fortaleza(d.admin.clave)):
        raise ErrorNegocio("CLAVE_DEBIL", msg)
    url = d.bd.url()
    pasos = []
    try:
        if nucleo_db.crear_base_si_falta(d.bd.motor, url):
            pasos.append("Base de datos creada")
        nucleo_db.probar_conexion(url)
        pasos.append("Conexion verificada")
        migrar(url)
        pasos.append("Tablas, indices y relaciones creados")
    except ErrorNegocio:
        raise
    except Exception as e:
        raise ErrorNegocio("ERROR_BD", f"No fue posible preparar la base: {str(e).splitlines()[0][:300]}") from e

    eng = nucleo_db.crear_motor(url)
    try:
        with Session(eng, expire_on_commit=False) as s, s.begin():
            if s.scalar(select(Empresa.id).limit(1)) is not None:
                raise ErrorNegocio("BD_EN_USO", "La base indicada ya contiene una instalacion.", 409)
            sembrar_base(s)
            emp = Empresa(codigo=d.empresa.codigo.upper(), nombre=d.empresa.nombre, rut=d.empresa.rut,
                          moneda=d.empresa.moneda, zona_horaria=d.empresa.zona_horaria, idioma=d.idioma)
            s.add(emp)
            s.flush()
            roles = sembrar_empresa(s, emp)
            s.add(Usuario(empresa_id=emp.id, usuario=d.admin.usuario.strip(), nombre=d.admin.nombre, email=d.admin.email,
                          clave_hash=hash_clave(d.admin.clave), roles=[roles["ADMINISTRADOR"]]))
            if d.temporada:
                try:
                    a1 = int(d.temporada[:4])
                except ValueError:
                    a1 = date.today().year
                s.add(Temporada(empresa_id=emp.id, codigo=d.temporada, nombre=f"Temporada {d.temporada}",
                                fecha_inicio=date(a1, 7, 1), fecha_termino=date(a1 + 1, 6, 30), actual=True))
            pasos.append("Datos iniciales y administrador creados")
            if d.datos_demo:
                from app.semilla.demo import sembrar_demo
                sembrar_demo(s, emp)
                pasos.append("Datos de demostracion cargados")
    finally:
        eng.dispose()
    nucleo_db.guardar_config_instancia(d.bd.motor, url)
    nucleo_db.reiniciar_motor()
    return {"ok": True, "pasos": pasos}


@router.post("/ejecutar")
def ejecutar(d: DatosInstalacion):
    _exigir_no_instalado()
    return instalar(d)
