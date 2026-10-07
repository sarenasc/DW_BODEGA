# Usuarios, roles y permisos

Control de acceso por rol (RBAC). Un **permiso** es `modulo:accion`; un **rol** agrupa permisos; un **usuario** tiene uno o más roles.
Nada es rígido: los cuatro roles iniciales son plantillas editables y pueden crearse roles nuevos (*Administración → Usuarios y roles*).

## Roles iniciales

| Rol | Descripción | Ve costos |
|---|---|---|
| Administrador | Acceso completo | Sí |
| Jefe de área | Gestión operativa y autorizaciones; sin usuarios, configuración general ni integraciones | Sí |
| Usuario / Digitador | Operación diaria: ingresos, consumos, traslados, reservas, conteos, préstamos | **No** |
| Lector | Solo lectura | **No** |

## Alcance

Además del rol, cada usuario puede limitarse a:

- **Bodegas** determinadas (o todas).
- **Familias de productos** determinadas (o todas). Ejemplo: usuario agrícola → Fitosanitarios; usuario de mantención → Mantención.

El alcance se aplica en el backend: filtra listados y rechaza operaciones sobre bodegas o familias ajenas (403), incluido el escaneo de un QR.

## Catálogo de permisos

| Módulo | Acciones |
|---|---|
| dashboard | ver |
| catalogo | ver, administrar |
| bodegas | ver, administrar |
| lotes | ver, administrar, bloquear, **consumir_bloqueado ★**, **consumir_vencido ★** |
| inventario | ver, crear (ingresos), editar (borradores, ubicar, etiquetas, fraccionar), ajustar |
| movimientos | ver, crear (salidas y consumos), anular |
| traslados | crear |
| fifo | **omitir ★** |
| reservas | ver, crear, **exceder ★** |
| procesos | ver, abrir, actualizar, cerrar, **cerrar_sin_sincronizar ★**, **reabrir ★** |
| costos | ver |
| conteos | ver, contar, **autorizar ★** |
| prestamos | ver, administrar |
| alertas | ver, gestionar, configurar |
| reportes | ver, exportar |
| trazabilidad | ver |
| integraciones | administrar |
| usuarios | administrar |
| configuracion | editar |
| auditoria | ver |
| adjuntos | administrar |

★ **Permiso especial**: autoriza una excepción a una regla.

| Permiso especial | Excepción que autoriza |
|---|---|
| `fifo:omitir` | Consumir fuera del orden recomendado cuando la política es "solo con permiso" |
| `lotes:consumir_bloqueado` | Consumir un lote BLOQUEADO o en CUARENTENA |
| `lotes:consumir_vencido` | Consumir un lote vencido o un envase con vida útil tras apertura vencida |
| `reservas:exceder` | Reservar sobre el disponible (además exige el parámetro `reservas.permitir_exceder`) |
| `procesos:cerrar_sin_sincronizar` | Cerrar un proceso sin actualizar desde producción |
| `procesos:reabrir` | Reabrir un proceso cerrado |
| `conteos:autorizar` | Generar los ajustes de un inventario físico |

## Permiso de costos

`costos:ver` es independiente de todo lo demás. Sin él, el usuario opera normalmente pero no ve: costo unitario, valorización,
costo del proceso, costo por kilo, valor del inventario ni reportes de costo. Los valores se eliminan en el backend, no solo se ocultan en pantalla.

## Reglas

- El rol Administrador siempre conserva `usuarios:administrar`.
- Un usuario no puede desactivarse a sí mismo.
- Cambiar la clave o desactivar a un usuario cierra sus sesiones.
- Un cambio de permisos rige desde la siguiente petición.
- Los roles iniciales no se eliminan, pero sus permisos sí se editan.

## Usuarios del Modo Demo

`admin`, `jefe`, `bodega` (digitador) y `lector`, todos con clave `Demo1234`.
