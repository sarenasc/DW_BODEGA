# Centro de alertas

Las advertencias no son solo tarjetas del dashboard: cada alerta es un registro persistente (`alertas`) con estado, severidad,
entidad relacionada y responsable de su cierre.

## Tipos y reglas

Cada tipo tiene una **regla** por empresa (`reglas_alertas`): activa o no, severidad y parámetros. Se editan en *Alertas → Reglas*.

| Tipo | Se genera cuando | Parámetro | Severidad inicial |
|---|---|---|---|
| STOCK_BAJO | Stock ≤ `stock_minimo` del producto | — | Media |
| STOCK_CRITICO | Stock ≤ `stock_critico` del producto | — | Alta |
| STOCK_AGOTADO | Producto con mínimo definido y sin stock | — | Alta |
| PRODUCTO_VENCIDO | Lote con stock y vencimiento pasado (además pasa a VENCIDO) | — | Crítica |
| PROXIMO_A_VENCER | Lote con stock que vence dentro de *N* días | `dias` = 30 | Media |
| STOCK_ANTIGUO | Existencia con stock ingresada hace más de *N* días | `dias` = 60 | Baja |
| LOTE_BLOQUEADO / LOTE_CUARENTENA | Lote con stock en ese estado | — | Media |
| PROCESO_SIN_SINCRONIZAR | Proceso abierto con origen externo sin sincronizar hace más de *N* horas | `horas` = 24 | Baja |
| PRESTAMO_VENCIDO | Préstamo pendiente con fecha de devolución pasada | — | Media |
| RESERVA_VENCIDA | Reserva activa con fecha límite pasada (se libera) | — | Baja |
| CONSUMO_FUERA_FIFO | Se consumió fuera del orden recomendado | — | Media |
| PROCESO_CERRADO_SIN_SINCRONIZACION | Cierre manual de un proceso con origen externo | — | Alta |
| DIFERENCIA_INVENTARIO | Un conteo físico terminó con diferencias | — | Alta |
| ERROR_SINCRONIZACION | Falló la lectura de la base productiva | — | Alta |
| OTRA | Alerta manual | — | A elección |

Los seis últimos son **eventos**: se crean en el momento en que ocurren. Los demás son **de estado**: los evalúa una tarea periódica
(cada 30 minutos, o al pulsar *Evaluar reglas ahora*).

## Comportamiento

- **Sin duplicados**: mientras una alerta siga abierta no se crea otra igual para la misma entidad.
- **Resolución automática**: una alerta de estado se cierra sola cuando la condición deja de cumplirse (llegó stock, se devolvió el préstamo, se sincronizó).
  Las de sincronización y de conteo se resuelven al sincronizar o autorizar.
- Desactivar una regla detiene su generación y cierra sus alertas de estado abiertas.

## Datos de cada alerta

Tipo, severidad, título, descripción, fecha de creación, fecha de vencimiento (si aplica), entidad e identificador relacionados,
usuario relacionado, bodega, estado, resuelta por, fecha de resolución y observación.

**Estados:** NUEVA → LEÍDA → EN GESTIÓN → RESUELTA / DESCARTADA.
**Severidad:** INFORMATIVA, BAJA, MEDIA, ALTA, CRÍTICA.

Marcar como leída solo requiere `alertas:ver`; gestionar y cerrar exige `alertas:gestionar` y, al cerrar, una observación.
Las alertas de una bodega solo las ve quien tiene acceso a ella.

## En la interfaz

- **Campana** de la barra superior y contador en el menú (rojo si hay críticas).
- **Dashboard**: alertas abiertas, nuevas y críticas, y los contadores de stock bajo, próximos a vencer, vencidos, fuera de FIFO,
  reservas vencidas y procesos sin sincronizar, con *Ver todas las alertas*.
- **Centro de alertas**: filtros por tipo, severidad, estado y bodega; botón **Ver …** que navega a la entidad (producto, lote, existencia, proceso, préstamo, reserva, conteo).

## Notificaciones externas

La arquitectura las admite; **ningún canal está implementado todavía**. Cada regla tiene una lista de `canales` y el servicio un registro de canales:

```python
from app.servicios.alertas import registrar_canal

def enviar_correo(alerta):   # recibe el registro de la alerta
    ...

registrar_canal("EMAIL", enviar_correo)
```

Al crear una alerta se invoca cada canal registrado que figure en su regla. Un fallo del canal no revierte la operación de negocio.
Con esto pueden agregarse correo, Microsoft Teams, Telegram o WhatsApp sin tocar el resto del sistema.

Tablas: `alertas`, `reglas_alertas`. Servicio: `app/servicios/alertas.py`. Pruebas: `tests/test_fase6_analitica.py`.
