"""Datos ficticios del Modo Demo: una empresa fruticola con dos bodegas, stock, procesos, consumos y alertas.

Todo se crea llamando a los mismos servicios que usa la aplicacion, de modo que el Demo respeta las reglas reales
(lotes generados por plantilla, movimientos, costos por existencia, FIFO, reservas).
"""
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import siguiente_numero
from app.core.config import ajustes
from app.core.dependencias import Contexto
from app.core.seguridad import hash_clave
from app.core.util import ahora, hoy
from app.modelos import (Bodega, ConexionIntegracion, ConversionUnidad, DetalleDocumentoInventario, DocumentoInventario,
                         ElementoPlano, Empresa, Existencia, Familia, FuenteIntegracion, MapeoIntegracion, MotivoMovimiento,
                         PlantillaLote, Proceso, Producto, Proveedor, SegmentoPlantillaLote, Subfamilia, Temporada, TipoBodega,
                         Ubicacion, UnidadMedida, Usuario, VersionPlantillaLote)
from app.semilla.base import sembrar_base, sembrar_empresa

CLAVE_DEMO = "Demo1234"
USUARIOS_DEMO = [("admin", "Andrea Administradora", "ADMINISTRADOR"), ("jefe", "Jorge Jefe de Bodega", "JEFE_AREA"),
                 ("bodega", "Beatriz Bodeguera", "DIGITADOR"), ("lector", "Luis Lector", "LECTOR")]
ARCHIVO_PRODUCCION = "produccion_demo.db"

# (id, codigo, dias atras, productor, cod productor, especie, variedad, lote, kilos recep, kilos proc, bins, exportadora, turno, linea, estado)
CORRIDAS = [
    (1001, "PK-1001", 34, "Agricola El Roble", "PR-077", "Cereza", "Santina", "L-26-0412", 31200, 29850, 78, "Exportadora Andes", "A", "Linea 1", "TERMINADA"),
    (1002, "PK-1002", 29, "Fundo Los Aromos", "PR-012", "Cereza", "Lapins", "L-26-0418", 44800, 42100, 112, "Exportadora Andes", "B", "Linea 1", "TERMINADA"),
    (1003, "PK-1003", 23, "Agricola El Roble", "PR-077", "Cereza", "Regina", "L-26-0431", 26500, 25040, 66, "Frutas del Sur", "A", "Linea 2", "TERMINADA"),
    (1004, "PK-1004", 17, "Huertos del Maule", "PR-105", "Arandano", "Duke", "L-26-0455", 12400, 11890, 31, "Frutas del Sur", "A", "Linea 3", "TERMINADA"),
    (1005, "PK-1005", 11, "Huertos del Maule", "PR-105", "Arandano", "Legacy", "L-26-0467", 15800, 15120, 40, "Exportadora Andes", "B", "Linea 3", "TERMINADA"),
    (1006, "PK-1006", 6, "Fundo Los Aromos", "PR-012", "Ciruela", "Angeleno", "L-26-0480", 38600, 36900, 96, "Exportadora Andes", "A", "Linea 1", "TERMINADA"),
    (1007, "PK-1007", 1, "Agricola Santa Elena", "PR-140", "Ciruela", "Larry Ann", "L-26-0492", 9800, 5000, 25, "Frutas del Sur", "A", "Linea 2", "EN PROCESO"),
    (1008, "PK-1008", 0, "Agricola El Roble", "PR-077", "Cereza", "Sweetheart", "L-26-0498", 12200, 5000, 30, "Exportadora Andes", "A", "Linea 1", "EN PROCESO"),
    (1009, "PK-1009", 0, "Huertos del Maule", "PR-105", "Arandano", "Brigitta", "L-26-0501", 6400, 2100, 16, "Frutas del Sur", "B", "Linea 3", "EN PROCESO"),
    (1010, "PK-1010", 0, "Fundo Los Aromos", "PR-012", "Kiwi", "Hayward", "L-26-0503", 18900, 0, 47, "Exportadora Andes", "B", "Linea 2", "PROGRAMADA"),
]


