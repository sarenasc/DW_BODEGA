# API REST

> Listado generado desde OpenAPI (`python scripts/generar_docs.py`). La referencia interactiva completa, con esquemas de entrada,
> esta en **`/api/docs`** (Swagger) y **`/api/openapi.json`** del servidor en marcha.

## Convenciones

- Base: `/api`. Rutas en espanol, coherentes con los nombres de tablas.
- **Autenticacion:** `POST /api/auth/login` devuelve un token de acceso de corta duracion (cabecera `Authorization: Bearer <token>`)
  y deja la sesion renovable en una cookie `httpOnly`. `POST /api/auth/refrescar` entrega un token nuevo.
- **Permisos:** cada operacion exige un permiso `modulo:accion` y respeta el alcance por bodega y familia del usuario.
  Sin el permiso `costos:ver` los campos de costo y valor llegan en `null`.
- **Errores:** `{"codigo": "STOCK_INSUFICIENTE", "mensaje": "...", "datos": {...}}`. El `codigo` es estable; el `mensaje` es para mostrar.
  401 sin sesion, 403 sin permiso, 404 inexistente o fuera de alcance, 409 conflicto de negocio, 422 entrada invalida, 429 demasiados intentos.
- **Listados:** `?q=&pagina=&tam=` y devuelven `{"total", "pagina", "tam", "items"}`.
- **Fechas:** UTC en ISO 8601 con sufijo `Z`. Las fechas sin hora son dias locales (`AAAA-MM-DD`).
- **Idempotencia:** `POST /api/consumos` acepta `clave_idempotencia`; repetir el envio devuelve el mismo movimiento con `duplicado: true`.
- **Advertencia FIFO:** un consumo fuera de orden responde 409 `FIFO_ADVERTENCIA` con la existencia recomendada en `datos`;
  se reenvia con `confirmar_fifo: true` (o `justificacion`, segun la politica).

## Operaciones (200)


### Adjuntos

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/adjuntos` | Listar |
| `POST` | `/api/adjuntos` | Subir |
| `DELETE` | `/api/adjuntos/{id_}` | Eliminar |
| `GET` | `/api/adjuntos/{id_}/descargar` | Descargar |

### Alertas

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/alertas` | Listar |
| `POST` | `/api/alertas` | Crear |
| `POST` | `/api/alertas/evaluar` | Ejecuta ahora la evaluacion de reglas (el planificador la corre periodicamente). |
| `GET` | `/api/alertas/opciones` | Opciones |
| `GET` | `/api/alertas/resumen` | Resumen |
| `POST` | `/api/alertas/{id_}/estado` | Cambiar Estado |
| `GET` | `/api/reglas-alertas` | Reglas |
| `PUT` | `/api/reglas-alertas/{id_}` | Editar Regla |

### Autenticacion

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/api/auth/cambiar-clave` | Cambiar Clave |
| `POST` | `/api/auth/login` | Login |
| `POST` | `/api/auth/refrescar` | Refrescar |
| `POST` | `/api/auth/salir` | Salir |
| `GET` | `/api/auth/yo` | Yo |

### Bodegas

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/bodegas` | Listar Bodega |
| `POST` | `/api/bodegas` | Crear Bodega |
| `GET` | `/api/bodegas/{id_}` | Obtener Bodega |
| `PUT` | `/api/bodegas/{id_}` | Editar Bodega |
| `DELETE` | `/api/bodegas/{id_}` | Eliminar Bodega |
| `GET` | `/api/bodegas/{id_}/ocupacion` | Resumen por ubicacion para colorear el visor: cantidad, valor, antiguedad y vencimiento. |
| `GET` | `/api/bodegas/{id_}/plano` | Ver Plano |
| `PUT` | `/api/bodegas/{id_}/plano` | Publica el plano editado. Los racks nuevos generan sus ubicaciones; los eliminados las desactivan. |
| `POST` | `/api/bodegas/{id_}/racks` | Nuevo Rack |
| `GET` | `/api/ubicaciones` | Listar Ubicaciones |
| `POST` | `/api/ubicaciones` | Nueva Ubicacion |
| `PUT` | `/api/ubicaciones/{id_}` | Editar Ubicacion |
| `GET` | `/api/ubicaciones/{id_}/contenido` | Contenido |

