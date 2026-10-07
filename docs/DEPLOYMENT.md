# Despliegue, respaldo y restauración

> **Sin validar en este entorno:** los archivos Docker y la ejecución sobre PostgreSQL, MySQL y SQL Server no pudieron probarse
> (el equipo de desarrollo no tiene Docker ni esos motores). Se probó SQLite de punta a punta. Valide en un ambiente de prueba antes de producción.

## Topología

```
Internet / red interna ──HTTPS──> proxy (Caddy) ──> frontend (nginx: sitio estático)
                                                         └── /api, /q ──> backend (uvicorn) ──> base de datos
```

Todo en el mismo origen: sin CORS y con cookie de sesión `SameSite=Strict`.

## Con Docker Compose

```bash
cp .env.example .env
```

Complete `.env` (`WMS_CLAVE_SECRETA`, `WMS_DOMINIO`, `WMS_URL_PUBLICA`, credenciales de la base) y luego:

```bash
docker compose -f docker-compose.produccion.yml up -d
```

Abra `https://<dominio>` y siga el asistente (motor PostgreSQL, servidor `bd`).
Para SQL Server o MySQL externos quite el servicio `bd`; para SQL Server defina `CON_SQLSERVER=1`.

## HTTPS (obligatorio para la cámara)

- **Dominio público**: Caddy obtiene y renueva el certificado solo.
- **Red interna**: use un nombre DNS interno y agregue `tls internal` en `despliegue/Caddyfile`; instale la autoridad certificadora de Caddy
  en los teléfonos y equipos. Sin un certificado confiable los navegadores no abren la cámara (los lectores USB/Bluetooth sí funcionan).

## Sin Docker

`uv run wms servir --host 127.0.0.1 --puerto 8000` detrás de un proxy inverso que termine HTTPS.
El backend sirve también el frontend si existe `frontend/out`. En Windows puede registrarse como servicio (NSSM o el Programador de tareas).

Un solo proceso del backend basta para decenas de usuarios. Con varios procesos, deje `WMS_PLANIFICADOR=1` solo en uno
y tenga en cuenta que el límite de intentos de acceso se cuenta por proceso.

## Qué hay que respaldar

| Qué | Dónde | Nota |
|---|---|---|
| Base de datos | Motor elegido | Contiene todo el negocio |
| `instance/config.json` | Volumen `instancia` | Conexión cifrada |
| `instance/archivos/` | Volumen `instancia` | Adjuntos |
| `WMS_CLAVE_SECRETA` | Gestor de secretos | Sin ella no se descifran `config.json` ni las contraseñas de integración |

Recomendación: respaldo completo diario, retención de 30 días, copia fuera del servidor y **una restauración de prueba al mes**.

## Respaldo y restauración por motor

Se usan las herramientas nativas. Detenga el backend antes de restaurar.

### PostgreSQL

```bash
pg_dump -h SERVIDOR -U USUARIO -Fc -f wms_$(date +%F).dump wms
```

```bash
pg_restore -h SERVIDOR -U USUARIO -d wms --clean --if-exists wms_2026-10-06.dump
```

Con Docker: `docker compose -f docker-compose.produccion.yml exec bd pg_dump -U "$BD_USUARIO" -Fc wms > wms.dump`.

### MySQL

```bash
mysqldump -h SERVIDOR -u USUARIO -p --single-transaction --routines wms > wms_$(date +%F).sql
```

```bash
mysql -h SERVIDOR -u USUARIO -p wms < wms_2026-10-06.sql
```

### SQL Server

```sql
BACKUP DATABASE wms TO DISK = N'D:\Respaldos\wms_20261006.bak' WITH COMPRESSION, CHECKSUM, INIT;
```

```sql
ALTER DATABASE wms SET SINGLE_USER WITH ROLLBACK IMMEDIATE;
RESTORE DATABASE wms FROM DISK = N'D:\Respaldos\wms_20261006.bak' WITH REPLACE;
ALTER DATABASE wms SET MULTI_USER;
```

Para recuperación a un punto en el tiempo use el modelo de recuperación completo y respaldos del registro de transacciones.

### Modo Demo (SQLite)

Con el servidor detenido copie `instance/demo.db` (y `demo.db-wal`, `demo.db-shm` si existen). En caliente:

```bash
sqlite3 instance/demo.db ".backup 'respaldo_demo.db'"
```

Restaurar: reemplazar el archivo con el servidor detenido. Para volver a los datos de fábrica: `uv run wms reiniciar-demo`.

### Archivos y configuración

```bash
tar czf wms_instancia_$(date +%F).tgz instance/config.json instance/archivos
```

## Verificación tras restaurar

```bash
uv run wms verificar
```

Comprueba que el saldo de cada existencia coincide con la suma de sus movimientos. Luego revise `/api/salud` y el acceso de un usuario.

## Lista previa a producción

- [ ] `WMS_CLAVE_SECRETA` aleatoria y guardada fuera del servidor.
- [ ] HTTPS activo y `WMS_COOKIE_SEGURA=1`.
- [ ] `WMS_MODO_DEMO` sin definir.
- [ ] Usuario de la base productiva de **solo lectura**.
- [ ] Respaldo automático y restauración probada.
- [ ] Suite de pruebas ejecutada contra el motor elegido (`WMS_URL_BD=… pytest` no aplica tal cual: ver [TESTING](TESTING.md)).
- [ ] Lectura de QR probada en los teléfonos reales y con la impresora de etiquetas definitiva.