def crear_base_productiva(reiniciar: bool = True) -> None:
    """Base SQLite que simula el sistema de produccion: permite demostrar importacion y sincronizacion sin infraestructura."""
    ruta = ajustes().dir_instancia / ARCHIVO_PRODUCCION
    if ruta.exists() and not reiniciar:
        return
    ruta.unlink(missing_ok=True)
    con = sqlite3.connect(ruta)
    con.executescript("""
        CREATE TABLE packing_corridas (id_corrida INTEGER PRIMARY KEY, n_proceso TEXT, fec_proceso TEXT, hora_ini TEXT, hora_fin TEXT,
            nom_productor TEXT, cod_productor TEXT, des_especie TEXT, des_variedad TEXT, n_lote TEXT, kilos_recepcion REAL,
            peso_neto REAL, kilos_embalados REAL, cant_bins INTEGER, cant_cajas INTEGER, des_exportadora TEXT, turno TEXT,
            linea TEXT, n_guia TEXT, predio TEXT, estado_corrida TEXT);
        CREATE VIEW vw_wms_procesos AS SELECT * FROM packing_corridas WHERE estado_corrida <> 'ANULADA';
    """)
    for (id_, cod, dias, prod, cprod, esp, var, lote, krec, kproc, bins, expo, turno, linea, estado) in CORRIDAS:
        fecha = (hoy() - timedelta(days=dias)).isoformat()
        con.execute("INSERT INTO packing_corridas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (id_, cod, fecha, "08:00", "17:30" if estado == "TERMINADA" else None, prod, cprod, esp, var, lote, krec, kproc,
                     round(kproc * 0.92), bins, int(kproc / 5), expo, turno, linea, f"G-{id_ + 4000}", f"Predio {cprod[-3:]}", estado))
    con.commit()
    con.close()


def avanzar_produccion() -> None:
    """Simula que produccion siguio trabajando: al pulsar 'Actualizar proceso' aparecen los kilos nuevos."""
    con = sqlite3.connect(ajustes().dir_instancia / ARCHIVO_PRODUCCION)
    con.execute("UPDATE packing_corridas SET peso_neto = 15000, kilos_embalados = 13800, cant_cajas = 3000 WHERE id_corrida = 1008")
    con.execute("UPDATE packing_corridas SET peso_neto = 9350, kilos_embalados = 8600, cant_cajas = 1870, estado_corrida = 'TERMINADA', "
                "hora_fin = '18:10' WHERE id_corrida = 1007")
    con.commit()
    con.close()