### Consumo rapido y QR

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/consumo/escanear` | Paso 2-3 del flujo: resuelve el QR y entrega la ficha con la advertencia FIFO/FEFO si corresponde. |
| `POST` | `/api/consumos` | Paso 4-5: el usuario solo indica la cantidad. Descuenta, valoriza y asocia al proceso en una transaccion. |
| `GET` | `/api/consumos/recientes` | Ultimos consumos para la pantalla movil, con indicacion de si pueden anularse. |
| `GET` | `/api/etiquetas` | Etiquetas |
| `GET` | `/api/existencias/{id_}/qr` | Qr Svg |

### Dashboard

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/dashboard` | Dashboard |

### Instalacion

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/api/instalacion/crear-estructura` | Paso 5 del asistente: crea la base si falta y ejecuta las migraciones (tablas, indices, relaciones). |
| `POST` | `/api/instalacion/ejecutar` | Ejecutar |
| `GET` | `/api/instalacion/estado` | Estado |
| `POST` | `/api/instalacion/probar-conexion` | Probar |

### Integraciones

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/integraciones/conexiones` | Listar Conexiones |
| `POST` | `/api/integraciones/conexiones` | Crear Conexion |
| `PUT` | `/api/integraciones/conexiones/{id_}` | Editar Conexion |
| `DELETE` | `/api/integraciones/conexiones/{id_}` | Eliminar Conexion |
| `POST` | `/api/integraciones/conexiones/{id_}/probar` | Probar Conexion |
| `GET` | `/api/integraciones/ejecuciones` | Ejecuciones |
| `GET` | `/api/integraciones/fuentes` | Listar Fuentes |
| `POST` | `/api/integraciones/fuentes` | Crear Fuente |
| `PUT` | `/api/integraciones/fuentes/{id_}` | Editar Fuente |
| `DELETE` | `/api/integraciones/fuentes/{id_}` | Eliminar Fuente |
| `GET` | `/api/integraciones/fuentes/{id_}/columnas` | Columnas reales del origen, para ofrecerlas en el mapeo visual. Nada se asume de la base productiva. |
| `GET` | `/api/integraciones/fuentes/{id_}/disponibles` | Procesos existentes en produccion, indicando cuales ya fueron importados. |
| `POST` | `/api/integraciones/fuentes/{id_}/importar` | Importar |
| `GET` | `/api/integraciones/fuentes/{id_}/vista-previa` | Filas de ejemplo: crudas y ya transformadas por el mapeo. |
| `GET` | `/api/integraciones/opciones` | Opciones |

