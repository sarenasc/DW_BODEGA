#!/usr/bin/env bash
# Regenera la migracion inicial a partir de los modelos (valido mientras no existan instalaciones que migrar).
# Uso: bash scripts/regenerar_migracion.sh   (desde backend/, con el entorno virtual activo o ALEMBIC definido)
set -euo pipefail
TMP="$(mktemp -d)"
export WMS_CLAVE_SECRETA="solo-para-generar-la-migracion-0123456789" WMS_PLANIFICADOR=0 WMS_DIR_INSTANCIA="$TMP"
export WMS_URL_BD="sqlite:///$(cygpath -m "$TMP" 2>/dev/null || echo "$TMP")/vacia.db"
rm -f alembic/versions/*.py
"${ALEMBIC:-alembic}" revision --autogenerate -m "esquema inicial" --rev-id 0001
"${ALEMBIC:-alembic}" upgrade head
rm -rf "$TMP"
