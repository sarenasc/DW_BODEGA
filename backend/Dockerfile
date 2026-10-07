# Backend WMS: FastAPI + SQLAlchemy. Imagen sin privilegios de root.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    WMS_DIR_INSTANCIA=/datos WMS_DIR_FRONTEND=/app/frontend
WORKDIR /app

# Controlador ODBC de SQL Server: opcional (docker build --build-arg CON_SQLSERVER=1).
ARG CON_SQLSERVER=0
RUN apt-get update && apt-get install -y --no-install-recommends curl gnupg \
    && if [ "$CON_SQLSERVER" = "1" ]; then \
         curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft.gpg \
         && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql.list \
         && apt-get update && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc-dev g++; \
       fi \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
# Instalacion editable: las migraciones se ubican junto al codigo (/app/alembic).
RUN pip install -e ".[postgresql,mysql]" \
    && if [ "$CON_SQLSERVER" = "1" ]; then pip install "pyodbc>=5.1"; fi

RUN useradd --system --uid 10001 wms && mkdir -p /datos && chown -R wms /datos /app
USER wms
VOLUME ["/datos"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s CMD curl -fsS http://127.0.0.1:8000/api/salud || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