### Inventario

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/documentos` | Listar Documentos |
| `POST` | `/api/documentos` | Crear Documento |
| `GET` | `/api/documentos/{id_}` | Ver Documento |
| `PUT` | `/api/documentos/{id_}` | Editar Documento |
| `POST` | `/api/documentos/{id_}/anular` | Anular |
| `POST` | `/api/documentos/{id_}/confirmar` | Confirmar |
| `GET` | `/api/existencias` | Listar Existencias |
| `GET` | `/api/existencias/por-codigo` | Por Codigo |
| `GET` | `/api/existencias/{id_}` | Ver Existencia |
| `POST` | `/api/existencias/{id_}/bloqueo` | Bloquear Existencia |
| `POST` | `/api/existencias/{id_}/ubicar` | Asigna o cambia la ubicacion dentro de la misma bodega (queda registrado como traslado). |
| `GET` | `/api/movimientos` | Listar Movimientos |
| `POST` | `/api/movimientos/{id_}/anular` | No elimina el movimiento: genera su inverso y deja ambos en el libro. |
| `GET` | `/api/productos/{id_}/politica-ingreso` | Lo que el formulario de ingreso necesita saber del producto: lote, vencimiento, ubicacion, granularidad. |
| `GET` | `/api/stock` | Stock fisico, reservado, disponible y comprometido. agrupar: producto | bodega | lote | ubicacion. |

### Lotes

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/lotes` | Listar Lotes |
| `GET` | `/api/lotes/{id_}` | Ver Lote |
| `PUT` | `/api/lotes/{id_}` | El codigo del lote es inmutable. Solo se corrigen datos descriptivos, con auditoria. |
| `POST` | `/api/lotes/{id_}/estado` | Cambiar Estado |
| `GET` | `/api/plantillas-lotes` | Listar |
| `POST` | `/api/plantillas-lotes` | Crear |
| `GET` | `/api/plantillas-lotes/opciones` | Opciones |
| `POST` | `/api/plantillas-lotes/vista-previa` | Usa el mismo motor que la generacion real: lo que se ve es lo que se generara. |
| `GET` | `/api/plantillas-lotes/{id_}` | Ver |
| `PUT` | `/api/plantillas-lotes/{id_}` | Editar |
| `POST` | `/api/plantillas-lotes/{id_}/activar` | Publica el borrador como nueva version vigente. Los lotes historicos conservan su version. |
| `POST` | `/api/plantillas-lotes/{id_}/desactivar` | Desactivar |
| `POST` | `/api/plantillas-lotes/{id_}/reiniciar-correlativo` | Reinicio manual: cambia la epoca del contador. Requiere que el codigo siga siendo unico. |

