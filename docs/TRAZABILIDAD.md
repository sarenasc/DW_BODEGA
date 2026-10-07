# Trazabilidad

Pantalla *Producción → Trazabilidad*. Permite recorrer la cadena completa en ambos sentidos.

## Hacia adelante — desde un lote

```
DOCUMENTO de ingreso → LOTE → EXISTENCIAS → MOVIMIENTOS / CONSUMOS → PROCESOS
```

Responde: *¿dónde terminó este lote?* Incluye sublotes y las existencias nacidas de traslados parciales o fraccionamientos.

## Hacia atrás — desde un proceso

```
PROCESO → CONSUMOS → EXISTENCIAS → LOTES → INGRESOS → DOCUMENTOS (y proveedor)
```

Responde: *¿qué se aplicó en este proceso y de dónde vino?* Agrega el resumen de productos consumidos con cantidad, costo y lotes utilizados.

## Desde una existencia

Su lote, su documento de origen, la existencia de la que se dividió (si corresponde), sus movimientos y los procesos que la consumieron.

## Cómo se usa

- Buscar por **lote**, **proceso**, **existencia / QR** o **producto** (este último lista sus lotes para elegir).
- O llegar con el botón **Trazabilidad** desde la ficha de un lote, un proceso, una existencia o un producto.

| Vista | Contenido |
|---|---|
| **Cadena** | Una columna por tipo de entidad. Al pasar el cursor sobre un elemento se resalta su cadena completa y se atenúa el resto. Cada tarjeta abre su entidad |
| **Línea de tiempo** | Todos los eventos en orden: ingreso, traslado, fraccionamiento, consumo, anulación — con fecha, usuario, cantidad, costo y motivo |
| **Productos consumidos** | Solo desde un proceso |

Las anulaciones aparecen como movimientos propios, marcadas, porque nada se elimina del libro.

## Reglas

- Requiere el permiso `trazabilidad:ver`. Los costos solo se muestran con `costos:ver`.
- Se respeta el alcance por bodega y familia del usuario.
- La trazabilidad usa siempre el **lote interno**; la referencia externa del proveedor es solo un dato del lote.

## API

`GET /api/trazabilidad/lote/{id}` · `/proceso/{id}` · `/existencia/{id}` · `/producto/{id}`.
Devuelve `columnas` (nodos por tipo), `enlaces` (origen → destino), `linea_tiempo` y `resumen`.

Servicio: `app/modulos/trazabilidad.py`. Pruebas: `tests/test_fase6_analitica.py`, `tests/test_demo.py`.
