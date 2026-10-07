"""Ejecucion programatica de migraciones Alembic."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

DIR_ALEMBIC = Path(__file__).resolve().parents[2] / "alembic"


def config_alembic(url: URL | str) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(DIR_ALEMBIC))
    cfg.attributes["url"] = url.render_as_string(hide_password=False) if isinstance(url, URL) else url
    return cfg


def migrar(url: URL | str) -> None:
    """Crea o actualiza tablas, indices y relaciones hasta la ultima version."""
    command.upgrade(config_alembic(url), "head")
