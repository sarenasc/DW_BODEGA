"""Genera docs/DATABASE.md y docs/API.md a partir de los modelos y de OpenAPI, para que no se desactualicen.

    python scripts/generar_docs.py
"""
import os
import tempfile
from pathlib import Path

os.environ.setdefault("WMS_CLAVE_SECRETA", "solo-para-generar-documentacion-0123456789")
os.environ.setdefault("WMS_PLANIFICADOR", "0")
os.environ.setdefault("WMS_DIR_INSTANCIA", tempfile.mkdtemp())

from sqlalchemy import CheckConstraint, UniqueConstraint  # noqa: E402

from app.main import crear_app  # noqa: E402
from app.modelos import Base  # noqa: E402

DOCS = Path(__file__).resolve().parents[2] / "docs"
GRUPOS = {
    "Plataforma": ["empresas", "usuarios", "roles", "permisos", "roles_permisos", "usuarios_roles", "usuarios_bodegas", "usuarios_familias",
                   "sesiones", "auditoria", "configuraciones", "adjuntos", "secuencias"],
    "Maestros": ["temporadas", "unidades_medida", "conversiones_unidades", "familias", "subfamilias", "definiciones_atributos", "productos",
                 "proveedores", "tipos_bodega", "bodegas", "ubicaciones", "elementos_plano", "tipos_movimiento", "motivos_movimiento",
                 "plantillas_etiquetas"],
    "Lotes": ["plantillas_lotes", "versiones_plantillas_lotes", "segmentos_plantillas_lotes", "contadores_lotes", "lotes", "historial_estados_lotes"],
    "Inventario": ["documentos_inventario", "detalles_documentos_inventario", "existencias", "movimientos_inventario", "excepciones_fifo",
                   "reservas_stock", "conteos_inventario", "detalles_conteos_inventario", "prestamos"],
    "Procesos e integracion": ["procesos", "capturas_procesos", "cambios_procesos", "conexiones_integracion", "fuentes_integracion",
                               "mapeos_integracion", "ejecuciones_sincronizacion"],
    "Alertas": ["reglas_alertas", "alertas"],
}
INTRO = """# Base de datos

> Documento generado desde los modelos (`python scripts/generar_docs.py`). No editar a mano.

## Criterios

- **Nombres fisicos en espanol**, `snake_case`, sin tildes ni ene.
- **Un motor por instalacion** (SQL Server, PostgreSQL, MySQL o SQLite en Modo Demo). Solo se usan tipos portables:
  `Integer`, `String`, `Numeric`, `DateTime`, `Date`, `Boolean`, `Text` y `JSON` generico (solo como bolsa de atributos, nunca en filtros de negocio).
- Cantidades y costos unitarios `NUMERIC(18,6)`; totales `NUMERIC(18,2)`. Nunca coma flotante.
- Fechas/hora en UTC sin zona. Los dias (vencimiento, antiguedad) se cuentan en la zona `WMS_ZONA_HORARIA`.
- `empresa_id` en las tablas raiz: el modelo no bloquea una futura operacion multiempresa.
- Sin borrado fisico en movimientos, lotes ni existencias. Los maestros usan baja logica (`activo`).
- La estructura se crea con migraciones Alembic (`backend/alembic/versions`).

## Modelo conceptual

```mermaid
erDiagram
    empresas ||--o{ bodegas : tiene
    bodegas ||--o{ ubicaciones : contiene
    ubicaciones ||--o{ ubicaciones : "padre de"
    bodegas ||--o{ elementos_plano : dibuja
    familias ||--o{ subfamilias : agrupa
    subfamilias ||--o{ productos : agrupa
    productos ||--o{ conversiones_unidades : convierte
    plantillas_lotes ||--o{ versiones_plantillas_lotes : versiona
    versiones_plantillas_lotes ||--o{ segmentos_plantillas_lotes : compone
    plantillas_lotes ||--o{ contadores_lotes : numera
    productos ||--o{ lotes : tiene
    lotes ||--o{ lotes : "sublote de"
    documentos_inventario ||--o{ detalles_documentos_inventario : detalla
    detalles_documentos_inventario ||--o{ existencias : origina
    lotes ||--o{ existencias : identifica
    ubicaciones ||--o{ existencias : almacena
    existencias ||--o{ existencias : "dividida en"
    existencias ||--o{ movimientos_inventario : registra
    movimientos_inventario ||--o| movimientos_inventario : anula
    movimientos_inventario ||--o| excepciones_fifo : "puede generar"
    procesos ||--o{ movimientos_inventario : consume
    procesos ||--o{ reservas_stock : reserva
    productos ||--o{ reservas_stock : compromete
    procesos ||--o{ capturas_procesos : sincroniza
    procesos ||--o{ cambios_procesos : audita
    fuentes_integracion ||--o{ procesos : provee
    fuentes_integracion ||--o{ mapeos_integracion : mapea
```

## Invariantes

1. `existencias.cantidad_fisica = SUM(movimientos_inventario.cantidad)` de esa existencia. Lo verifica `wms verificar` y las pruebas.
2. `existencias.cantidad_fisica >= 0` (restriccion `CHECK`).
3. `SUM(movimientos_inventario.costo_total)` de una existencia agotada es exactamente 0.
4. Un movimiento se anula una sola vez (`UNIQUE movimiento_anulado_id`).
5. Un lote es unico por empresa (`UNIQUE empresa_id, codigo`); un contador es unico por plantilla y alcance.
6. Stock disponible = stock fisico - reservas ACTIVAS pendientes (`reservas_stock.cantidad - cantidad_consumida`).

"""