### Maestros

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/catalogos` | Listas cortas para poblar selectores del frontend en una sola llamada. |
| `GET` | `/api/conversiones` | Listar Conversion |
| `POST` | `/api/conversiones` | Crear Conversion |
| `GET` | `/api/conversiones-calcular` | Calcular Conversion |
| `GET` | `/api/conversiones/{id_}` | Obtener Conversion |
| `PUT` | `/api/conversiones/{id_}` | Editar Conversion |
| `DELETE` | `/api/conversiones/{id_}` | Eliminar Conversion |
| `GET` | `/api/definiciones-atributos` | Listar Definicion Atributo |
| `POST` | `/api/definiciones-atributos` | Crear Definicion Atributo |
| `GET` | `/api/definiciones-atributos/{id_}` | Obtener Definicion Atributo |
| `PUT` | `/api/definiciones-atributos/{id_}` | Editar Definicion Atributo |
| `DELETE` | `/api/definiciones-atributos/{id_}` | Eliminar Definicion Atributo |
| `GET` | `/api/familias` | Listar Familia |
| `POST` | `/api/familias` | Crear Familia |
| `GET` | `/api/familias/{id_}` | Obtener Familia |
| `PUT` | `/api/familias/{id_}` | Editar Familia |
| `DELETE` | `/api/familias/{id_}` | Eliminar Familia |
| `GET` | `/api/motivos-movimiento` | Listar Motivo Movimiento |
| `POST` | `/api/motivos-movimiento` | Crear Motivo Movimiento |
| `GET` | `/api/motivos-movimiento/{id_}` | Obtener Motivo Movimiento |
| `PUT` | `/api/motivos-movimiento/{id_}` | Editar Motivo Movimiento |
| `DELETE` | `/api/motivos-movimiento/{id_}` | Eliminar Motivo Movimiento |
| `GET` | `/api/plantillas-etiquetas` | Listar Plantilla Etiqueta |
| `POST` | `/api/plantillas-etiquetas` | Crear Plantilla Etiqueta |
| `GET` | `/api/plantillas-etiquetas/{id_}` | Obtener Plantilla Etiqueta |
| `PUT` | `/api/plantillas-etiquetas/{id_}` | Editar Plantilla Etiqueta |
| `DELETE` | `/api/plantillas-etiquetas/{id_}` | Eliminar Plantilla Etiqueta |
| `GET` | `/api/productos` | Listar Producto |
| `POST` | `/api/productos` | Crear Producto |
| `GET` | `/api/productos/{id_}` | Obtener Producto |
| `PUT` | `/api/productos/{id_}` | Editar Producto |
| `DELETE` | `/api/productos/{id_}` | Eliminar Producto |
| `GET` | `/api/productos/{id_}/convertir` | Convertir Producto |
| `GET` | `/api/productos/{id_}/detalle` | Detalle Producto |
| `GET` | `/api/proveedores` | Listar Proveedor |
| `POST` | `/api/proveedores` | Crear Proveedor |
| `GET` | `/api/proveedores/{id_}` | Obtener Proveedor |
| `PUT` | `/api/proveedores/{id_}` | Editar Proveedor |
| `DELETE` | `/api/proveedores/{id_}` | Eliminar Proveedor |
| `GET` | `/api/subfamilias` | Listar Subfamilia |
| `POST` | `/api/subfamilias` | Crear Subfamilia |
| `GET` | `/api/subfamilias/{id_}` | Obtener Subfamilia |
| `PUT` | `/api/subfamilias/{id_}` | Editar Subfamilia |
| `DELETE` | `/api/subfamilias/{id_}` | Eliminar Subfamilia |
| `GET` | `/api/temporadas` | Listar Temporada |
| `POST` | `/api/temporadas` | Crear Temporada |
| `GET` | `/api/temporadas/{id_}` | Obtener Temporada |
| `PUT` | `/api/temporadas/{id_}` | Editar Temporada |
| `DELETE` | `/api/temporadas/{id_}` | Eliminar Temporada |
| `GET` | `/api/tipos-bodega` | Listar Tipo Bodega |
| `POST` | `/api/tipos-bodega` | Crear Tipo Bodega |
| `GET` | `/api/tipos-bodega/{id_}` | Obtener Tipo Bodega |
| `PUT` | `/api/tipos-bodega/{id_}` | Editar Tipo Bodega |
| `DELETE` | `/api/tipos-bodega/{id_}` | Eliminar Tipo Bodega |
| `GET` | `/api/tipos-movimiento` | Listar Tipo Movimiento |
| `POST` | `/api/tipos-movimiento` | Crear Tipo Movimiento |
| `GET` | `/api/tipos-movimiento/{id_}` | Obtener Tipo Movimiento |
| `PUT` | `/api/tipos-movimiento/{id_}` | Editar Tipo Movimiento |
| `DELETE` | `/api/tipos-movimiento/{id_}` | Eliminar Tipo Movimiento |
| `GET` | `/api/unidades` | Listar Unidad |
| `POST` | `/api/unidades` | Crear Unidad |
| `GET` | `/api/unidades/{id_}` | Obtener Unidad |
| `PUT` | `/api/unidades/{id_}` | Editar Unidad |
| `DELETE` | `/api/unidades/{id_}` | Eliminar Unidad |

### Operaciones

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/conteos` | Listar Conteos |
| `POST` | `/api/conteos` | Abre el conteo y toma la foto del stock del sistema en la bodega o ubicacion elegida. |
| `GET` | `/api/conteos/{id_}` | Ver Conteo |
| `POST` | `/api/conteos/{id_}/anular` | Anular Conteo |
| `POST` | `/api/conteos/{id_}/autorizar` | Genera los ajustes (movimientos AJUSTE_POSITIVO / AJUSTE_NEGATIVO) de las diferencias aprobadas. |
| `POST` | `/api/conteos/{id_}/cerrar` | Termina el conteo y lo deja en revision. Los ajustes no se aplican hasta la autorizacion. |
| `POST` | `/api/conteos/{id_}/contar` | Registra la cantidad encontrada y muestra la diferencia contra el sistema. |
| `POST` | `/api/existencias/{id_}/abrir` | Registra fecha, usuario y cantidad restante al abrir. Calcula la vida util tras apertura si esta configurada. |
| `POST` | `/api/existencias/{id_}/fraccionar` | Divide una existencia en varias (p. ej. tambor de 200 L en 4 bidones de 50 L), con sublotes opcionales. |
| `GET` | `/api/prestamos` | Listar Prestamos |
| `POST` | `/api/prestamos` | Crear Prestamo |
| `POST` | `/api/prestamos/{id_}/devolver` | Devolver |

