# Integración con la base productiva

```
BASE PRODUCTIVA ──(solo lectura)──> SINCRONIZACIÓN ──> BASE LOCAL DEL WMS ──> OPERACIÓN LOCAL
```

La base productiva es **solo una fuente de sincronización**. La aplicación trabaja sobre su copia local y no necesita una conexión permanente:
si producción no responde, los consumos, las reservas y el stock siguen operando.

## Configuración (Administración → Integraciones)

**1. Conexión.** Motor (SQL Server, PostgreSQL, MySQL), servidor, puerto, base, usuario y contraseña.
La contraseña se guarda cifrada y nunca se devuelve. **Use un usuario de solo lectura.** Botón *Probar*.

**2. Fuente.** De dónde salen los procesos:

- *Vista o tabla*: su nombre (`dbo.vw_procesos`).
- *Consulta SQL*: una única sentencia `SELECT`.
- Columna identificadora del proceso (obligatoria) y columna de fecha (para listar los más recientes).

**3. Mapeo visual.** *Guardar y probar* lee las columnas reales del origen y las muestra; cada una se asigna a un campo interno:

```
peso_neto   →  kilos_procesados
n_lote      →  lote_productivo
kilos_exp   →  extra.kilos_exportables      (campo adicional)
```

Nada se asume: ni nombres de tablas ni de columnas. Las columnas no mapeadas pueden guardarse igualmente como datos adicionales.

| Opción por campo | Valores |
|---|---|
| Transformación | Recortar, mayúsculas, número (acepta `5.200,50`), fecha (varios formatos), factor multiplicador |
| Política de actualización | *Siempre* · *Solo al importar* · *Manual* (nunca se sobrescribe al actualizar) |

La vista previa muestra filas del origen ya transformadas.

Campos internos disponibles: código, número, tipo, fecha, hora de inicio y término, temporada, estado externo, exportadora, productor,
código de productor, campo, predio, especie, variedad, lote productivo, número de lote, **kilos recepcionados, procesados, producidos y despachados**,
cantidad, bins, cajas, turno, línea, guía, recepción relacionada — y cualquier `extra.<clave>`.

## Ciclo de un proceso

| Acción | Qué ocurre |
|---|---|
| **Importar** (*Procesos → Importar desde producción*) | Lista los procesos del origen, marca los ya importados y copia los elegidos a la base local, con su snapshot |
| **Abrir** | El proceso admite consumos y reservas |
| **Actualizar proceso** | Relee el origen, guarda el snapshot crudo y actualiza los campos configurados. Cada cambio queda con valor anterior, valor nuevo, fecha y usuario |
| **Cerrar → Actualizar y cerrar** (opción principal) | Sincroniza por última vez, fija los kilos definitivos y cierra |
| **Cerrar sin actualizar** | Solo con el permiso `procesos:cerrar_sin_sincronizar`; admite digitar los kilos; queda marcado como cierre manual y genera una alerta |
| **Reabrir** | Con permiso especial y motivo |

Al cerrar se registran: última sincronización, si se cerró sincronizado o manual, kilos definitivos, base de costeo usada, usuario y fecha.
**Un proceso cerrado no vuelve a consultar la fuente.**

Ejemplo: 10:00 → 5.000 kg · 13:00 → 15.000 kg · 17:00 → 28.450 kg. Cada *Actualizar* deja una línea en el historial; el costo por kilo se
muestra como **provisorio** hasta el cierre.

## Sincronización automática

Opcional por fuente (*Sincronización automática*, en minutos; 0 = solo manual). Una tarea interna actualiza los procesos **abiertos**
cuya última sincronización supera ese intervalo. Requiere `WMS_PLANIFICADOR=1`.

## Fallas

| Situación | Comportamiento |
|---|---|
| Origen caído al actualizar | Error 502; se registra la ejecución fallida y una alerta *Error de sincronización*; el proceso no cambia |
| Origen caído al cerrar | El cierre no se realiza (nada queda a medias). Puede reintentarse o cerrarse sin actualizar con permiso |
| El proceso ya no existe en el origen | Se informa; **la copia local se conserva** |
| Dato no convertible (texto en un campo numérico) | Error indicando el valor |

Una sincronización correcta resuelve las alertas pendientes del proceso. El historial está en *Integraciones → Historial de sincronización*.

## Seguridad

- Solo `SELECT`: se rechazan `;`, `INSERT`, `UPDATE`, `DELETE`, `DROP`, `EXEC`, `INTO`, etc. Es una segunda barrera;
  la principal es el usuario de solo lectura.
- El identificador del proceso viaja como parámetro enlazado. Límite de 500 filas por lectura y tiempos máximos de conexión.
- Solo el permiso `integraciones:administrar` ve y edita conexiones, consultas y mapeos.

## Modo Demo

Incluye una base productiva simulada (`instance/produccion_demo.db`) con 10 corridas de packing, ya conectada y mapeada.
Ocho están importadas (seis cerradas, dos abiertas) y dos quedan disponibles para importar.
"Producción" ya avanzó en `PK-1007` y `PK-1008`: al pulsar *Actualizar proceso* los kilos cambian (5.000 → 15.000).

## Estado de validación

Probado de punta a punta contra una base externa SQLite. **Las conexiones a SQL Server, PostgreSQL y MySQL productivos requieren validación en el entorno real.**
