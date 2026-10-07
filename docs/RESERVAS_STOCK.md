# Reservas de stock

Una reserva **compromete** inventario antes de que ocurra el consumo. No genera movimiento ni descuenta stock físico:
la salida física ocurre únicamente con el movimiento de consumo o salida.

```
stock disponible = stock físico − stock reservado
```

| Concepto | Definición |
|---|---|
| Stock físico | Lo que hay en las existencias |
| Stock reservado | Saldo pendiente (`cantidad − cantidad_consumida`) de las reservas ACTIVAS |
| Stock disponible | Físico − reservado |
| Stock comprometido | Reservado + cantidades en documentos de salida o traslado en borrador |

Se muestran en *Stock* (por producto, bodega, lote o ubicación), en la ficha de la existencia, en el reporte *Stock actual* y en el dashboard.

## Qué se puede reservar

Siempre un **producto** y una cantidad; opcionalmente se acota:

| Nivel | Significado |
|---|---|
| Producto | Cualquier existencia de cualquier bodega |
| Bodega | Stock del producto en esa bodega |
| Lote | Un lote determinado |
| Existencia | Una existencia concreta (hereda su bodega y lote) |

Puede asociarse a un **proceso**, un **área**, un **documento de referencia**, un **motivo** y una **fecha de vencimiento** de la reserva.
Queda registrado el usuario y la fecha.

## Estados

| Estado | Cómo se llega |
|---|---|
| ACTIVA | Al crearla |
| CONSUMIDA | El consumo del proceso asociado completó la cantidad |
| LIBERADA | Liberación manual, o cierre / anulación del proceso |
| VENCIDA | Pasó su fecha límite: se libera sola y genera una alerta |
| ANULADA | Anulación manual (solo si aún no tiene consumos) |

## Reglas

1. **No se reserva más que el disponible** del nivel pedido y de los niveles que lo contienen.
   Excepción: parámetro `reservas.permitir_exceder` activo **y** permiso `reservas:exceder`.
2. **El stock reservado por otros no se consume.** Si la cantidad pedida supera lo libre, el consumo se rechaza indicando cuánto queda
   (parámetro `reservas.bloquean_consumo`). Lo mismo aplica al traslado hacia otra bodega.
3. **El proceso dueño consume su reserva.** Cada consumo de ese proceso y producto reduce la reserva; al completarse queda CONSUMIDA. **No hay doble descuento.**
4. **Anular el consumo devuelve su parte** a la reserva (y la reactiva si estaba consumida).
5. Cerrar o anular el proceso libera sus reservas activas.
6. El stock de lotes bloqueados, en cuarentena o vencidos no respalda reservas.

## Ejemplo

Existencias: 40 L de Fungicida A. Reserva de 20 L para `PROC-000125`.

| Momento | Físico | Reservado | Disponible |
|---|---|---|---|
| Tras reservar | 40 | 20 | 20 |
| Otro proceso consume 20 L | 20 | 20 | 0 |
| Otro proceso intenta 5 L más | rechazado: "el resto está reservado" | | |
| `PROC-000125` consume 8 L | 12 | 12 | 0 |
| `PROC-000125` consume 12 L | 0 | 0 (reserva CONSUMIDA) | 0 |

## Concurrencia

Crear una reserva y consumir bloquean la fila del producto, de modo que dos usuarios no pueden reservar a la vez el mismo saldo.

## Uso

- *Reservas → Nueva reserva*: muestra en vivo físico, reservado y disponible del producto y la bodega elegidos.
- Ficha de existencia → *Reservar*.
- API: `POST /api/reservas`, `GET /api/reservas/disponibilidad`, `POST /api/reservas/{id}/liberar`, `…/anular`.

Tabla: `reservas_stock`. Pruebas: `tests/test_fase4_procesos_reservas.py`.
