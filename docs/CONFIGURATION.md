# Configuración

Hay tres niveles: variables de entorno (arranque), parámetros generales (en la aplicación) y maestros.

## Variables de entorno

Prefijo `WMS_`. Plantilla: [.env.example](../.env.example).

| Variable | Predeterminado | Uso |
|---|---|---|
| `WMS_CLAVE_SECRETA` | — (obligatoria fuera del Demo) | Firma los tokens y cifra credenciales. Si cambia, hay que reinstalar la conexión y reingresar las contraseñas de integración |
| `WMS_MODO_DEMO` | `0` | `1`: SQLite con datos ficticios, sin asistente |
| `WMS_URL_BD` | vacío | URL SQLAlchemy explícita; reemplaza al archivo de instancia |
| `WMS_DIR_INSTANCIA` | `instance/` | Configuración cifrada, base Demo y archivos adjuntos |
| `WMS_DIR_ARCHIVOS` | `<instancia>/archivos` | Almacenamiento de adjuntos |
| `WMS_DIR_FRONTEND` | `frontend/out` | Sitio estático a servir (si existe) |
| `WMS_URL_PUBLICA` | `http://localhost:8000` | Se imprime dentro de los QR |
| `WMS_COOKIE_SEGURA` | `0` | `1` bajo HTTPS |
| `WMS_MINUTOS_TOKEN_ACCESO` | `30` | Vigencia del token de acceso |
| `WMS_DIAS_SESION` | `14` | Vigencia de la sesión renovable |
| `WMS_INTENTOS_LOGIN` / `WMS_VENTANA_LOGIN_SEGUNDOS` | `8` / `300` | Límite de intentos de acceso |
| `WMS_ZONA_HORARIA` | `America/Santiago` | Zona en que se cuentan los días |
| `WMS_PLANIFICADOR` | `1` | Tareas internas (alertas cada 30 min, sincronización cada 5 min) |
| `WMS_ORIGENES_CORS` | vacío | Solo si el frontend vive en otro origen |

## Parámetros generales

*Configuración → Empresa y parámetros*. El valor de la empresa prevalece sobre el global.

| Clave | Predeterminado | Efecto |
|---|---|---|
| `fifo.ambito` | `BODEGA` | Dónde se busca stock más antiguo: la misma bodega o toda la empresa |
| `fifo.tolerancia_dias` | `0` | Diferencia de días de ingreso que no se considera desviación (0 = mismo día) |
| `reservas.permitir_exceder` | `false` | Permite reservar sobre el disponible (además exige el permiso `reservas:exceder`) |
| `reservas.bloquean_consumo` | `true` | Impide consumir stock reservado por otro proceso |
| `costeo.base_kilos` | `kilos_procesados` | Base del costo por kilo. También `kilos_recepcionados`, `kilos_producidos`, `kilos_despachados` o `extra.<clave>` |
| `antiguedad.rangos` | `[30, 60, 90, 180]` | Límites de los rangos de antigüedad |
| `existencias.prefijo` | `INV` | Prefijo del código público |
| `etiquetas.url_base` | vacío | URL de los QR (vacío = `WMS_URL_PUBLICA`) |

## Configuración heredable

Familia → Subfamilia → Producto. Un valor vacío **hereda**; el producto puede sobreescribir. La ficha del producto muestra el valor efectivo y de dónde proviene.

| Parámetro | Valores |
|---|---|
| Utiliza lote / vencimiento / serie, requiere QR, requiere ubicación, permite sublotes | Sí · No · Heredar |
| Plantilla de lote | Cualquier plantilla activa |
| Granularidad de inventario | `POR_ENVASE` · `POR_LOTE` · `CONSOLIDADA` · `UNIDAD_LOGISTICA` |
| Estrategia de salida | `FIFO` · `FEFO` · `FEFO_FIFO` · `SIN_RECOMENDACION` |
| Política ante desviación | `ADVERTIR` · `BLOQUEAR` · `JUSTIFICAR` · `PERMISO` |
| Vida útil (meses), prioridad del vencimiento (`MANUAL` / `CALCULADA`), vida útil tras apertura (días) | Numéricos |

Si ningún nivel define un valor rige el global: usa lote, sin vencimiento, requiere QR, `POR_ENVASE`, `FIFO`, `ADVERTIR`.

## Dónde se configura cada cosa

| Elemento | Menú |
|---|---|
| Empresa, parámetros, temporadas, tipos de ingreso y salida, tipos de movimiento, tipos de bodega, etiquetas | Configuración |
| Familias, subfamilias, productos, unidades, conversiones, proveedores | Maestros |
| Bodegas, ubicaciones, plano | Maestros → Bodegas |
| Plantillas de lote | Maestros → Creador de lotes |
| Conexiones, fuentes y mapeo | Administración → Integraciones |
| Roles, permisos, usuarios | Administración → Usuarios y roles |
| Reglas de alerta | Alertas → Reglas |

Nada de lo anterior está escrito en el código: familias, unidades, tipos de movimiento, motivos, plantillas y reglas son datos.
