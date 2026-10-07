"""Configuracion de arranque. Todo valor sensible proviene de variables de entorno."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

RAIZ = Path(__file__).resolve().parents[3]


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WMS_", env_file=".env", extra="ignore")

    # Clave maestra: firma JWT y cifra credenciales. Obligatoria fuera del modo demo.
    clave_secreta: str = ""
    modo_demo: bool = False
    dir_instancia: Path = RAIZ / "instance"
    dir_archivos: Path | None = None
    dir_frontend: Path = RAIZ / "frontend" / "out"
    minutos_token_acceso: int = 30
    dias_sesion: int = 14
    cookie_segura: bool = False  # True cuando se sirve por HTTPS
    url_publica: str = "http://localhost:8000"
    origenes_cors: str = ""
    intentos_login: int = 8
    ventana_login_segundos: int = 300
    planificador: bool = True
    # URL explicita (pruebas o despliegues que prefieren variable de entorno al asistente)
    url_bd: str = ""

    @property
    def secreto(self) -> str:
        if self.clave_secreta:
            return self.clave_secreta
        if self.modo_demo:
            return "demo-clave-no-usar-en-produccion-0123456789"
        raise RuntimeError("Defina WMS_CLAVE_SECRETA (minimo 32 caracteres) antes de iniciar.")

    @property
    def archivos(self) -> Path:
        return self.dir_archivos or (self.dir_instancia / "archivos")


@lru_cache
def ajustes() -> Ajustes:
    a = Ajustes()
    a.dir_instancia.mkdir(parents=True, exist_ok=True)
    return a
