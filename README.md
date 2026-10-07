# WMS Bodegas

Sistema web de gestión de bodegas, inventario, lotes internos, QR, consumos y procesos productivos.
Primera etapa enfocada en **productos fitosanitarios**; todo es parametrizable para pañoles, repuestos, EPP y otros inventarios.

- **Existencia con QR**: cada ingreso crea existencias identificables (`INV-000000042`) con lote, ubicación, fecha de ingreso y **costo propio**.
- **Libro de movimientos inmutable**: el stock solo cambia con un movimiento; se corrige con movimientos inversos.
- **Consumo rápido** desde el teléfono: proceso → escanear → cantidad → registrar, con advertencia FIFO / FEFO.
- **Costo por proceso y por kilo**, con procesos copiados desde la base productiva.
- Reservas de stock, centro de alertas, trazabilidad visual, bodega en 2D / 3D, reportes exportables.

Estado detallado y honesto del proyecto: [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

## Probar el Modo Demo

Datos ficticios completos sobre SQLite, sin infraestructura externa.

**Con Docker**

```bash
docker compose up -d
```

Abrir <http://localhost:8080>.

**Sin Docker** (Python 3.12+ con [uv](https://docs.astral.sh/uv/) y Node 20+)

```bash
cd frontend && npm install && npm run build
```

```bash
cd backend && uv sync && uv run wms demo
```

Abrir <http://127.0.0.1:8000>.

| Usuario | Clave | Rol |
|---|---|---|
| `admin` | `Demo1234` | Administrador |
| `jefe` | `Demo1234` | Jefe de área |
| `bodega` | `Demo1234` | Digitador (no ve costos) |
| `lector` | `Demo1234` | Solo lectura |

`uv run wms reiniciar-demo` borra la base del Demo para regenerarla.
Guion de demostración paso a paso: [docs/INSTALLATION.md](docs/INSTALLATION.md#guion-de-demostración).

## Instalación real

Al primer inicio sin configuración aparece el **asistente de instalación**: idioma, empresa, motor
(SQL Server, PostgreSQL o MySQL), prueba de conexión, creación de la estructura, administrador y configuración inicial.
Ver [docs/INSTALLATION.md](docs/INSTALLATION.md) y [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Estructura

```
backend/    FastAPI + SQLAlchemy + Alembic (API REST bajo /api, Swagger en /api/docs)
  app/core        configuración, base de datos, seguridad, permisos, auditoría
  app/modelos     tablas (nombres físicos en español)
  app/servicios   reglas de negocio: lotes, inventario, costeo, integración, alertas, reportes
  app/modulos     rutas HTTP por módulo
  app/semilla     datos iniciales y datos Demo
  tests/          110 pruebas (pytest)
frontend/   Next.js + TypeScript + Tailwind (sitio estático, 36 pantallas)
docs/       documentación
despliegue/ proxy HTTPS de ejemplo
```

## Pruebas

```bash
cd backend && uv run pytest
```

```bash
cd frontend && npm test
```

Ver [docs/TESTING.md](docs/TESTING.md).

## Documentación

| Documento | Contenido |
|---|---|
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Capas, módulos y decisiones técnicas |
| [DATABASE](docs/DATABASE.md) | Tablas, relaciones e invariantes (generado) |
| [API](docs/API.md) | Operaciones REST (generado) |
| [INSTALLATION](docs/INSTALLATION.md) · [CONFIGURATION](docs/CONFIGURATION.md) · [DEPLOYMENT](docs/DEPLOYMENT.md) | Instalar, configurar, desplegar, respaldar |
| [SECURITY](docs/SECURITY.md) · [USER_ROLES](docs/USER_ROLES.md) | Seguridad, roles y permisos |
| [INVENTORY_LOGIC](docs/INVENTORY_LOGIC.md) · [LOT_LOGIC](docs/LOT_LOGIC.md) · [QR_WORKFLOW](docs/QR_WORKFLOW.md) | Existencias, FIFO/FEFO, costos, lotes, QR |
| [RESERVAS_STOCK](docs/RESERVAS_STOCK.md) · [ALERTAS](docs/ALERTAS.md) · [TRAZABILIDAD](docs/TRAZABILIDAD.md) | Reservas, alertas, trazabilidad |
| [PRODUCTION_INTEGRATION](docs/PRODUCTION_INTEGRATION.md) · [WAREHOUSE_3D](docs/WAREHOUSE_3D.md) | Integración productiva, bodega visual |
| [TESTING](docs/TESTING.md) · [PROJECT_STATUS](docs/PROJECT_STATUS.md) · [CHANGELOG](docs/CHANGELOG.md) | Pruebas, estado y cambios |
| [ANALISIS_INICIAL](docs/ANALISIS_INICIAL.md) | Análisis previo a la implementación |
