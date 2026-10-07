"""Entorno Alembic. La URL llega desde la aplicacion (config.attributes) o desde WMS_URL_BD / instancia."""
from alembic import context
from sqlalchemy import create_engine

from app.modelos import Base

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    url = config.attributes.get("url")
    if not url:
        from app.core.db import url_activa
        url = url_activa()
    if not url:
        raise RuntimeError("No hay base configurada. Use el asistente o defina WMS_URL_BD.")
    return url


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as conexion:
        context.configure(connection=conexion, target_metadata=target_metadata, compare_type=True,
                          render_as_batch=conexion.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
