"""Datos iniciales de toda instalacion: permisos, roles, catalogos y parametros. Idempotente."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permisos import PERMISOS, ROLES_INICIALES
from app.modelos import (Configuracion, Empresa, MotivoMovimiento, Permiso, PlantillaEtiqueta, ReglaAlerta, Rol,
                         TipoBodega, TipoMovimiento, UnidadMedida)

UNIDADES = [
    ("kg", "Kilogramo", "MASA", 3), ("g", "Gramo", "MASA", 1), ("L", "Litro", "VOLUMEN", 3),
    ("ml", "Mililitro", "VOLUMEN", 0), ("un", "Unidad", "CONTEO", 0), ("m", "Metro", "LONGITUD", 2),
    ("caja", "Caja", "ENVASE", 0), ("bidon", "Bidon", "ENVASE", 0), ("saco", "Saco", "ENVASE", 0),
    ("tambor", "Tambor", "ENVASE", 0), ("rollo", "Rollo", "ENVASE", 0), ("pallet", "Pallet", "ENVASE", 0),
]
TIPOS_MOVIMIENTO = [
    ("INGRESO", "Ingreso", 1), ("SALIDA", "Salida", -1), ("CONSUMO", "Consumo", -1),
    ("TRASLADO_SALIDA", "Traslado (salida)", -1), ("TRASLADO_ENTRADA", "Traslado (entrada)", 1),
    ("AJUSTE_POSITIVO", "Ajuste positivo", 1), ("AJUSTE_NEGATIVO", "Ajuste negativo", -1),
    ("DEVOLUCION", "Devolucion", 1), ("PRESTAMO", "Prestamo", -1), ("DEVOLUCION_PRESTAMO", "Devolucion de prestamo", 1),
    ("MERMA", "Merma", -1), ("VENCIMIENTO", "Baja por vencimiento", -1),
    ("ANULACION", "Anulacion (movimiento inverso)", 0),
    ("FRACCIONAMIENTO_SALIDA", "Fraccionamiento (origen)", -1), ("FRACCIONAMIENTO_ENTRADA", "Fraccionamiento (destino)", 1),
]
# (clase, codigo, nombre, tipo_movimiento, requiere_proceso, requiere_documento)
MOTIVOS = [
    ("INGRESO", "COMPRA", "Compra", "INGRESO", False, True),
    ("INGRESO", "TRASLADO", "Traslado recibido", "INGRESO", False, False),
    ("INGRESO", "ACTUALIZACION_STOCK", "Actualizacion de stock", "INGRESO", False, False),
    ("INGRESO", "PRESTAMO", "Prestamo recibido", "INGRESO", False, False),
    ("INGRESO", "DEVOLUCION", "Devolucion a bodega", "DEVOLUCION", False, False),
    ("SALIDA", "PROCESO", "Consumo en proceso", "CONSUMO", True, False),
    ("SALIDA", "DESPACHO", "Despacho", "SALIDA", False, True),
    ("SALIDA", "GUIA_INTERNA", "Guia interna", "SALIDA", False, True),
    ("SALIDA", "CONSUMO_INTERNO", "Consumo interno", "CONSUMO", False, False),
    ("SALIDA", "ASEO_LINEA", "Aseo / lavado de linea", "CONSUMO", False, False),
    ("SALIDA", "MERMA", "Merma", "MERMA", False, False),
    ("SALIDA", "VENCIMIENTO", "Baja por vencimiento", "VENCIMIENTO", False, False),
    ("SALIDA", "PRESTAMO", "Prestamo", "PRESTAMO", False, False),
]
# tipo, nombre, severidad, parametros
REGLAS_ALERTA = [
    ("STOCK_BAJO", "Stock bajo el minimo", "MEDIA", {}),
    ("STOCK_CRITICO", "Stock bajo el nivel critico", "ALTA", {}),
    ("STOCK_AGOTADO", "Producto sin stock", "ALTA", {}),
    ("PRODUCTO_VENCIDO", "Lote vencido con stock", "CRITICA", {}),
    ("PROXIMO_A_VENCER", "Lote proximo a vencer", "MEDIA", {"dias": 30}),
    ("STOCK_ANTIGUO", "Existencia antigua", "BAJA", {"dias": 60}),
    ("CONSUMO_FUERA_FIFO", "Consumo fuera del orden recomendado", "MEDIA", {}),
    ("LOTE_BLOQUEADO", "Lote bloqueado con stock", "MEDIA", {}),
    ("LOTE_CUARENTENA", "Lote en cuarentena con stock", "MEDIA", {}),
    ("PROCESO_SIN_SINCRONIZAR", "Proceso abierto sin sincronizar", "BAJA", {"horas": 24}),
    ("PROCESO_CERRADO_SIN_SINCRONIZACION", "Proceso cerrado sin sincronizacion", "ALTA", {}),
    ("PRESTAMO_VENCIDO", "Prestamo no devuelto en plazo", "MEDIA", {}),
    ("RESERVA_VENCIDA", "Reserva vencida", "BAJA", {}),
    ("DIFERENCIA_INVENTARIO", "Diferencia en inventario fisico", "ALTA", {"porcentaje": 0}),
    ("ERROR_SINCRONIZACION", "Error al sincronizar con produccion", "ALTA", {}),
]
# clave, valor, descripcion
PARAMETROS = [
    ("fifo.ambito", "BODEGA", "Ambito de comparacion FIFO: BODEGA o EMPRESA"),
    ("fifo.tolerancia_dias", 0, "Diferencia de dias de ingreso que no se considera desviacion"),
    ("reservas.permitir_exceder", False, "Permite reservar sobre el disponible (ademas requiere permiso especial)"),
    ("reservas.bloquean_consumo", True, "Impide consumir stock reservado por otro proceso"),
    ("costeo.base_kilos", "kilos_procesados", "Campo del proceso usado como base del costo por kilo"),
    ("antiguedad.rangos", [30, 60, 90, 180], "Limites en dias de los rangos de antiguedad"),
    ("existencias.prefijo", "INV", "Prefijo del codigo publico de existencias"),
    ("etiquetas.url_base", "", "URL base impresa en el QR (vacio = URL publica del sistema)"),
]
ETIQUETA = ["qr", "codigo_publico", "producto_codigo", "producto_nombre", "lote", "fecha_ingreso", "fecha_vencimiento",
            "cantidad", "unidad", "bodega", "ubicacion"]


def sembrar_base(db: Session) -> None:
    existentes = {p.codigo: p for p in db.scalars(select(Permiso))}
    for codigo, desc, especial in PERMISOS:
        if codigo not in existentes:
            modulo, accion = codigo.split(":")
            existentes[codigo] = Permiso(codigo=codigo, modulo=modulo, accion=accion, descripcion=desc, especial=especial)
            db.add(existentes[codigo])
    for cod, nom, dim, decs in UNIDADES:
        if not db.scalar(select(UnidadMedida).where(UnidadMedida.codigo == cod)):
            db.add(UnidadMedida(codigo=cod, nombre=nom, dimension=dim, decimales=decs))
    tipos = {t.codigo: t for t in db.scalars(select(TipoMovimiento))}
    for cod, nom, signo in TIPOS_MOVIMIENTO:
        if cod not in tipos:
            tipos[cod] = TipoMovimiento(codigo=cod, nombre=nom, signo=signo, es_sistema=True)
            db.add(tipos[cod])
    db.flush()
    for clase, cod, nom, tipo, rp, rd in MOTIVOS:
        if not db.scalar(select(MotivoMovimiento).where(MotivoMovimiento.clase == clase, MotivoMovimiento.codigo == cod)):
            db.add(MotivoMovimiento(clase=clase, codigo=cod, nombre=nom, tipo_movimiento_id=tipos[tipo].id,
                                    requiere_proceso=rp, requiere_documento=rd))
    for cod, nom in [("FITOSANITARIOS", "Fitosanitarios"), ("MANTENCION", "Mantencion"), ("MECANICA", "Mecanica"),
                     ("MATERIALES", "Materiales de produccion"), ("GENERAL", "General")]:
        if not db.scalar(select(TipoBodega).where(TipoBodega.codigo == cod)):
            db.add(TipoBodega(codigo=cod, nombre=nom))
    if not db.scalar(select(PlantillaEtiqueta)):
        db.add(PlantillaEtiqueta(nombre="Estandar 100x60", ancho_mm=100, alto_mm=60, campos=ETIQUETA, predeterminada=True))
    for clave, valor, desc in PARAMETROS:
        if not db.scalar(select(Configuracion).where(Configuracion.empresa_id.is_(None), Configuracion.clave == clave)):
            db.add(Configuracion(empresa_id=None, clave=clave, valor=valor, descripcion=desc))
    db.flush()


def sembrar_empresa(db: Session, empresa: Empresa) -> dict[str, Rol]:
    """Roles y reglas de alerta propios de la empresa."""
    permisos = {p.codigo: p for p in db.scalars(select(Permiso))}
    roles = {}
    for codigo, (nombre, desc, lista) in ROLES_INICIALES.items():
        rol = db.scalar(select(Rol).where(Rol.empresa_id == empresa.id, Rol.codigo == codigo))
        if not rol:
            rol = Rol(empresa_id=empresa.id, codigo=codigo, nombre=nombre, descripcion=desc, es_sistema=True)
            db.add(rol)
        if codigo == "ADMINISTRADOR" or not rol.permisos:
            rol.permisos = [permisos[c] for c in lista]
        roles[codigo] = rol
    for tipo, nombre, sev, params in REGLAS_ALERTA:
        if not db.scalar(select(ReglaAlerta).where(ReglaAlerta.empresa_id == empresa.id, ReglaAlerta.tipo == tipo)):
            db.add(ReglaAlerta(empresa_id=empresa.id, tipo=tipo, nombre=nombre, severidad=sev, parametros=params))
    db.flush()
    return roles
