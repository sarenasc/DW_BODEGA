# QR y consumo rápido

## Qué identifica el QR

Una **existencia concreta**, no un producto.

| Dato | Ejemplo | Uso |
|---|---|---|
| Id interno | `1582` | Clave en la base |
| Código público | `INV-000001582` | Lo que ve y puede digitar el usuario |
| Token QR | `K7Q2M4…` (128 bits aleatorios) | Contenido del QR |

El QR contiene `{URL}/q/{token}` y **ningún dato de negocio**. El backend resuelve el token (exige sesión y alcance sobre la bodega).
El lector acepta la URL completa, el token solo o el código `INV-…`, e ignora el dominio: las etiquetas siguen sirviendo si cambia el servidor.

## Etiquetas

Tras confirmar un ingreso: **Imprimir QR**. También desde *Existencias y QR* (selección múltiple) o desde la ficha.

- PDF con una etiqueta por página, del tamaño de la plantilla (100 × 60 mm por defecto).
- Campos configurables: QR, código público, código y nombre del producto, lote, fecha de ingreso, vencimiento, cantidad, bodega, ubicación.
- La cantidad impresa es la **inicial**; el saldo vigente se consulta escaneando.
- Cada impresión queda auditada y se cuenta en la existencia.
- Un traslado parcial o un fraccionamiento crean existencias nuevas que requieren su etiqueta.

## Consumo rápido

Pantalla *Consumo rápido*, pensada para el teléfono y para usarse con una mano.

1. **Proceso fijado** — se elige una vez y queda recordado en el dispositivo. Otros tipos de rebaja (merma, consumo interno…) no exigen proceso.
2. **Escanear** — cámara, lector USB/Bluetooth, digitar el código o elegir de la lista.
3. **Ficha** — producto, lote, fecha de ingreso, disponible, vencimiento y la **advertencia FIFO / FEFO** si corresponde, con el lote recomendado, su ubicación y un botón para usarlo.
4. **Cantidad** — teclado numérico grande; botón *Todo*.
5. **Registrar** — descuenta, valoriza con el costo de esa existencia y asocia al proceso. Vibración y sonido de confirmación.
6. La pantalla vuelve sola a **Escanear**.

**Últimos consumos** aparece debajo (hora, producto, cantidad). Con permiso `movimientos:anular` se puede **anular**: genera el movimiento inverso; nada se elimina.

Cada ficha lleva una clave de idempotencia: un doble toque o un reintento por mala señal no duplica el consumo.

## Medios de lectura

| Medio | Funcionamiento | Estado |
|---|---|---|
| Lector USB / Bluetooth | Actúa como teclado: escribe el código y envía Enter. El campo recupera el foco solo | Lógica probada digitando el código |
| Cámara, Android Chrome | `BarcodeDetector` nativo | Requiere validación en equipo real |
| Cámara, iPhone Safari | Decodificación con jsQR | Requiere validación en equipo real |
| Digitación / lista | Código `INV-…` o búsqueda | Probado |

**La cámara exige HTTPS** (o `localhost`). Sin un certificado confiable el navegador no la abre; la pantalla lo informa y ofrece digitar.

## Otros usos del escaneo

- *Escanear* (menú inferior): abre la ficha de la existencia con sus acciones (ubicar, trasladar, fraccionar, reservar, prestar, abrir envase).
- *Inventario físico*: escanear y digitar la cantidad encontrada.
- Cámara nativa del teléfono: al leer la etiqueta abre `/q/{token}`, que lleva a la ficha (pide iniciar sesión si hace falta).
