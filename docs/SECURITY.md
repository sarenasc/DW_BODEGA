# Seguridad

## Controles implementados

| Área | Control | Dónde |
|---|---|---|
| Contraseñas | Hash **Argon2id**; mínimo 8 caracteres con letras y números; nunca se registran ni se devuelven | `core/seguridad.py` |
| Sesión | Token de acceso JWT (HS256) de 30 min **solo en memoria** del navegador; sesión renovable en cookie `httpOnly`, `SameSite=Strict`, `Secure` bajo HTTPS, con **rotación** en cada uso | `modulos/auth.py` |
| Rotación | La sesión rotada se acepta 20 s más (dos pestañas renovando a la vez); cerrar sesión o desactivar al usuario la invalida de inmediato | idem |
| Fuerza bruta | Límite de intentos de acceso por IP + usuario (8 en 5 min → 429) | idem |
| CSRF | La API se autentica con cabecera `Authorization`, que un sitio ajeno no puede agregar; la cookie solo sirve para `/api/auth/*` y es `SameSite=Strict` | diseño |
| Autorización | RBAC `modulo:accion` verificado **en el backend** en cada operación; alcance por bodega y por familia aplicado en consultas y escrituras | `core/dependencias.py` |
| Costos | Permiso independiente `costos:ver`; sin él los campos llegan en `null` y los reportes de costo responden 403 | `core/util.ocultar_costos` |
| Inyección SQL | Solo ORM y parámetros enlazados; no se concatena entrada del usuario en SQL | todo el backend |
| Consulta de integración | Se admite **una** sentencia `SELECT` (o el nombre de una vista); se rechazan `;`, DML, DDL y procedimientos; el identificador viaja como parámetro; PostgreSQL abre la sesión en solo lectura | `servicios/integracion.py` |
| Secretos | `WMS_CLAVE_SECRETA` por variable de entorno; conexión de la instancia y contraseñas de integración cifradas (Fernet); jamás se devuelven por la API ni se escriben en auditoría | `core/db.py`, `core/auditoria.py` |
| QR | Token aleatorio de 128 bits; el QR no contiene datos de negocio; resolverlo exige sesión y alcance sobre la bodega | `modulos/inventario.py` |
| Archivos | Lista blanca de extensiones, máximo 15 MB, nombre en disco generado por el servidor, verificación de ruta al descargar, huella SHA-256 | `modulos/adjuntos.py` |
| Validación | Pydantic en toda entrada (campos desconocidos rechazados en los maestros); el frontend valida además para la experiencia de uso | — |
| Cabeceras | `X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, `Permissions-Policy: camera=(self)`, `Cache-Control: no-store` en `/api` | `main.py`, `nginx.conf` |
| Auditoría | Usuario, fecha, IP, dispositivo, entidad, acción, valor anterior y nuevo, motivo | `core/auditoria.py` |
| Integridad | Claves foráneas, únicos, `CHECK`, transacciones; movimientos inmutables | modelos |
| Exportación | Las celdas que comienzan con `=`, `+`, `-`, `@` se neutralizan en CSV y Excel | `servicios/reportes.py` |
| Asistente | Los puntos de instalación responden 409 una vez instalado el sistema | `modulos/instalacion.py` |

## Revisión realizada

Recorrido manual de autenticación, autorización, entrada de datos, archivos e integración, más las pruebas automáticas que lo respaldan
(acceso sin token, token falso, permisos por rol, alcance por bodega y familia, límite de intentos, rotación, credenciales no expuestas,
consultas no permitidas, archivos no permitidos, exportación sin permiso).

## Limitaciones conocidas

- **El límite de intentos vive en memoria del proceso.** Con varios procesos o tras un reinicio se reinicia. Para instalaciones expuestas a Internet agregue limitación en el proxy.
- **Modo Demo:** claves conocidas y clave maestra fija. No exponerlo fuera de una red de confianza ni usarlo con datos reales.
- **Sin segundo factor ni inicio de sesión corporativo** (Microsoft 365). No fue requerido; el diseño de sesiones lo admite.
- **Política de contenido (CSP)** no configurada: el visor 3D y los estilos requieren ajustes específicos. Recomendada antes de exponer a Internet.
- **El validador de consultas es una segunda barrera, no la principal.** La garantía real es que el usuario de la base productiva sea de solo lectura.
- **El asistente recibe la contraseña de la base por la red:** complete la instalación por HTTPS o desde el propio servidor.
- **Sin antivirus sobre adjuntos**: solo se valida tipo y tamaño.
- No se realizó una prueba de penetración externa.

## Recomendaciones de operación

- HTTPS siempre; `WMS_COOKIE_SEGURA=1`.
- Clave maestra única por instalación, respaldada fuera del servidor.
- Usuario de base de datos propio del sistema, sin privilegios de administrador del motor tras la instalación.
- Asigne `costos:ver` y los permisos especiales (★) solo a quien los necesite; revise *Auditoría* periódicamente.
- Mantenga actualizadas las dependencias (`uv lock --upgrade`, `npm audit`).
