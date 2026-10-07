"""Catalogo de permisos (modulo:accion) y roles iniciales. Los roles son plantillas editables."""

# (codigo, descripcion, especial)
PERMISOS: list[tuple[str, str, bool]] = [
    ("dashboard:ver", "Ver dashboard", False),
    ("catalogo:ver", "Ver familias, subfamilias, productos, unidades y proveedores", False),
    ("catalogo:administrar", "Crear y editar maestros de productos", False),
    ("bodegas:ver", "Ver bodegas, ubicaciones y plano", False),
    ("bodegas:administrar", "Crear y editar bodegas, ubicaciones y plano", False),
    ("lotes:ver", "Ver lotes y plantillas", False),
    ("lotes:administrar", "Administrar plantillas de lote", False),
    ("lotes:bloquear", "Cambiar estado de lotes (bloqueo, cuarentena)", False),
    ("lotes:consumir_bloqueado", "Consumir lotes bloqueados o en cuarentena", True),
    ("lotes:consumir_vencido", "Consumir lotes vencidos", True),
    ("inventario:ver", "Ver stock y existencias", False),
    ("inventario:crear", "Registrar ingresos y documentos", False),
    ("inventario:editar", "Editar documentos en borrador, ubicar existencias, imprimir etiquetas", False),
    ("inventario:ajustar", "Registrar ajustes de inventario", False),
    ("movimientos:ver", "Ver movimientos", False),
    ("movimientos:crear", "Registrar salidas y consumos", False),
    ("movimientos:anular", "Anular movimientos (genera movimiento inverso)", False),
    ("traslados:crear", "Trasladar entre bodegas y ubicaciones", False),
    ("fifo:omitir", "Consumir fuera del orden recomendado cuando la politica exige permiso", True),
    ("reservas:ver", "Ver reservas de stock", False),
    ("reservas:crear", "Crear y liberar reservas", False),
    ("reservas:exceder", "Reservar sobre el stock disponible", True),
    ("procesos:ver", "Ver procesos", False),
    ("procesos:abrir", "Crear, importar y abrir procesos", False),
    ("procesos:actualizar", "Actualizar procesos desde produccion", False),
    ("procesos:cerrar", "Cerrar procesos", False),
    ("procesos:cerrar_sin_sincronizar", "Cerrar procesos sin actualizar desde produccion", True),
    ("procesos:reabrir", "Reabrir procesos cerrados", True),
    ("costos:ver", "Ver costos, valorizacion, costo de proceso y costo por kilo", False),
    ("conteos:ver", "Ver inventarios fisicos", False),
    ("conteos:contar", "Registrar conteos", False),
    ("conteos:autorizar", "Autorizar ajustes de conteo", True),
    ("prestamos:ver", "Ver prestamos", False),
    ("prestamos:administrar", "Registrar prestamos y devoluciones", False),
    ("alertas:ver", "Ver centro de alertas", False),
    ("alertas:gestionar", "Gestionar y resolver alertas", False),
    ("alertas:configurar", "Configurar reglas de alertas", False),
    ("reportes:ver", "Ver reportes", False),
    ("reportes:exportar", "Exportar reportes", False),
    ("trazabilidad:ver", "Ver trazabilidad", False),
    ("integraciones:administrar", "Administrar conexiones, fuentes y mapeos", False),
    ("usuarios:administrar", "Administrar usuarios, roles y permisos", False),
    ("configuracion:editar", "Editar configuracion general", False),
    ("auditoria:ver", "Ver registro de auditoria", False),
    ("adjuntos:administrar", "Subir y eliminar archivos adjuntos", False),
]

_TODOS = [p[0] for p in PERMISOS]
_VER = [p for p in _TODOS if p.endswith(":ver")]

ROLES_INICIALES = {
    "ADMINISTRADOR": ("Administrador", "Acceso completo.", _TODOS),
    "JEFE_AREA": ("Jefe de area", "Gestion operativa y autorizaciones.", [
        p for p in _TODOS if p not in ("usuarios:administrar", "configuracion:editar", "integraciones:administrar",
                                      "reservas:exceder")]),
    "DIGITADOR": ("Usuario / Digitador", "Operacion diaria sin ver costos.", [
        "dashboard:ver", "catalogo:ver", "bodegas:ver", "lotes:ver", "inventario:ver", "inventario:crear",
        "inventario:editar", "movimientos:ver", "movimientos:crear", "traslados:crear", "reservas:ver",
        "reservas:crear", "procesos:ver", "conteos:ver", "conteos:contar", "prestamos:ver",
        "prestamos:administrar", "alertas:ver", "trazabilidad:ver", "reportes:ver"]),
    "LECTOR": ("Lector", "Solo lectura, sin costos.", [p for p in _VER if p != "costos:ver"]),
}