def tipo(col) -> str:
    return str(col.type).replace("VARCHAR", "String").replace("INTEGER", "Integer").replace("DATETIME", "DateTime").replace("BOOLEAN", "Boolean") \
        .replace("NUMERIC", "Numeric").replace("TEXT", "Text").replace("DATE", "Date")


def base_datos() -> str:
    tablas = Base.metadata.tables
    salida = [INTRO, f"## Tablas ({len(tablas)})\n"]
    vistas = set()
    for grupo, nombres in GRUPOS.items():
        salida.append(f"\n### {grupo}\n")
        for nombre in nombres:
            t = tablas[nombre]
            vistas.add(nombre)
            salida.append(f"\n#### `{nombre}`\n")
            if t.comment:
                salida.append(t.comment + "\n")
            salida.append("| Columna | Tipo | Nulo | Referencia |\n|---|---|---|---|")
            for c in t.columns:
                fk = ", ".join(f"`{f.column.table.name}.{f.column.name}`" for f in c.foreign_keys)
                marca = " **PK**" if c.primary_key else ""
                salida.append(f"| `{c.name}`{marca} | {tipo(c)} | {'si' if c.nullable else 'no'} | {fk} |")
            unicos = [", ".join(col.name for col in k.columns) for k in t.constraints if isinstance(k, UniqueConstraint)]
            unicos += [c.name for c in t.columns if c.unique]
            checks = [str(k.sqltext) for k in t.constraints if isinstance(k, CheckConstraint)]
            indices = [", ".join(col.name for col in i.columns) for i in t.indexes]
            if unicos:
                salida.append(f"\nUnicos: {'; '.join(f'({u})' for u in unicos)}")
            if checks:
                salida.append(f"\nRestricciones: {'; '.join(f'`{c}`' for c in checks)}")
            if indices:
                salida.append(f"\nIndices: {'; '.join(f'({i})' for i in indices)}")
    faltan = set(tablas) - vistas
    assert not faltan, f"Tablas sin grupo en la documentacion: {faltan}"
    return "\n".join(salida) + "\n"


def api() -> str:
    esquema = crear_app().openapi()
    por_etiqueta: dict[str, list[str]] = {}
    total = 0
    for ruta, metodos in sorted(esquema["paths"].items()):
        for metodo, op in metodos.items():
            etiqueta = (op.get("tags") or ["Sistema"])[0]
            desc = (op.get("description") or op.get("summary") or "").strip().split("\n")[0]
            por_etiqueta.setdefault(etiqueta, []).append(f"| `{metodo.upper()}` | `{ruta}` | {desc} |")
            total += 1
    salida = [f"""# API REST

> Listado generado desde OpenAPI (`python scripts/generar_docs.py`). La referencia interactiva completa, con esquemas de entrada,
> esta en **`/api/docs`** (Swagger) y **`/api/openapi.json`** del servidor en marcha.

## Convenciones

- Base: `/api`. Rutas en espanol, coherentes con los nombres de tablas.
- **Autenticacion:** `POST /api/auth/login` devuelve un token de acceso de corta duracion (cabecera `Authorization: Bearer <token>`)
  y deja la sesion renovable en una cookie `httpOnly`. `POST /api/auth/refrescar` entrega un token nuevo.
- **Permisos:** cada operacion exige un permiso `modulo:accion` y respeta el alcance por bodega y familia del usuario.
  Sin el permiso `costos:ver` los campos de costo y valor llegan en `null`.
- **Errores:** `{{"codigo": "STOCK_INSUFICIENTE", "mensaje": "...", "datos": {{...}}}}`. El `codigo` es estable; el `mensaje` es para mostrar.
  401 sin sesion, 403 sin permiso, 404 inexistente o fuera de alcance, 409 conflicto de negocio, 422 entrada invalida, 429 demasiados intentos.
- **Listados:** `?q=&pagina=&tam=` y devuelven `{{"total", "pagina", "tam", "items"}}`.
- **Fechas:** UTC en ISO 8601 con sufijo `Z`. Las fechas sin hora son dias locales (`AAAA-MM-DD`).
- **Idempotencia:** `POST /api/consumos` acepta `clave_idempotencia`; repetir el envio devuelve el mismo movimiento con `duplicado: true`.
- **Advertencia FIFO:** un consumo fuera de orden responde 409 `FIFO_ADVERTENCIA` con la existencia recomendada en `datos`;
  se reenvia con `confirmar_fifo: true` (o `justificacion`, segun la politica).

## Operaciones ({total})
"""]
    for etiqueta in sorted(por_etiqueta):
        salida.append(f"\n### {etiqueta}\n\n| Metodo | Ruta | Descripcion |\n|---|---|---|")
        salida += por_etiqueta[etiqueta]
    return "\n".join(salida) + "\n"


if __name__ == "__main__":
    (DOCS / "DATABASE.md").write_text(base_datos(), encoding="utf-8")
    (DOCS / "API.md").write_text(api(), encoding="utf-8")
    print("docs/DATABASE.md y docs/API.md generados")
