# Lógica de lotes

El sistema usa **solo lote interno**. Un código del proveedor puede guardarse como `referencia_externa`, pero no participa en FIFO, QR ni trazabilidad.

## ¿El producto usa lote?

Sí · No · Heredar de la subfamilia o familia. Sin lote el producto maneja stock agregado (sus existencias no llevan lote).

## Plantillas

Una plantilla define cómo se construye el código mediante **segmentos** ordenados. Se asocia a una familia, subfamilia o producto.

| Grupo | Segmentos | Configuración |
|---|---|---|
| Literales | Texto fijo, Separador | Valor |
| Fecha | Año (2 o 4 dígitos), Mes (10 / OCT / OCTUBRE), Día, Fecha (`YYYYMMDD`, `DDMMYYYY`, `YYMMDD`, `YYYY-MM-DD`, `DD-MM-YYYY`), Fecha/hora | Formato |
| Numeración | Correlativo | Largo, valor inicial |
| Contexto | Código de producto, familia, subfamilia, bodega, empresa, temporada; usuario, turno, proceso | Largo máximo |
| Entrada | Campo manual | Etiqueta, validación (expresión regular), obligatorio |

Ejemplo: `[Subfamilia] [-] [Año 2] [-] [Correlativo 5]` → `FUNG-26-00001`.

El constructor visual permite agregar, eliminar, reordenar, duplicar y configurar bloques, con **vista previa en vivo**
calculada por el mismo motor que genera los lotes reales.

## Correlativo: alcance y reinicio

En lugar de un tipo de correlativo por cada caso, hay **un** segmento correlativo y dos propiedades de la plantilla:

- **Alcance** — numeración separada por cualquier combinación de: empresa, bodega, familia, subfamilia, producto, temporada, proceso.
- **Reinicio** — nunca, diario, mensual, anual, por temporada, manual.

Así se obtienen el correlativo global, diario, mensual, anual, por producto, etc. y sus combinaciones.

El contador se identifica por una clave formada por el alcance y el período (`SUBFAMILIA=FUNG|A=2026`).
Al cambiar el período cambia la clave y la numeración parte de 1: el reinicio es implícito. El reinicio manual incrementa una "época".

## Generación transaccional

Dentro de la **misma transacción** que crea el lote:

1. `UPDATE contadores_lotes SET ultimo_valor = ultimo_valor + 1 WHERE plantilla_id = … AND clave_alcance = …` (toma el bloqueo de la fila).
2. Si no existe, se inserta con valor 1; si otra transacción la creó a la vez, se reintenta.
3. Se arma el código y se inserta el lote. `UNIQUE (empresa_id, codigo)` es la última barrera.

Dos usuarios simultáneos quedan en fila; si la operación falla, el contador se revierte con ella (no hay saltos).
Probado con 16 hilos: 16 lotes únicos y consecutivos.

## Modos y momento de creación

| Modo | Comportamiento |
|---|---|
| Automático | El sistema genera el código |
| Semiautomático | Se genera, pero el usuario puede digitar uno propio o completar campos manuales |
| Manual | El usuario digita el lote; se valida formato y unicidad |

Un producto que usa lote y no tiene plantilla activa exige digitar el lote.

El momento de creación (al crear o confirmar la recepción, al ingresar a bodega, al imprimir QR, al crear el proceso, manual) se guarda
en la plantilla. **En esta versión el lote se genera siempre al confirmar el ingreso**; los demás momentos quedan registrados pero no cambian el comportamiento.

## Validación antes de activar

Al guardar o activar se simulan productos, bodegas y cruces de período (día siguiente, mes siguiente, 31 de diciembre → 1 de enero):

- **Error** si un código se repetiría: reinicio periódico sin ese período en el código, o alcance por una dimensión que el código no refleja.
- **Error** si falta el correlativo en modo automático, si hay más de uno, o si el código supera 60 caracteres.
- **Advertencia** por correlativo corto (se desborda) o campo manual sin validación.

Una plantilla con errores no se activa.

## Versionado

Editar una plantilla activa **no la modifica**: crea un borrador. Al activarlo pasa a ser la versión vigente y la anterior queda retirada
con su fecha de término. Cada lote guarda la versión con que se generó; **los lotes históricos no cambian**.

## Estados del lote

| Estado | Significado | Consumo |
|---|---|---|
| DISPONIBLE | Normal | Sí |
| BLOQUEADO | Retenido | Solo con permiso especial |
| CUARENTENA | En espera de liberación | Solo con permiso especial |
| VENCIDO | Fecha de vencimiento superada (lo asigna el sistema) | Solo con permiso especial |
| AGOTADO | Sin stock (automático; vuelve a DISPONIBLE si reingresa stock) | — |
| ANULADO | Su ingreso fue anulado; el número no se reutiliza | Nunca |

Cada cambio queda en el historial con usuario, fecha y motivo.

## Vencimiento

Manual o calculado (fecha de fabricación + vida útil en meses). La prioridad entre ambos es configurable.
Un producto que usa vencimiento no puede ingresar sin fecha (ni forma de calcularla).

## Sublotes

Al fraccionar, cada parte puede recibir un sublote del lote original: `FUNG-26-00125-01`, `-02`…, enlazado por `lote_padre_id`.
