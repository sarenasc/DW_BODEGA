# Estado del proyecto

**Fecha de última actualización:** 2026-10-06 (noche)

## Resumen actual

Las nueve fases (0 a 8) están implementadas con backend, frontend, persistencia, migración, permisos, auditoría, pruebas, documentación y datos Demo.
El sistema corre de punta a punta en **Modo Demo (SQLite)** y el guion comercial de 26 pasos pasa como prueba automática.

Lo que falta para producción es **validación en el entorno real**, no desarrollo: ejecutar sobre el motor definitivo, levantar con Docker,
probar cámara, lectores e impresora. Además hay un puñado de funciones menores parciales o no implementadas, listadas abajo sin maquillaje.

## Fase actual

Fase 8 concluida. Siguiente etapa: validación en ambiente de prueba.

## Roadmap

| Fase | Estado | Evidencia |
|---|---|---|
| 0 Fundaciones | Implementada | 13 pruebas; asistente de 8 pasos y acceso recorridos en navegador |
| 1 Maestros | Implementada | 10 pruebas |
| 2 Lotes e inventario | Implementada | 15 pruebas; ingreso verificado en navegador |
| 3 Operación móvil | Implementada | 16 pruebas; consumo verificado en vista de teléfono |
| 4 Procesos y costeo, reservas | Implementada | 11 pruebas |
| 5 Integración productiva | Implementada | 12 pruebas (origen simulado en SQLite) |
| 6 Analítica | Implementada | 16 pruebas |
| 7 Operaciones avanzadas | Implementada | 11 pruebas |
| 8 Bodega visual y endurecimiento | Implementada | Editor 2D y visor 3D en navegador; prueba de carga; revisión de seguridad; respaldo documentado |

Cambio de orden respecto al plan: el backend de todas las fases se construyó y probó antes que el frontend, porque el modelo de datos
se diseñó completo de una vez y así cada pantalla se escribió contra una API ya verificada.

## Auditoría final: requerimientos vs. implementación

Clasificación: **C** completo · **P** parcial · **N** no implementado · **V** requiere validación en hardware o entorno real.

### Plataforma

| Requerimiento | Est. | Nota |
|---|---|---|
| Arquitectura modular, API REST, OpenAPI / Swagger | C | `/api/docs` |
| Frontend sin acceso directo a la base | C | |
| Responsive: teléfono, tablet, notebook, PC | C | Menú lateral en escritorio, navegación inferior en móvil |
| Asistente de instalación de 8 pasos | C | Probado con el motor Demo |
| Un motor por instalación: SQL Server, PostgreSQL, MySQL | **V** | Solo SQL portable; **ninguno de los tres se ha ejecutado** |
| Crear base, tablas, índices, relaciones, migraciones, datos iniciales, administrador | C / V | Verificado en SQLite; creación de base por motor sin probar |
| Modo Demo con un comando | C | `uv run wms demo` verificado |
| Docker: dos Dockerfile y `docker compose up -d` | **V** | Escritos; **Docker no está instalado en el equipo de desarrollo** |
| `.env.example`, sin secretos en el código | C | |
| Usuarios, roles, permisos por módulo y acción (RBAC) | C | |
| Permisos por bodega y por familia | C | |
| Permiso independiente de costos | C | Se eliminan en el backend |
| Auditoría (usuario, fecha, IP, dispositivo, entidad, acción, antes, después, motivo) | C | |
| Hash seguro, tokens, límite de intentos, validación, ORM | C | Ver SECURITY |
| Protección CSRF | C | Por diseño (cabecera de autorización + `SameSite=Strict`) |
| Multiempresa futura no bloqueada | C | `empresa_id`; sin interfaz para varias empresas |
| Idioma en el asistente | P | Solo español; la interfaz no está internacionalizada |
| Temporadas y filtros por temporada | C | |

### Maestros

| Requerimiento | Est. | Nota |
|---|---|---|
| Multi-bodega con jerarquía opcional y configurable | C | |
| Familias → subfamilias → productos con herencia y sobreescritura | C | |
| Maestro de productos con todos los campos base | C | |
| Atributos configurables adicionales | P | Tabla y API existen (`definiciones_atributos`, `productos.atributos`); **sin pantalla** |
| Catálogo de unidades y conversiones almacenadas | C | |
| Proveedores, tipos de bodega, tipos de ingreso / salida / movimiento | C | |
| Uso de serie (`usa_serie`) | P | Se configura y hereda; **no hay registro de números de serie** |

### Lotes

| Requerimiento | Est. | Nota |
|---|---|---|
| Solo lote interno; referencia externa opcional | C | |
| Creador visual por bloques: agregar, eliminar, reordenar, duplicar, configurar, guardar, activar, desactivar | C | Reordenar con flechas (no arrastrando) |
| Todos los tipos de segmento | C | |
| Plantillas asociables a familia, subfamilia o producto | C | |
| Modos automático, semiautomático, manual | C | |
| Momento de creación configurable | P | Se guarda; **el lote se genera siempre al confirmar el ingreso** |
| Alcance y reinicio del correlativo, combinables | C | |
| Generación transaccional sin duplicados | C | 16 hilos |
| Validación previa: ejemplos, colisiones, advertencias | C | |
| Versionado con vigencias; lotes históricos intactos | C | |
| Campos y estados del lote; bloqueado no consumible sin permiso | C | |
| Vencimiento manual o calculado con prioridad | C | |
| Apertura de envase | C | |
| Sublotes y fraccionamiento | C | |

