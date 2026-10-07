"""Motor y sesiones. Una instalacion usa un unico motor, elegido en el asistente."""
import json
import re
import threading
from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from .config import ajustes
from .errores import ErrorNegocio
from .seguridad import cifrar, descifrar

MOTORES = {
    "postgresql": {"driver": "postgresql+psycopg", "puerto": 5432, "mantenimiento": "postgres"},
    "mysql": {"driver": "mysql+pymysql", "puerto": 3306, "mantenimiento": None},
    "sqlserver": {"driver": "mssql+pyodbc", "puerto": 1433, "mantenimiento": "master"},
    "demo": {"driver": "sqlite", "puerto": None, "mantenimiento": None},
}

_engine: Engine | None = None
_fabrica: sessionmaker | None = None


def construir_url(motor: str, servidor: str = "", puerto: int | None = None, usuario: str = "", clave: str = "",
                  base_datos: str = "", parametros: dict | None = None) -> URL:
    if motor not in MOTORES:
        raise ErrorNegocio("MOTOR_INVALIDO", f"Motor no soportado: {motor}")
    m = MOTORES[motor]
    if motor == "demo":
        ruta = ajustes().dir_instancia / (base_datos or "demo.db")
        return make_url(f"sqlite:///{ruta.as_posix()}")
    consulta = dict(parametros or {})
    if motor == "sqlserver":
        consulta.setdefault("driver", "ODBC Driver 18 for SQL Server")
        consulta.setdefault("TrustServerCertificate", "yes")
    if motor == "mysql":
        consulta.setdefault("charset", "utf8mb4")
    return URL.create(m["driver"], username=usuario or None, password=clave or None, host=servidor or None,
                      port=puerto or m["puerto"], database=base_datos or None, query=consulta)


def crear_motor(url: URL | str) -> Engine:
    url = make_url(url) if isinstance(url, str) else url
    if url.get_backend_name() == "sqlite":
        eng = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(eng, "connect")
        def _conectar(dbapi, _):
            dbapi.isolation_level = None  # control manual: BEGIN IMMEDIATE serializa escritores
            cur = dbapi.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA busy_timeout=30000")
            cur.close()

        # SQLite admite un solo escritor y su espera por bloqueo no es justa: con muchos usuarios algunos
        # agotan el tiempo. Un candado del proceso ordena las transacciones en fila (solo Modo Demo).
        candado = threading.Lock()

        def _soltar(info: dict) -> None:
            if info.pop("wms_candado", False):
                candado.release()

        @event.listens_for(eng, "begin")
        def _begin(conn):
            candado.acquire()
            conn.info["wms_candado"] = True
            try:
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            except Exception:
                _soltar(conn.info)
                raise

        @event.listens_for(eng, "commit")
        def _commit(conn):
            _soltar(conn.info)

        @event.listens_for(eng, "rollback")
        def _rollback(conn):
            _soltar(conn.info)

        @event.listens_for(eng, "checkin")
        def _checkin(dbapi, registro):  # red de seguridad: la conexion vuelve al pool sin commit ni rollback
            _soltar(registro.info)

        return eng
    opciones = {"pool_pre_ping": True, "pool_size": 10, "max_overflow": 20}
    if url.get_backend_name() == "mysql":
        opciones["isolation_level"] = "READ COMMITTED"
    return create_engine(url, **opciones)


# ---- configuracion de instancia (archivo local cifrado) ----

def _ruta_config():
    return ajustes().dir_instancia / "config.json"


def leer_config_instancia() -> dict | None:
    r = _ruta_config()
    if not r.exists():
        return None
    datos = json.loads(r.read_text(encoding="utf-8"))
    datos["url"] = descifrar(datos["url_cifrada"])
    return datos


def guardar_config_instancia(motor: str, url: URL, extra: dict | None = None) -> None:
    datos = {"motor": motor, "url_cifrada": cifrar(url.render_as_string(hide_password=False)), **(extra or {})}
    _ruta_config().write_text(json.dumps(datos, indent=2), encoding="utf-8")


def url_activa() -> str | None:
    a = ajustes()
    if a.url_bd:
        return a.url_bd
    cfg = leer_config_instancia()
    if cfg:
        return cfg["url"]
    if a.modo_demo:
        return construir_url("demo").render_as_string(hide_password=False)
    return None


def motor() -> Engine:
    global _engine, _fabrica
    if _engine is None:
        url = url_activa()
        if not url:
            raise ErrorNegocio("NO_INSTALADO", "El sistema aun no esta instalado.", 503)
        _engine = crear_motor(url)
        _fabrica = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def reiniciar_motor() -> None:
    global _engine, _fabrica
    if _engine is not None:
        _engine.dispose()
    _engine, _fabrica = None, None


def nueva_sesion() -> Session:
    motor()
    return _fabrica()


def get_db() -> Iterator[Session]:
    db = nueva_sesion()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---- creacion de base (asistente) ----

_NOMBRE_BD = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


def probar_conexion(url: URL) -> None:
    eng = crear_motor(url)
    try:
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
    finally:
        eng.dispose()


def crear_base_si_falta(motor_: str, url: URL) -> bool:
    """Intenta crear la base. Devuelve True si la creo. Requiere permisos del usuario indicado."""
    if motor_ == "demo":
        return False
    nombre = url.database or ""
    if not _NOMBRE_BD.match(nombre):
        raise ErrorNegocio("NOMBRE_BD_INVALIDO", "El nombre de la base solo admite letras, numeros y guion bajo.")
    try:
        probar_conexion(url)
        return False
    except Exception:
        pass
    admin = url.set(database=MOTORES[motor_]["mantenimiento"])
    eng = create_engine(admin, isolation_level="AUTOCOMMIT")
    try:
        with eng.connect() as c:
            if motor_ == "mysql":
                c.execute(text(f"CREATE DATABASE IF NOT EXISTS `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            elif motor_ == "sqlserver":
                c.execute(text(f"IF DB_ID('{nombre}') IS NULL CREATE DATABASE [{nombre}]"))
                c.execute(text(f"ALTER DATABASE [{nombre}] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE"))
            else:
                c.execute(text(f'CREATE DATABASE "{nombre}"'))
    finally:
        eng.dispose()
    return True