### Procesos

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/costos` | Costeo multidimensional: por proceso, especie, productor, variedad, temporada, semana, mes, producto, familia, bodega... |
| `GET` | `/api/procesos` | Listar |
| `POST` | `/api/procesos` | Proceso manual (sin origen externo), p. ej. una sanitizacion. |
| `GET` | `/api/procesos/valores` | Valores distintos de las dimensiones de proceso, para los filtros (no hay catalogos fijos de especies o productores). |
| `GET` | `/api/procesos/{id_}` | Ver |
| `PUT` | `/api/procesos/{id_}` | Edicion manual. Cada cambio queda en el historial con valor anterior y nuevo. |
| `POST` | `/api/procesos/{id_}/abrir` | Abrir |
| `POST` | `/api/procesos/{id_}/actualizar` | Consulta nuevamente la base productiva y actualiza los campos configurados. |
| `POST` | `/api/procesos/{id_}/anular` | Anular |
| `GET` | `/api/procesos/{id_}/capturas` | Capturas |
| `POST` | `/api/procesos/{id_}/cerrar` | Cerrar |
| `GET` | `/api/procesos/{id_}/consumos` | Consumos asociados al proceso, con existencia QR, lote, costo, usuario, bodega y ubicacion. |
| `POST` | `/api/procesos/{id_}/reabrir` | Reabrir |

### Proyeccion de insumos

| Metodo | Ruta | Descripcion |
|---|---|---|
| `POST` | `/api/proyeccion` | Receta que falta por aplicar: kilos pendientes por especie x consumo historico por kilo, comparada con el stock disponible. |
| `GET` | `/api/proyeccion/historial` | Base del calculo: por especie, kilos procesados, cantidad de procesos y gasto historico por kilo. |

### Reportes

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/buscar` | Buscador general: producto, codigo, lote, QR, ubicacion, documento y proceso. |
| `GET` | `/api/reportes` | Listar |
| `GET` | `/api/reportes/{codigo}` | Ejecutar |

### Reservas de stock

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/reservas` | Listar |
| `POST` | `/api/reservas` | Crear |
| `GET` | `/api/reservas/disponibilidad` | Ver Disponibilidad |
| `POST` | `/api/reservas/{id_}/anular` | Anular |
| `POST` | `/api/reservas/{id_}/liberar` | Devuelve al disponible el saldo no consumido. |

### Sistema

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/salud` | Salud |

### Trazabilidad

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/trazabilidad/existencia/{id_}` | Desde Existencia |
| `GET` | `/api/trazabilidad/lote/{id_}` | Lote -> ingreso -> documento -> existencias -> movimientos -> consumos -> procesos. |
| `GET` | `/api/trazabilidad/proceso/{id_}` | Proceso -> consumos -> productos -> existencias -> lotes -> ingresos -> documentos. |
| `GET` | `/api/trazabilidad/producto/{id_}` | Lotes de un producto, como punto de entrada a la trazabilidad. |

### Usuarios y configuracion

| Metodo | Ruta | Descripcion |
|---|---|---|
| `GET` | `/api/auditoria` | Listar Auditoria |
| `GET` | `/api/configuraciones` | Listar Config |
| `PUT` | `/api/configuraciones/{clave}` | Fijar Config |
| `GET` | `/api/empresa` | Ver Empresa |
| `PUT` | `/api/empresa` | Editar Empresa |
| `GET` | `/api/permisos` | Listar Permisos |
| `GET` | `/api/roles` | Listar Roles |
| `POST` | `/api/roles` | Crear Rol |
| `PUT` | `/api/roles/{id_}` | Editar Rol |
| `DELETE` | `/api/roles/{id_}` | Eliminar Rol |
| `GET` | `/api/usuarios` | Listar Usuarios |
| `POST` | `/api/usuarios` | Crear Usuario |
| `PUT` | `/api/usuarios/{id_}` | Editar Usuario |
