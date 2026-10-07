# Lógica de inventario

## Lote ≠ existencia

- **Lote** (`lotes`): identidad y trazabilidad. Código interno, producto, fechas, estado.
- **Existencia** (`existencias`): una cantidad física concreta de ese lote, en una ubicación, con su fecha de ingreso, su costo unitario y su QR.

Un lote puede tener muchas existencias: `FUNG-26-00125` → `INV-000001` (20 L, Rack A) e `INV-000002` (20 L, Rack B).

## Granularidad: cuántas existencias genera un ingreso

Configurable y heredable (familia → subfamilia → producto). Ejemplo: llegan 20 bidones de 20 L.

| Granularidad | Resultado |
|---|---|
| `POR_ENVASE` | 20 existencias de 20 L, 20 QR. Si se ingresa en la unidad base, se indica la cantidad de envases |
| `POR_LOTE` | 1 existencia de 400 L para el lote |
| `CONSOLIDADA` | 1 existencia de 400 L (registra que agrupa 20 envases) |
| `UNIDAD_LOGISTICA` | 1 existencia por pallet (o las unidades logísticas que se indiquen), cada una con su QR |

## Movimientos

El stock nunca se edita: cada cambio es una fila en `movimientos_inventario`, con cantidad con signo en unidad base, costo unitario y total,
bodega y ubicación de origen y destino, proceso, documento, usuario y motivo.

Tipos: ingreso, salida, consumo, traslado (salida y entrada), ajuste positivo y negativo, devolución, préstamo, devolución de préstamo,
merma, vencimiento, fraccionamiento, anulación — y los que se agreguen en *Configuración*.

**No se borran ni se modifican.** Una corrección es:

- **Anulación**: genera el movimiento inverso (tipo ANULACION) enlazado al original. Un movimiento se anula una sola vez.
- **Ajuste**: documento de ajuste con motivo obligatorio.
- **Anulación del documento**: revierte todos sus movimientos. Un ingreso solo se anula si sus existencias no tienen movimientos posteriores;
  el lote queda ANULADO y su número no se reutiliza.

## Documentos

`BORRADOR` (editable, no afecta stock) → `CONFIRMADO` (genera movimientos inmutables) → `ANULADO`.
Clases: INGRESO, SALIDA, TRASLADO, AJUSTE. Los tipos de ingreso y salida son configurables y pueden exigir documento o proceso.

## Unidades

Cada producto tiene unidad principal (inventario), de compra y de consumo. Las conversiones son datos:
propias del producto (1 bidón = 20 L) o universales (1 L = 1000 ml), y se encadenan (bidón → L → ml). Sin conversión configurada la operación se rechaza.

## Valorización: identificación específica

Cada existencia conserva para siempre el costo unitario de su ingreso.

- Ingreso: 2 bidones a $170.000 → 40 L a **$8.500/L**. Se guardan el valor del documento y su equivalente en unidad base.
- Dos ingresos con costos distintos conviven: 10 L a $8.000 + 20 L a $9.000 = inventario de **$260.000**.
- Consumo: 5 L de la existencia de $9.500 → **$47.500**. No se promedia con otras existencias.
- Redondeo: la salida que deja una existencia en cero se lleva el remanente; entradas y salidas cuadran al peso.
- Valor de inventario = Σ (cantidad física × costo unitario) de cada existencia.
- Un ingreso sin valor unitario se rechaza.

Los promedios que muestre el dashboard son solo analíticos; el movimiento guarda el costo real.

## FIFO y FEFO

| Estrategia | Orden recomendado |
|---|---|
| `FIFO` | Fecha de ingreso más antigua |
| `FEFO` | Vencimiento más próximo |
| `FEFO_FIFO` | Vencimiento y, a igualdad, fecha de ingreso |
| `SIN_RECOMENDACION` | No evalúa |

**La antigüedad se mide por `fecha_ingreso`, nunca por el número de lote.** Un traslado o un fraccionamiento heredan la fecha de ingreso original.

Al consumir la existencia X se buscan otras existencias del mismo producto con stock, disponibles, de lotes disponibles y no vencidos,
en el ámbito configurado (`fifo.ambito`). Si alguna debió usarse antes, se aplica la política:

| Política | Comportamiento |
|---|---|
| `ADVERTIR` | Muestra la advertencia; el usuario puede continuar |
| `BLOQUEAR` | No permite el consumo |
| `JUSTIFICAR` | Exige una justificación escrita |
| `PERMISO` | Exige el permiso `fifo:omitir` |

La advertencia indica producto, lote recomendado, fecha de ingreso, cantidad disponible, bodega y ubicación.
Todo consumo fuera de orden queda en `excepciones_fifo` y genera una alerta.
Ingresos del mismo día no se consideran desviación (`fifo.tolerancia_dias`).

## Estados que impiden consumir

No dependen de la política FIFO: lote BLOQUEADO o en CUARENTENA (permiso `lotes:consumir_bloqueado`), lote VENCIDO o envase
con vida útil tras apertura vencida (`lotes:consumir_vencido`), lote o existencia ANULADOS (nunca).

## Stock físico, reservado, disponible, comprometido

| Concepto | Definición |
|---|---|
| Físico | Suma de `cantidad_fisica` de las existencias |
| Reservado | Saldo pendiente de las reservas ACTIVAS |
| Disponible | Físico − reservado |
| Comprometido | Reservado + cantidades en documentos de salida o traslado en BORRADOR |

Ver [RESERVAS_STOCK](RESERVAS_STOCK.md).

## Concurrencia

- **Descuento atómico**: `UPDATE existencias SET cantidad_fisica = cantidad_fisica - :q WHERE id = :id AND cantidad_fisica >= :q`.
  Si no afecta filas, se responde "stock insuficiente" con el saldo real. Una restricción `CHECK` impide el negativo como última barrera.
- **Serialización por producto**: reservas y salidas bloquean la fila del producto, de modo que el disponible se mide de forma consistente.
- **Idempotencia**: `clave_idempotencia` única; un doble toque o un reintento por mala señal devuelve el mismo movimiento.
- **Proceso**: el consumo verifica y bloquea el estado ABIERTO dentro de su transacción; un cierre simultáneo no deja consumos a medias.

Probado con 12 hilos sobre una existencia de 20 L (solo 6 consumos de 3 L pasan) y con 20 usuarios por HTTP (ver [TESTING](TESTING.md)).

## Operaciones

| Operación | Efecto |
|---|---|
| Traslado total | La existencia cambia de bodega o ubicación y conserva su QR; salida y entrada relacionadas |
| Traslado parcial | Nace una existencia hija con QR propio y el mismo lote, costo y fecha de ingreso |
| Fraccionamiento | Divide en N partes (tambor de 200 L → 4 de 50 L), con sublotes `-01`, `-02` opcionales |
| Apertura de envase | Registra fecha, usuario y cantidad restante; calcula el vencimiento tras apertura |
| Préstamo y devolución | Salida y reingreso a la misma existencia; alerta si vence el plazo |
| Inventario físico | Conteo por bodega o ubicación con escaneo; los ajustes se generan solo tras la autorización |

Stock negativo: no permitido ni configurable en esta versión.