### Inventario

| Requerimiento | Est. | Nota |
|---|---|---|
| Lote ≠ existencia | C | |
| Granularidad configurable y heredable (4 opciones) | C | |
| Ingresos con tipos y documentos parametrizables | C | |
| Valorización obligatoria al ingreso; costo histórico inmutable | C | |
| Capas de costo por existencia | C | |
| Inventario basado en movimientos, con todos los campos | C | |
| Movimientos no se borran: anulación, inverso, ajuste | C | |
| Documentos BORRADOR / CONFIRMADO / ANULADO | C | |
| QR por existencia con token seguro, resuelto por el backend | C | |
| Impresión de etiquetas configurables | C / V | PDF probado; **impresora real sin probar**; sin formato ZPL |
| FIFO por fecha de ingreso; advertencia con todos los datos | C | |
| Cuatro políticas FIFO | C | |
| FEFO, combinada y sin recomendación, heredables | C | |
| Costo de la rebaja con el costo de la existencia | C | |
| Valor de inventario por bodega, familia, subfamilia, producto, lote, ubicación, proveedor | C | |
| Valor de inventario por empresa y temporada | P | Una empresa; el stock no se clasifica por temporada (los consumos sí) |
| Traslados entre bodegas y ubicaciones | C | Inmediatos (sin estado "en tránsito") |
| Préstamos | C | |
| Inventario físico con autorización | C | |
| Stock negativo prohibido | C | No configurable (ver decisiones) |
| Concurrencia sin stock negativo | C | Hilos y prueba HTTP |
| Adjuntos (local) | C | Almacenamiento de objetos (S3): **N** |

### Reservas, alertas, trazabilidad

| Requerimiento | Est. | Nota |
|---|---|---|
| Reservas con estados; físico, reservado, disponible, comprometido | C | |
| Reserva por proceso, área, usuario, documento, motivo, vencimiento | C | |
| No reservar sobre el disponible salvo configuración y permiso | C | |
| Consumo reduce o cierra la reserva; sin doble descuento | C | |
| Centro de alertas persistente, 15 tipos, estados y severidades | C | |
| Reglas configurables | C | |
| Alertas en el dashboard y navegación a la entidad | C | |
| Preparado para correo, Teams, Telegram, WhatsApp | C | Punto de extensión probado; **ningún canal implementado** (no era exigido) |
| Trazabilidad visual adelante y atrás, con línea de tiempo | C | |

### Operación móvil

| Requerimiento | Est. | Nota |
|---|---|---|
| Flujo proceso → escanear → cantidad → registrar → siguiente | C | |
| Últimos consumos con anulación por inverso | C | |
| Tipos de rebaja configurables | C | |
| Cámara en Android Chrome e iPhone Safari | **V** | Implementado (detector nativo + jsQR); **sin probar en teléfonos**; exige HTTPS |
| Lectores USB / Bluetooth | **V** | Implementado como entrada de teclado; sin probar con hardware |
| Botones grandes, tarjetas, uso con una mano | C | |
| Modo sin conexión | N | No requerido; hay idempotencia para reintentos |

### Procesos e integración

| Requerimiento | Est. | Nota |
|---|---|---|
| Estados y acciones abrir / actualizar / cerrar | C | |
| Copia local de toda la información + snapshot | C | |
| Kilos recepcionados, procesados, producidos, despachados y campos adicionales | C | |
| Base de costeo configurable (predeterminada: kilos procesados) | C | |
| Actualizar con auditoría de valor anterior y nuevo | C | |
| "Actualizar y cerrar" principal; "Cerrar sin actualizar" con permiso | C | |
| Conexión, vista o consulta, identificador, mapeo visual, campos adicionales | C | |
| Credenciales cifradas; solo lectura | C | |
| Conexión a SQL Server, PostgreSQL, MySQL productivos | **V** | Probado contra un origen SQLite |
| Costo total, costo por kilo provisorio / definitivo | C | |
| Costeo multidimensional (14 dimensiones) | C | |

### Analítica

| Requerimiento | Est. | Nota |
|---|---|---|
| Dashboard con todos los indicadores pedidos | C | |
| Filtros: fecha, bodega, familia, subfamilia, producto, especie, proceso, productor, temporada | C | Producto y proceso por API y enlaces; en pantalla están los otros siete |
| Dashboard de antigüedad con rangos configurables | C | |
| Reportes (16 exigidos; hay 31) | C | |
| Exportación Excel, CSV, PDF | C | |
| Buscador general | C | |

