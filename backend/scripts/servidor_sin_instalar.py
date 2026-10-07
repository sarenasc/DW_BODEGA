"""Levanta un servidor SIN instalar (carpeta de instancia temporal) para probar el asistente de instalacion."""
import os
import tempfile

os.environ["WMS_DIR_INSTANCIA"] = tempfile.mkdtemp(prefix="wms_asistente_")
os.environ["WMS_CLAVE_SECRETA"] = "clave-de-prueba-del-asistente-0123456789"
os.environ["WMS_MODO_DEMO"] = "0"
os.environ["WMS_PLANIFICADOR"] = "0"

import uvicorn  # noqa: E402

uvicorn.run("app.main:app", host="127.0.0.1", port=8766)
