# Pruebas

## Ejecutar

```bash
cd backend && uv run pytest
```

```bash
cd frontend && npm test
```

```bash
cd frontend && npm run lint
```

Cada módulo de pruebas del backend crea su propia base SQLite temporal con datos base y cuatro usuarios (uno por rol).
Las pruebas llaman a la **API real** (cliente de pruebas de FastAPI), por lo que cubren ruta, validación, permisos, servicio y persistencia a la vez.
La concurrencia se prueba con hilos reales sobre los servicios.

## Resultado actual

| Suite | Pruebas | Resultado |
|---|---|---|
| Backend (`pytest`) | 110 | Todas aprobadas |
| Frontend (`vitest`) | 6 | Todas aprobadas |
| Tipos del frontend (`tsc`) | — | Sin errores |
| Compilación del frontend | 36 pantallas | Correcta |

## Cobertura por área (backend)

| Archivo | Pruebas | Qué verifica |
|---|---|---|
| `test_fase0_fundaciones` | 13 | Instalación completa con migraciones sobre base vacía; acceso correcto e incorrecto; token ausente o falso; rotación de sesión, ventana de gracia y cierre; límite de intentos; permisos por rol; roles editables; clave débil; auditoría con valor anterior y nuevo; alcance por bodega y familia; cifrado; cabeceras |
| `test_fase1_maestros` | 10 | Herencia familia → subfamilia → producto y vuelta a heredar; valores de política válidos; códigos duplicados; conversiones propias, universales y encadenadas; conversión inexistente; racks y códigos jerárquicos; jerarquía libre; temporada actual única; baja lógica |
| `test_fase2_lotes_inventario` | 15 | Todos los segmentos y formatos; detección de colisiones; plantilla inválida no se activa; versionado; ingreso por envase; las cuatro granularidades; reparto sin residuo; capas de costo; validaciones de ingreso; correlativos y lote manual; vencimiento manual y calculado; borrador editable y confirmado inmutable; anulación de ingreso; QR y etiquetas PDF; ocultamiento de costos; **16 hilos generando lotes sin duplicados ni saltos** |
| `test_fase3_consumo` | 16 | Ficha de escaneo; las cuatro políticas FIFO; FIFO por fecha de ingreso y no por número de lote; FEFO y estrategia combinada; tolerancia del mismo día; costo exacto de la existencia; última salida sin residuo; stock insuficiente; conversión de unidad; **doble envío móvil**; proceso no abierto; últimos consumos y anulación por inverso; lote bloqueado, en cuarentena y vencido; alcance por bodega; **12 hilos consumiendo la misma existencia sin stock negativo** |
| `test_fase4_procesos_reservas` | 11 | Ciclo del proceso y ejemplo de $150.000 / 30.000 kg = $5/kg; base de costeo configurable y congelada al cierre; cierre manual; costeo por especie, productor, mes, producto…; reservas: no descuentan, bloqueo a otros procesos, consumo por el dueño, devolución al anular, por bodega / lote / existencia, liberar, anular, exceder con permiso, vencimiento; comprometido |
| `test_fase5_integracion` | 12 | Solo `SELECT`; transformaciones; credenciales cifradas y no expuestas; columnas y vista previa; importación con snapshot; actualización con valor anterior, nuevo y usuario; políticas por campo; actualizar y cerrar; cerrar sin actualizar con permiso; **origen caído sin detener la operación local**; proceso eliminado en origen; sincronización automática; fuente tipo vista |
| `test_fase6_analitica` | 16 | Alertas de stock con resolución automática; vencimientos y reglas configurables; stock antiguo, cuarentena, préstamo vencido; estados de alerta; resumen; canal de notificación extensible; dashboard y filtros; dashboard sin costos; los 31 reportes; contenido; exportación Excel / CSV / PDF; permisos de reportes; buscador; trazabilidad adelante y atrás |
| `test_fase7_operaciones` | 11 | Traslado total y parcial; asignar ubicación; ajuste por documento; inventario físico completo con autorización; préstamo y devolución; fraccionamiento con y sin sublotes; apertura de envase; adjuntos; plano: generación de ubicaciones, protección de stock, ocupación y contenido |
| `test_demo` | 2 | Contenido del Demo y libro cuadrado; **guion comercial de 26 pasos** de punta a punta |

Invariante verificado en varias suites: para toda existencia, saldo = suma de sus movimientos, y nunca negativo.

## Prueba de carga

`backend/scripts/prueba_carga.py` (contra un servidor en marcha; modifica datos, usar el Demo):

```bash
uv run python scripts/prueba_carga.py --url http://127.0.0.1:8000 --usuarios 20 --consumos 15
```

Resultado en el equipo de desarrollo (Modo Demo, SQLite): 20 usuarios simultáneos y 300 intentos sobre una existencia de 450 L →
**180 aceptados, 120 rechazados por stock insuficiente, saldo final 0, un movimiento por consumo aceptado, ningún error**.
18 consumos por segundo; latencia mediana de 1 s con los 20 usuarios encolados (SQLite admite un escritor a la vez).
Con un motor real las escrituras de productos distintos no se encolan entre sí; **esa medición está pendiente**.

## Verificación manual en navegador

Hecha sobre el Modo Demo: acceso; dashboard; las 36 pantallas cargan sin errores; **ingreso** desde el formulario (3 bidones → 30 L, lote generado, 3 existencias);
**consumo rápido** completo en vista de teléfono (advertencia FIFO, teclado, registro, últimos consumos); **actualizar y cerrar** un proceso;
editor en planta y vista 3D.

## Lo que NO se ha probado

| Área | Motivo | Cómo validar |
|---|---|---|
| PostgreSQL, MySQL, SQL Server | No disponibles en el equipo de desarrollo | Instalar con el asistente en un ambiente de prueba y recorrer el guion; la suite puede apuntarse a otro motor adaptando el *fixture* `api` de `tests/conftest.py` |
| Docker (`docker compose`) | Docker no instalado | `docker compose up -d` y abrir el puerto 8080 |
| Cámara en Android / iPhone | Requiere equipos y HTTPS | Escanear etiquetas impresas reales |
| Lectores USB / Bluetooth | Sin hardware | Verificar que el lector envíe Enter al final |
| Impresión de etiquetas | Sin impresora | Imprimir el PDF en la impresora definitiva y ajustar el tamaño de la plantilla |
| Pruebas de interfaz automatizadas | Solo hay pruebas unitarias de utilidades | Agregar Playwright para los flujos críticos |
| Carga con motor real y volumen alto | — | Repetir `prueba_carga.py` y medir reportes con miles de existencias |