### Bodega visual

| Requerimiento | Est. | Nota |
|---|---|---|
| Editor en planta: grilla, arrastrar, racks, pasillos, zonas, obstáculos, dimensiones, duplicar, mover, rotar, eliminar, deshacer | C | "Copiar" equivale a duplicar; rotación de 0° / 90° |
| Vista 3D: navegación, consulta, ocupación, antigüedad, vencimiento, valorización | C | |
| Ubicación física ↔ lógica; clic muestra contenido y capacidad | C | |
| Bodegas industriales de miles de posiciones | P | Fluido con cientos; falta instanciado de mallas |
| Demo con 3D atractivo | C | |

### Calidad y documentación

| Requerimiento | Est. | Nota |
|---|---|---|
| Pruebas unitarias, de integración y de API | C | 110 |
| Pruebas básicas de frontend | P | 6 pruebas de utilidades; **sin pruebas de interfaz automatizadas** |
| Los 20 documentos | C | DATABASE y API se generan desde el código |
| Respaldo y restauración por motor | C / V | Documentado; comandos sin ejecutar |
| Prueba de carga | P | Hecha sobre SQLite; falta con motor real |

## Parcialmente implementado (resumen)

1. Momento de creación del lote: se configura, pero siempre se genera al confirmar el ingreso.
2. Atributos configurables de producto: sin pantalla.
3. Números de serie: solo la bandera.
4. Internacionalización: solo español.
5. Visor 3D sin instanciado para bodegas muy grandes.
6. Pruebas automáticas de interfaz.
7. Los parámetros de frecuencia del planificador (30 y 5 minutos) son fijos.
8. Varios mensajes del backend están escritos sin tildes.

## No implementado

- Stock negativo configurable.
- Canales de notificación externos (solo el punto de extensión).
- Almacenamiento de objetos para adjuntos.
- Etiquetas en formato ZPL.
- Estado "en tránsito" en traslados.
- Modo sin conexión.
- Inicio de sesión corporativo y segundo factor.

## Requiere validación en hardware o entorno real

1. **PostgreSQL, MySQL y SQL Server** (instalación, migraciones, operación, concurrencia).
2. **Docker Compose** (demo y producción).
3. **Cámara** en Android e iPhone, bajo HTTPS.
4. **Lectores** USB / Bluetooth.
5. **Impresora** de etiquetas y tamaño real.
6. **Base productiva real**: conexión, consulta y mapeo.
7. Respaldo y restauración.

## Pruebas ejecutadas

- `pytest`: **110 aprobadas, 0 fallidas** (ejecutadas de día y de noche; ver errores corregidos).
- `vitest`: 6 aprobadas. `tsc`: sin errores. Compilación: 36 pantallas.
- Prueba de carga HTTP: 20 usuarios, 300 intentos, verificación correcta.
- Recorrido manual en navegador de las 36 pantallas y de los flujos críticos.

Detalle en [TESTING](TESTING.md).

## Errores conocidos

Ninguno abierto. Corregidos durante el desarrollo (ver [CHANGELOG](CHANGELOG.md)):
consumo de lote bloqueado con permiso; registro de fallos de sincronización; sesión perdida al renovar desde dos pestañas;
primera ejecución que llevaba al acceso en vez del asistente;
**fechas contadas en UTC en vez de la zona de la planta**; precarga de páginas con error 404.

## Decisiones técnicas

Ver la tabla completa en [ARCHITECTURE](ARCHITECTURE.md#decisiones-técnicas). Las que se apartan de lo previsto en el análisis:

- Frontend estático en vez de servidor Next.js.
- Componentes propios en vez del generador de shadcn/ui y de TanStack Query; el cliente de la API no se genera desde OpenAPI.
- Días contados en la zona horaria de la planta.
- No se hicieron commits de git: el repositorio está inicializado y los archivos sin confirmar, a la espera de la decisión del usuario.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Diferencias de comportamiento entre motores | Ejecutar el guion y la suite en el motor elegido antes de producción |
| Cámara sin HTTPS confiable en red interna | Definir dominio y certificado; lector externo como alternativa |
| Carpeta del proyecto dentro de OneDrive | Mover el repositorio fuera de OneDrive (`node_modules` tiene decenas de miles de archivos) |
| Consulta SQL configurable hacia producción | Usuario de solo lectura obligatorio |
| Rendimiento de reportes con mucho volumen | Hoy agregan en memoria; materializar si crece |

## Próximo trabajo

1. Elegir el motor de producción y validar instalación y guion completo.
2. Probar `docker compose up -d`.
3. Definir dominio y HTTPS; probar cámara y lectores en los equipos reales.
4. Conectar la base productiva real y construir el mapeo.
5. Definir la impresora de etiquetas y ajustar la plantilla.
6. Cargar maestros y stock inicial (ingreso tipo "Actualización de stock" con costo).
7. Piloto con una bodega y una familia.
8. Después: pruebas de interfaz, pantalla de atributos, momento de creación del lote, números de serie, canal de correo.