def sembrar_demo(db: Session, emp: Empresa) -> None:
    from app.modulos.bodegas import RackEntrada, crear_ubicacion, generar_rack
    from app.modulos.procesos import CierreEntrada
    from app.modulos.procesos import cerrar as cerrar_proceso
    from app.modulos.reservas import ReservaEntrada, crear_reserva
    from app.servicios import inventario as inv
    from app.servicios.alertas import evaluar_reglas
    from app.servicios.integracion import importar_proceso
    from app.servicios.lotes import cambiar_estado_lote

    admin = db.scalar(select(Usuario).where(Usuario.empresa_id == emp.id).order_by(Usuario.id))
    usuarios = {u.usuario: u for u in db.scalars(select(Usuario).where(Usuario.empresa_id == emp.id))}
    ctx = Contexto(admin, admin.permisos, "127.0.0.1", "Carga de datos demo")
    ctx_bodega = Contexto(usuarios.get("bodega", admin), admin.permisos, "127.0.0.1", "Carga de datos demo")
    u = {x.codigo: x for x in db.scalars(select(UnidadMedida))}
    motivos = {(m.clase, m.codigo): m for m in db.scalars(select(MotivoMovimiento))}
    tipos_bodega = {t.codigo: t.id for t in db.scalars(select(TipoBodega))}
    ahora_ = ahora()

    if not db.scalar(select(Temporada).where(Temporada.empresa_id == emp.id, Temporada.actual.is_(True))):
        a1 = hoy().year if hoy().month >= 7 else hoy().year - 1
        db.add_all([Temporada(empresa_id=emp.id, codigo=f"{a1}-{a1 + 1}", nombre=f"Temporada {a1}-{a1 + 1}",
                              fecha_inicio=date(a1, 7, 1), fecha_termino=date(a1 + 1, 6, 30), actual=True),
                    Temporada(empresa_id=emp.id, codigo=f"{a1 - 1}-{a1}", nombre=f"Temporada {a1 - 1}-{a1}",
                              fecha_inicio=date(a1 - 1, 7, 1), fecha_termino=date(a1, 6, 30))])
    for origen, destino, factor in (("kg", "g", 1000), ("L", "ml", 1000)):
        db.add(ConversionUnidad(unidad_origen_id=u[origen].id, unidad_destino_id=u[destino].id, factor=factor))
    proveedores = {}
    for cod, nom, rut in (("AGROQ", "Agroquimica del Valle Ltda.", "76.123.456-7"), ("FITOSUR", "Fitosur Insumos SpA", "77.234.567-8"),
                          ("RODAMAX", "Rodamax Repuestos Industriales", "76.345.678-9")):
        proveedores[cod] = Proveedor(empresa_id=emp.id, codigo=cod, nombre=nom, rut=rut)
        db.add(proveedores[cod])
    db.flush()

    # ---- plantillas de lote
    def plantilla(codigo, nombre, segmentos, alcance, reinicio):
        p = PlantillaLote(empresa_id=emp.id, codigo=codigo, nombre=nombre, modo="AUTOMATICO", activa=True)
        v = VersionPlantillaLote(version=1, estado="VIGENTE", vigente_desde=ahora_ - timedelta(days=200), alcance=alcance, reinicio=reinicio)
        v.segmentos = [SegmentoPlantillaLote(posicion=i, tipo=t, configuracion=c) for i, (t, c) in enumerate(segmentos)]
        p.versiones.append(v)
        db.add(p)
        db.flush()
        return p

    sep = ("SEPARADOR", {"valor": "-"})
    pl_fito = plantilla("LOTE-FITO", "Lote fitosanitario", [("SUBFAMILIA", {}), sep, ("ANIO", {"digitos": 2}), sep,
                                                            ("CORRELATIVO", {"largo": 5})], ["SUBFAMILIA"], "ANUAL")
    pl_rep = plantilla("LOTE-REP", "Lote repuestos e insumos", [("TEXTO", {"valor": "REP"}), sep, ("FECHA", {"formato": "YYMMDD"}), sep,
                                                                ("CORRELATIVO", {"largo": 3})], [], "DIARIO")

    # ---- familias, subfamilias y productos
    fito = Familia(empresa_id=emp.id, codigo="FITO", nombre="Fitosanitarios", descripcion="Productos fitosanitarios y de postcosecha",
                   usa_lote=True, usa_vencimiento=True, requiere_qr=True, requiere_ubicacion=True, granularidad="POR_ENVASE",
                   estrategia_salida="FIFO", politica_fifo="ADVERTIR", plantilla_lote_id=pl_fito.id, vida_util_abierto_dias=60)
    mant = Familia(empresa_id=emp.id, codigo="MANT", nombre="Mantencion", descripcion="Repuestos e insumos de mantencion",
                   usa_lote=False, usa_vencimiento=False, requiere_qr=True, granularidad="CONSOLIDADA",
                   estrategia_salida="SIN_RECOMENDACION")
    db.add_all([fito, mant])
    db.flush()
    sub = {}
    for fam, cod, nom, extra in ((fito, "FUNG", "Fungicidas", {}), (fito, "DESI", "Desinfectantes", {}), (fito, "CERA", "Ceras y recubrimientos", {}),
                                 (fito, "COAD", "Coadyuvantes", {"estrategia_salida": "FEFO_FIFO"}), (mant, "RODA", "Rodamientos", {}),
                                 (mant, "LUBR", "Lubricantes", {"usa_lote": True, "plantilla_lote_id": pl_rep.id}),
                                 (mant, "CORR", "Correas y bandas", {})):
        sub[cod] = Subfamilia(familia_id=fam.id, codigo=cod, nombre=nom, **extra)
        sub[cod].familia = fam
        db.add(sub[cod])
    db.flush()

    prod: dict[str, Producto] = {}

    def producto(codigo, nombre, subfam, base, compra=None, factor=None, costo=None, minimo=None, critico=None, **extra):
        p = Producto(empresa_id=emp.id, codigo=codigo, nombre=nombre, subfamilia_id=sub[subfam].id, unidad_base_id=u[base].id,
                     unidad_compra_id=u[compra].id if compra else None, unidad_consumo_id=u[base].id, costo_referencial=costo,
                     stock_minimo=minimo, stock_critico=critico, **extra)
        p.subfamilia, p.unidad_base = sub[subfam], u[base]
        db.add(p)
        db.flush()
        if compra:
            db.add(ConversionUnidad(producto_id=p.id, unidad_origen_id=u[compra].id, unidad_destino_id=u[base].id, factor=factor))
        prod[codigo] = p
        return p

    producto("FUNG-001", "Fungicida Fludioxonil 230 SC", "FUNG", "L", "bidon", 20, 8500, minimo=60, critico=20, marca="Scholar", proveedor_id=proveedores["AGROQ"].id)
    producto("FUNG-002", "Fungicida Pyrimethanil 400 SC", "FUNG", "L", "bidon", 10, 12400, minimo=30, critico=10, marca="Penbotec", proveedor_id=proveedores["AGROQ"].id)
    producto("FUNG-003", "Fungicida Imazalil 500 EC", "FUNG", "L", "bidon", 5, 21500, minimo=25, critico=10, proveedor_id=proveedores["FITOSUR"].id)
    producto("DESI-001", "Acido peracetico 15%", "DESI", "L", "bidon", 20, 4250, minimo=80, critico=40, proveedor_id=proveedores["FITOSUR"].id)
    producto("DESI-002", "Hipoclorito de sodio 10%", "DESI", "L", "tambor", 200, 620, minimo=300, critico=100, granularidad="CONSOLIDADA",
             proveedor_id=proveedores["FITOSUR"].id)
    producto("DESI-003", "Dioxido de cloro 5%", "DESI", "L", "bidon", 20, 5900, minimo=40, critico=20, proveedor_id=proveedores["AGROQ"].id)
    producto("CERA-001", "Cera carnauba para carozos", "CERA", "L", "tambor", 200, 3100, minimo=200, granularidad="CONSOLIDADA",
             proveedor_id=proveedores["AGROQ"].id)
    producto("COAD-001", "Coadyuvante siliconado", "COAD", "L", "bidon", 5, 15800, minimo=10, proveedor_id=proveedores["FITOSUR"].id)
    producto("COAD-002", "Regulador de pH", "COAD", "kg", "saco", 25, 1900, minimo=50, proveedor_id=proveedores["FITOSUR"].id)
    producto("ROD-6204", "Rodamiento 6204 2RS", "RODA", "un", "caja", 10, 3200, minimo=20, critico=8, marca="SKF", proveedor_id=proveedores["RODAMAX"].id)
    producto("ROD-6305", "Rodamiento 6305 ZZ", "RODA", "un", "caja", 10, 5400, minimo=10, critico=4, marca="FAG", proveedor_id=proveedores["RODAMAX"].id)
    producto("LUB-001", "Grasa grado alimenticio H1", "LUBR", "kg", "caja", 12, 9800, minimo=12, proveedor_id=proveedores["RODAMAX"].id)
    producto("LUB-002", "Aceite hidraulico ISO 46", "LUBR", "L", "bidon", 20, 3600, minimo=40, proveedor_id=proveedores["RODAMAX"].id)
    producto("COR-A45", "Correa en V A-45", "CORR", "un", None, None, 4700, minimo=6, critico=2, proveedor_id=proveedores["RODAMAX"].id)

    # ---- bodegas, ubicaciones y plano
    b_fit = Bodega(empresa_id=emp.id, codigo="FIT", nombre="Bodega Fitosanitarios", tipo_bodega_id=tipos_bodega["FITOSANITARIOS"],
                   largo=24, ancho=14, alto=6, niveles=["Rack", "Nivel", "Posicion"], direccion="Planta Packing, sector norte")
    b_man = Bodega(empresa_id=emp.id, codigo="MAN", nombre="Bodega Mantencion", tipo_bodega_id=tipos_bodega["MANTENCION"],
                   largo=16, ancho=10, alto=5, niveles=["Rack", "Nivel", "Posicion"], direccion="Taller de mantencion")
    db.add_all([b_fit, b_man])
    db.flush()

    def rack(bodega, codigo, x, y, niveles, posiciones, ancho=6.0, rotacion=0, color=None):
        r = generar_rack(db, bodega, RackEntrada(codigo=codigo, niveles=niveles, posiciones=posiciones, capacidad_posicion=Decimal(400)))
        db.add(ElementoPlano(bodega_id=bodega.id, ubicacion_id=r.id, tipo="RACK", nombre=codigo, x=x, y=y, ancho=ancho, fondo=1.2,
                             alto=niveles * 1.5, rotacion=rotacion, color=color, parametros={"niveles": niveles, "posiciones": posiciones}))

    def area(bodega, tipo, codigo, x, y, ancho, fondo, color, almacena=True):
        ub = crear_ubicacion(db, bodega, codigo, tipo, nombre=codigo.capitalize()).id if almacena else None
        db.add(ElementoPlano(bodega_id=bodega.id, ubicacion_id=ub, tipo=tipo, nombre=codigo, x=x, y=y, ancho=ancho, fondo=fondo,
                             alto=0.08 if tipo != "OBSTACULO" else 6, color=color))

    for i, y in enumerate((1.0, 4.2, 7.4, 10.6), 1):
        rack(b_fit, f"R{i:02d}", 2, y, 3, 5)
    rack(b_fit, "R05", 10.5, 1.0, 3, 4, ancho=5)
    area(b_fit, "ZONA", "CUARENTENA", 17.5, 1, 5.5, 4, "#f59e0b")
    area(b_fit, "PISO", "TAMBORES", 10.5, 8.5, 6, 4.5, "#38bdf8")
    area(b_fit, "ZONA", "RECEPCION", 17.5, 8.5, 5.5, 4.5, "#34d399")
    area(b_fit, "PASILLO", "Pasillo A", 2, 2.7, 14, 1.2, "#94a3b8", almacena=False)
    area(b_fit, "OBSTACULO", "Pilar", 16.6, 6.3, 0.5, 0.5, "#64748b", almacena=False)
    rack(b_man, "R01", 1.5, 1, 4, 4, ancho=5)
    rack(b_man, "R02", 1.5, 4, 4, 4, ancho=5)
    area(b_man, "PISO", "LUBRICANTES", 9, 1, 5, 3.5, "#38bdf8")
    area(b_man, "ZONA", "HERRAMIENTAS", 9, 5.5, 5, 3.5, "#a78bfa")
    db.flush()
    db.scalar(select(Ubicacion).where(Ubicacion.codigo_completo == "FIT-TAMBORES")).capacidad_bultos = 12
    ubic = {x.codigo_completo: x.id for x in db.scalars(select(Ubicacion).where(Ubicacion.bodega_id.in_([b_fit.id, b_man.id])))}
    n_factura = [3400]

    def ingreso(codigo, cantidad, dias, ubicacion, precio=None, unidad=None, vence_en=None, bodega=b_fit, motivo="COMPRA", bultos=None,
                fabricado_hace=None) -> list[Existencia]:
        p = prod[codigo]
        n_factura[0] += 1
        fecha = (ahora_ - timedelta(days=dias)).replace(hour=14, minute=20, second=0, microsecond=0)
        unidad_id = u[unidad].id if unidad else (p.unidad_compra_id or p.unidad_base_id)
        factor = Decimal(1) if unidad_id == p.unidad_base_id else next(
            Decimal(str(c.factor)) for c in db.scalars(select(ConversionUnidad).where(ConversionUnidad.producto_id == p.id)))
        doc = DocumentoInventario(
            empresa_id=emp.id, numero=siguiente_numero(db, emp.id, "doc_INGRESO", "ING", 7), clase="INGRESO",
            motivo_id=motivos[("INGRESO", motivo)].id, tipo_documento="FACTURA" if motivo == "COMPRA" else "GUIA_INTERNA",
            numero_documento=f"F-{n_factura[0]}", fecha_documento=fecha.date(), fecha=fecha, proveedor_id=p.proveedor_id,
            bodega_id=bodega.id, usuario_id=ctx_bodega.usuario.id, moneda="CLP",
            temporada_id=db.scalar(select(Temporada.id).where(Temporada.empresa_id == emp.id, Temporada.actual.is_(True))))
        doc.detalles = [DetalleDocumentoInventario(
            producto_id=p.id, cantidad=cantidad, unidad_id=unidad_id, precio_unitario=precio if precio is not None else p.costo_referencial * factor,
            ubicacion_id=ubic[ubicacion], bultos=bultos,
            fecha_fabricacion=(fecha.date() - timedelta(days=fabricado_hace)) if fabricado_hace else None,
            fecha_vencimiento=(hoy() + timedelta(days=vence_en)) if vence_en is not None else None)]
        db.add(doc)
        db.flush()
        r = inv.confirmar_documento(db, ctx_bodega, doc)
        return [db.get(Existencia, i) for i in r["existencias"]]

    ex = {
        # Fungicida principal: dos ingresos con costo distinto, en racks distintos -> escenario de advertencia FIFO.
        "f1_viejo": ingreso("FUNG-001", 3, 75, "FIT-R01-N01-P01", precio=160000, vence_en=420),
        "f1_nuevo": ingreso("FUNG-001", 4, 12, "FIT-R02-N01-P02", precio=190000, vence_en=600),
        "f2": ingreso("FUNG-002", 4, 48, "FIT-R01-N02-P03", vence_en=24),          # proximo a vencer
        "f3": ingreso("FUNG-003", 2, 130, "FIT-R03-N01-P01", vence_en=200),        # stock antiguo y bajo minimo
        "d1_a": ingreso("DESI-001", 5, 40, "FIT-R02-N02-P01", precio=82000, vence_en=300),
        "d1_b": ingreso("DESI-001", 4, 9, "FIT-R02-N02-P02", precio=88000, vence_en=380),
        "d2": ingreso("DESI-002", 3, 28, "FIT-TAMBORES", vence_en=150),
        "d3": ingreso("DESI-003", 2, 95, "FIT-R03-N02-P02", vence_en=-6),          # vencido
        "c1": ingreso("CERA-001", 2, 20, "FIT-TAMBORES", vence_en=500),
        "co1": ingreso("COAD-001", 3, 33, "FIT-R04-N01-P01", vence_en=260),
        "co2": ingreso("COAD-002", 4, 15, "FIT-R04-N01-P03", vence_en=700),
        "cuar": ingreso("FUNG-002", 2, 3, "FIT-CUARENTENA", vence_en=540),         # recien llegado, en cuarentena
        "r1": ingreso("ROD-6204", 4, 60, "MAN-R01-N01-P01", bodega=b_man),
        "r2": ingreso("ROD-6305", 1, 85, "MAN-R01-N02-P02", bodega=b_man),         # bajo minimo
        "l1": ingreso("LUB-001", 2, 25, "MAN-LUBRICANTES", bodega=b_man),
        "l2": ingreso("LUB-002", 3, 45, "MAN-LUBRICANTES", bodega=b_man),
        "k1": ingreso("COR-A45", 8, 110, "MAN-R02-N01-P01", bodega=b_man, precio=4700),
    }
    cambiar_estado_lote(db, ctx, ex["cuar"][0].lote, "CUARENTENA", "Pendiente de certificado de analisis")

    # ---- integracion con la base productiva simulada
    crear_base_productiva()
    conexion = ConexionIntegracion(empresa_id=emp.id, nombre="Produccion (demo)", motor="demo", base_datos=ARCHIVO_PRODUCCION,
                                   usuario="lector_wms")
    db.add(conexion)
    db.flush()
    fuente = FuenteIntegracion(conexion_id=conexion.id, nombre="Corridas de packing", tipo="VISTA", origen="vw_wms_procesos",
                               columna_id="id_corrida", columna_fecha="fec_proceso", intervalo_minutos=0)
    fuente.conexion = conexion
    for externa, interno, transf, pol in (
            ("n_proceso", "codigo", None, "SOLO_IMPORTAR"), ("fec_proceso", "fecha", "FECHA", "SIEMPRE"),
            ("hora_ini", "hora_inicio", None, "SIEMPRE"), ("hora_fin", "hora_termino", None, "SIEMPRE"),
            ("nom_productor", "productor", None, "SIEMPRE"), ("cod_productor", "codigo_productor", None, "SIEMPRE"),
            ("des_especie", "especie", None, "SIEMPRE"), ("des_variedad", "variedad", None, "SIEMPRE"),
            ("n_lote", "lote_productivo", None, "SIEMPRE"), ("kilos_recepcion", "kilos_recepcionados", "NUMERO", "SIEMPRE"),
            ("peso_neto", "kilos_procesados", "NUMERO", "SIEMPRE"), ("kilos_embalados", "kilos_producidos", "NUMERO", "SIEMPRE"),
            ("cant_bins", "bins", "NUMERO", "SIEMPRE"), ("cant_cajas", "cajas", "NUMERO", "SIEMPRE"),
            ("des_exportadora", "exportadora", None, "SIEMPRE"), ("turno", "turno", None, "SIEMPRE"),
            ("linea", "linea", None, "SIEMPRE"), ("n_guia", "guia", None, "SIEMPRE"), ("predio", "predio", None, "SIEMPRE"),
            ("estado_corrida", "estado_externo", None, "SIEMPRE")):
        fuente.mapeos.append(MapeoIntegracion(columna_externa=externa, campo_interno=interno, transformacion=transf, politica_actualizacion=pol))
    db.add(fuente)
    db.flush()

    procesos: dict[int, Proceso] = {}
    for corrida in CORRIDAS[:8]:  # las dos ultimas quedan disponibles para demostrar la importacion
        p = importar_proceso(db, ctx, fuente, str(corrida[0]), emp.id)
        abierto = datetime.combine(p.fecha, datetime.min.time()).replace(hour=11)  # 08:00 hora de Chile, en UTC
        p.estado, p.abierto_en, p.abierto_por = "ABIERTO", abierto, ctx.usuario.id
        procesos[corrida[0]] = p
    db.flush()

    def consumir(id_corrida, existencia: Existencia, cantidad, minuto=0, confirmar=False, justificacion=None, quien=ctx_bodega):
        p = procesos[id_corrida]
        fecha = min(datetime.combine(p.fecha, datetime.min.time()).replace(hour=13, minute=minuto), ahora_ - timedelta(minutes=30 - minuto // 2))
        inv.registrar_salida(db, quien, existencia, Decimal(str(cantidad)), "CONSUMO", proceso=p, motivo_id=motivos[("SALIDA", "PROCESO")].id,
                             confirmar_fifo=confirmar, justificacion=justificacion, fecha=fecha, cantidad_ingresada=Decimal(str(cantidad)),
                             unidad_ingresada_id=existencia.unidad_id)

    f1v, f1n, d1a, d1b = ex["f1_viejo"], ex["f1_nuevo"], ex["d1_a"], ex["d1_b"]
    consumir(1001, f1v[0], 12, 5), consumir(1001, d1a[0], 18, 20), consumir(1001, ex["c1"][0], 35, 40)
    consumir(1002, f1v[0], 8, 5), consumir(1002, f1v[1], 9, 15), consumir(1002, d1a[0], 2, 30), consumir(1002, d1a[1], 20, 35), consumir(1002, ex["c1"][0], 50, 50)
    consumir(1003, f1v[1], 10, 5), consumir(1003, d1a[2], 14, 25), consumir(1003, ex["co1"][0], 2.5, 40), consumir(1003, ex["c1"][0], 28, 55)
    consumir(1004, ex["f2"][0], 6, 10), consumir(1004, d1a[2], 6, 20), consumir(1004, ex["d2"][0], 40, 45)
    consumir(1005, ex["f2"][0], 4, 10), consumir(1005, ex["f2"][1], 3.5, 12), consumir(1005, d1a[3], 9, 30), consumir(1005, ex["d2"][0], 55, 50)
    consumir(1006, f1v[2], 14, 5), consumir(1006, d1a[3], 11, 20), consumir(1006, ex["c1"][0], 42, 35), consumir(1006, ex["co2"][0], 6, 50)
    # Consumo fuera de FIFO (existencia nueva habiendo una mas antigua): queda como excepcion y alerta.
    consumir(1006, d1b[0], 5, 55, confirmar=True, justificacion="Bidon antiguo al fondo del rack")
    consumir(1007, f1v[2], 4, 5), consumir(1007, ex["d2"][0], 30, 25), consumir(1007, ex["co1"][0], 1.5, 40)
    consumir(1008, f1n[0], 4, 10, confirmar=True, quien=ctx), consumir(1008, d1b[0], 6, 25, confirmar=True)

    for id_corrida in (1001, 1002, 1003, 1004, 1005, 1006):
        p = procesos[id_corrida]
        cerrar_proceso(p.id, CierreEntrada(actualizar=True), db, ctx)
        p.cerrado_en = datetime.combine(p.fecha, datetime.min.time()).replace(hour=21, minute=30)
        p.ultima_sincronizacion = p.cerrado_en
    procesos[1007].ultima_sincronizacion = ahora_ - timedelta(hours=30)  # abierto y sin sincronizar hace mas de un dia
    avanzar_produccion()

    # Proceso manual (sin origen externo): sanitizacion de camaras.
    sanit = Proceso(empresa_id=emp.id, codigo=siguiente_numero(db, emp.id, "proceso", "PROC", 6), tipo="Sanitizacion de camaras",
                    fecha=hoy() - timedelta(days=2), estado="ABIERTO", abierto_en=ahora_ - timedelta(days=2), abierto_por=ctx.usuario.id,
                    observaciones="Proceso creado manualmente, sin kilos asociados.",
                    temporada_id=procesos[1001].temporada_id)
    db.add(sanit)
    db.flush()
    procesos[0] = sanit
    consumir(0, ex["d2"][0], 25, 10)

    # ---- reservas
    crear_reserva(db, ctx, ReservaEntrada(producto_id=prod["FUNG-001"].id, cantidad=Decimal(20), proceso_id=procesos[1008].id,
                                          area="Packing linea 1", motivo="Aplicacion programada turno tarde",
                                          fecha_vencimiento=ahora_ + timedelta(days=1)))
    crear_reserva(db, ctx, ReservaEntrada(producto_id=prod["DESI-001"].id, cantidad=Decimal(30), bodega_id=b_fit.id, area="Sanitizacion",
                                          motivo="Lavado de linea de fin de semana", documento_referencia="OT-2291"))
    vencida = crear_reserva(db, ctx, ReservaEntrada(producto_id=prod["COAD-001"].id, cantidad=Decimal(4), area="Packing linea 2",
                                                    motivo="Reserva no retirada", fecha_vencimiento=ahora_ + timedelta(hours=1)))
    vencida.fecha, vencida.fecha_vencimiento = ahora_ - timedelta(days=3), ahora_ - timedelta(days=1)

    # ---- traslado parcial, prestamos y merma
    inv.trasladar(db, ctx_bodega, ex["l2"][0], Decimal(10), b_fit.id, ubic["FIT-RECEPCION"], observacion="Aceite para bomba dosificadora")
    from app.modelos import Prestamo
    for existencia, cantidad, persona, area_, dias, plazo, devolver in ((ex["k1"][0], 2, "Carlos Mena", "Mantencion electrica", 9, -4, False),
                                                                      (ex["r1"][0], 5, "Patricia Lagos", "Linea 2", 20, -12, True)):
        m, _ = inv.registrar_salida(db, ctx, existencia, Decimal(cantidad), "PRESTAMO", evaluar_fifo=False,
                                    motivo_texto=f"Prestamo a {persona}", fecha=ahora_ - timedelta(days=dias))
        pr = Prestamo(empresa_id=emp.id, numero=siguiente_numero(db, emp.id, "prestamo", "PRE", 6), existencia_id=existencia.id,
                      producto_id=existencia.producto_id, cantidad=cantidad, persona=persona, area=area_,
                      fecha_prestamo=ahora_ - timedelta(days=dias), fecha_devolucion_esperada=hoy() + timedelta(days=plazo),
                      usuario_id=ctx.usuario.id, movimiento_salida_id=m.id, observacion="Dato de demostracion")
        if devolver:
            inv.aumentar(db, existencia, Decimal(cantidad))
            inv.movimiento(db, ctx, existencia, "DEVOLUCION_PRESTAMO", Decimal(cantidad), bodega_destino_id=existencia.bodega_id,
                           fecha=ahora_ - timedelta(days=dias - 6), motivo_texto=f"Devolucion de {pr.numero}")
            pr.cantidad_devuelta, pr.estado, pr.fecha_devolucion_real = cantidad, "DEVUELTO", ahora_ - timedelta(days=dias - 6)
        db.add(pr)
    inv.registrar_salida(db, ctx, ex["co2"][1], Decimal("3.5"), "MERMA", evaluar_fifo=False, motivo_id=motivos[("SALIDA", "MERMA")].id,
                         motivo_texto="Saco roto en descarga", fecha=ahora_ - timedelta(days=13))
    db.flush()

    # ---- inventario fisico: lo crea y cuenta la bodeguera, una linea la cuenta control de gestion (admin) y autoriza el jefe
    from app.modulos.operaciones import ConteoEntrada, LineaConteo, autorizar_conteo, cerrar_conteo, contar, crear_conteo
    ctx_jefe = Contexto(usuarios.get("jefe", admin), admin.permisos, "127.0.0.1", "Carga de datos demo")
    conteo = crear_conteo(ConteoEntrada(bodega_id=b_man.id, ubicacion_id=ubic["MAN-LUBRICANTES"], observaciones="Conteo mensual de lubricantes"),
                          db, ctx_bodega)
    contar(conteo["id"], LineaConteo(existencia_id=ex["l1"][0].id, cantidad=Decimal("23.5"), observacion="Envase abierto con merma"), db, ctx_bodega)
    contar(conteo["id"], LineaConteo(existencia_id=ex["l2"][0].id, cantidad=Decimal(50)), db, ctx)
    cerrar_conteo(conteo["id"], False, db, ctx_bodega)
    autorizar_conteo(conteo["id"], db, ctx_jefe)
    db.flush()
    evaluar_reglas(db, emp.id)


def crear_demo(db: Session) -> Empresa:
    """Instalacion completa del Modo Demo sobre una base vacia."""
    sembrar_base(db)
    emp = Empresa(codigo="DEMO", nombre="Agrofruticola Demo SpA", rut="76.000.000-0", moneda="CLP")
    db.add(emp)
    db.flush()
    roles = sembrar_empresa(db, emp)
    clave = hash_clave(CLAVE_DEMO)
    for usuario, nombre, rol in USUARIOS_DEMO:
        db.add(Usuario(empresa_id=emp.id, usuario=usuario, nombre=nombre, email=f"{usuario}@demo.local", clave_hash=clave, roles=[roles[rol]]))
    db.flush()
    sembrar_demo(db, emp)
    return emp
