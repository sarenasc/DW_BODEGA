# Registro de cambios

## [Sin publicar]

### Nuevas funciones

- **Proyección de insumos** (*Producción → Proyección de insumos*): a partir del historial de consumo por especie, se ingresan los kilos
  que faltan por procesar y el sistema calcula la receta pendiente por producto, la compara con el stock disponible (descontando reservas)
  e indica cuánto falta comprar y el costo estimado. API: `GET /api/proyeccion/historial`, `POST /api/proyeccion`.
- **Rebaja por aseo / lavado de línea**: nuevo tipo de salida, sin proceso obligatorio, disponible en el consumo rápido.
  El reporte de consumos muestra el tipo de rebaja.
- **Guardar productos desde el plano**: al hacer clic en una posición o área (2D o 3D) se puede guardar una existencia en ella,
  total o parcialmente. En la planta, al seleccionar un rack se muestra la vista frontal de sus posiciones.
- **Capacidad máxima en envases** por ubicación (`ubicaciones.capacidad_bultos`): un área de tambores o una posición puede limitarse
  por número de envases además de por cantidad; se define desde el panel de la ubicación. Migración inicial regenerada.
- **Responsables del inventario físico**: se registra y muestra, con su rol, quién creó el conteo, quién contó cada existencia
  (`detalles_conteos_inventario.contado_por`) y quién autorizó los ajustes; también en el reporte *Inventario físico*. El Demo incluye un conteo de ejemplo.
- Los catálogos nuevos de una actualización (motivos, permisos, parámetros) se agregan solos al iniciar en instalaciones existentes.

## [1.0.0-rc1] — 2026-10-06

Primera versión completa: fases 0 a 8. Pendiente de validación en el entorno real (ver [PROJECT_STATUS](PROJECT_STATUS.md)).

### Arquitectura

- Monolito modular FastAPI + SQLAlchemy 2 (síncrono) + Alembic; un paquete por módulo en `app/modulos`, reglas de negocio en `app/servicios`.
- Una instalación usa un único motor (SQL Server, PostgreSQL, MySQL o Demo / SQLite), elegido en el asistente.
- Nombres físicos de tablas y columnas en español; rutas de la API en español.
- Frontend Next.js exportado como sitio estático y servido en el mismo origen que la API.
- Los días (vencimientos, antigüedad, consumo del día, filtros por fecha) se cuentan en la zona horaria de la planta (`WMS_ZONA_HORARIA`).
- En SQLite las transacciones se ordenan con un candado del proceso.

### Migraciones

- `0001_esquema_inicial`: 52 tablas con claves foráneas, restricciones únicas, `CHECK` e índices. Regenerable con `scripts/regenerar_migracion.sh` hasta la versión 1.0.

### Nuevas funciones

- **Fase 0** — asistente de instalación de 8 pasos, autenticación con sesión rotativa, RBAC, alcance por bodega y familia, auditoría, parámetros.
- **Fase 1** — maestros parametrizables con herencia; unidades y conversiones; ubicaciones jerárquicas y generación de racks.
- **Fase 2** — creador visual de lotes con plantillas versionadas y validación de colisiones; correlativos transaccionales; documentos de inventario; existencias; libro de movimientos; valorización por existencia; QR y etiquetas PDF.
- **Fase 3** — consumo rápido móvil (cámara, lector externo, teclado numérico), FIFO / FEFO con cuatro políticas, idempotencia, últimos consumos, anulación por movimiento inverso.
- **Fase 4** — procesos, base de costeo configurable, costo total y por kilo, costeo multidimensional, reservas de stock y stock comprometido.
- **Fase 5** — integración de solo lectura con la base productiva: conexiones, fuentes, mapeo visual, importación, snapshots, actualización auditada, cierre sincronizado o manual.
- **Fase 6** — centro de alertas con reglas configurables, dashboard, 31 reportes con exportación a Excel / CSV / PDF, buscador general, trazabilidad visual.
- **Fase 7** — inventario físico, préstamos, traslados, fraccionamiento, sublotes, apertura de envase, adjuntos.
- **Fase 8** — editor de bodega en planta (2D), vista 3D, prueba de carga, revisión de seguridad, guía de respaldo y restauración, Docker.
- **Modo Demo** — empresa ficticia con dos bodegas, 14 productos, lotes, existencias, procesos importados de una base productiva simulada, consumos, reservas, préstamos y alertas.

### Reglas de negocio fijadas

- La antigüedad FIFO se mide por `fecha_ingreso`; un traslado o un fraccionamiento la heredan.
- Cada existencia conserva su costo unitario de ingreso; la salida que la deja en cero absorbe el remanente de redondeo.
- Reservar no descuenta stock. El consumo del proceso dueño reduce la reserva; anular el consumo se la devuelve.
- Un lote bloqueado, en cuarentena o vencido solo se consume con permiso especial y no cuenta como "más antiguo disponible".
- Al cerrar un proceso se congelan los kilos definitivos y la base de costeo utilizada.
- Un documento confirmado es inmutable; se corrige con anulación, movimiento inverso o ajuste.
- El stock de lotes no disponibles no respalda reservas.

### Correcciones durante el desarrollo

- Consumir un lote bloqueado con permiso especial fallaba por "stock reservado".
- El registro de un fallo de sincronización abría una segunda transacción de escritura (bloqueo en SQLite).
- Dos pestañas renovando la sesión a la vez dejaban a una fuera: se agregó una ventana de gracia de 20 s a la rotación.
- **Fechas contadas en UTC**: entre las 21:00 y la medianoche de Chile el sistema consideraba que ya era el día siguiente (vencimientos, antigüedad, consumo del día, filtros). Detectado porque las pruebas fallaban de noche.
- La navegación interna pedía archivos de precarga con un nombre distinto al exportado (404): se agregó un paso posterior a la compilación.
- En la primera ejecución el frontend llevaba a la pantalla de acceso en lugar del asistente.
- El límite de intentos de acceso bloqueaba la prueba de carga (y la dejaba colgada): ahora comparte una sola sesión.

### Conocido

- Sin ejecutar sobre PostgreSQL, MySQL ni SQL Server; Docker sin probar; cámara, lectores e impresora sin validar en hardware.
- Varios mensajes del backend carecen de tildes.
