# Instalación

## Requisitos

| Componente | Versión |
|---|---|
| Python | 3.12 o 3.13 |
| Node.js | 20 o superior (solo para compilar el frontend) |
| Base de datos | PostgreSQL 13+, MySQL 8.0.16+ (necesario para `CHECK`), SQL Server 2017+ — o ninguna en Modo Demo |
| Navegador | Chrome / Edge / Safari actuales. La cámara exige HTTPS (o `localhost`) |

Controladores: PostgreSQL y MySQL se instalan con `uv sync --extra postgresql --extra mysql`.
SQL Server requiere además el *ODBC Driver 18 for SQL Server* del sistema operativo y `--extra sqlserver`.

## Modo Demo

Ver [README](../README.md#probar-el-modo-demo). La base queda en `instance/demo.db` y la base productiva simulada en `instance/produccion_demo.db`.
Para abrirlo desde un teléfono de la misma red: `uv run wms demo --host 0.0.0.0` (el Demo usa claves conocidas: no lo exponga fuera de una red de confianza).
La cámara del teléfono no funcionará sin HTTPS; el código se puede digitar o elegir de la lista.

## Instalación con el asistente

1. Defina la clave maestra (ver [CONFIGURATION](CONFIGURATION.md)):
   ```bash
   export WMS_CLAVE_SECRETA="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   ```
2. Compile el frontend e inicie el backend:
   ```bash
   cd frontend && npm install && npm run build
   ```
   ```bash
   cd backend && uv sync --extra postgresql && uv run wms servir --host 0.0.0.0
   ```
3. Abra el sistema. Al no existir configuración se muestra el asistente:

| Paso | Qué hace |
|---|---|
| 1 Idioma | Idioma de la aplicación |
| 2 Empresa | Nombre, código, RUT, moneda, zona horaria |
| 3 Base de datos | **Un** motor: SQL Server, PostgreSQL, MySQL o Modo Demo; servidor, puerto, usuario, contraseña, base y parámetros adicionales |
| 4 Probar conexión | Verifica el acceso; avisa si la base aún no existe |
| 5 Crear estructura | Crea la base si falta (y hay permisos) y ejecuta las migraciones: tablas, índices y relaciones |
| 6 Administrador | Usuario y clave del primer administrador |
| 7 Configuración inicial | Temporada inicial, datos de demostración opcionales; crea roles, unidades, tipos de movimiento, motivos y reglas de alerta |
| 8 Entrar | Acceso al sistema |

La conexión elegida se guarda cifrada en `instance/config.json`. El asistente deja de estar disponible una vez instalado.
El motor no se cambia después: para usar otro motor se instala una instancia nueva.

Alternativa sin asistente de base de datos: definir `WMS_URL_BD` con una URL de SQLAlchemy.

## Permisos del usuario de base de datos

- Para que el asistente **cree la base**: `CREATEDB` (PostgreSQL), `CREATE` (MySQL) o `dbcreator` (SQL Server).
  Si no los tiene, cree la base vacía a mano y el asistente creará solo las tablas.
- En operación normal basta ser propietario de la base (crear y alterar tablas para las migraciones, leer y escribir datos).

## Actualización

Al iniciar, el backend aplica las migraciones pendientes. También: `uv run wms migrar`. Respalde antes (ver [DEPLOYMENT](DEPLOYMENT.md)).

## Guion de demostración

Con `admin` / `Demo1234`:

1. **Dashboard**: valor de inventario, consumo del día, costo por kilo, alertas.
2. **Bodegas → Plano 2D / 3D** de *Bodega Fitosanitarios*: girar, colorear por antigüedad o vencimiento, clic en una posición.
3. **Familias**: crear familia y subfamilia (definir si usa lote, granularidad, estrategia).
4. **Creador de lotes**: armar una plantilla con bloques, ver la vista previa y la validación; activar; asociarla a la subfamilia.
5. **Productos**: crear producto; en su ficha agregar la conversión (1 caja = 100 un) y marcarla para compra.
6. **Nuevo ingreso**: producto, cantidad, valor unitario, ubicación → confirmar. Se generan lote, existencias y QR; **Imprimir QR**.
7. **Stock**: físico, reservado y disponible. **Reservas → Nueva reserva** para el proceso `PK-1008`.
8. **Procesos → Importar desde producción**: importar `PK-1009`.
9. **Consumo rápido** (ideal desde el teléfono): fijar `PK-1008`, digitar `INV-000000005` (existencia nueva de *Fungicida Fludioxonil*):
   aparece la **advertencia FIFO** con la existencia recomendada; continuar, digitar cantidad, **Registrar**.
10. **Procesos → PK-1008**: costo total y costo por kilo provisorio. **Actualizar proceso**: los kilos pasan de 5.000 a 15.000 y queda el historial.
    **Cerrar → Actualizar y cerrar**: kilos definitivos.
11. **Alertas**: consumo fuera de FIFO, stock bajo, vencimientos; resolver una.
12. **Trazabilidad** desde el proceso (hacia atrás) o desde un lote (hacia adelante).

Entrar luego como `bodega` muestra la misma operación **sin costos**.
