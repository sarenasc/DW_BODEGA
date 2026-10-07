"""Fase 2: creador de lotes, correlativos, ingresos, existencias, valorizacion, QR y etiquetas."""
import threading
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select

from app.core import db as nucleo_db
from app.modelos import Existencia, Lote, MovimientoInventario, Producto
from app.servicios.lotes import ContextoLote, calcular_vencimiento, crear_lote, renderizar, validar_plantilla

SEP = {"tipo": "SEPARADOR", "configuracion": {"valor": "-"}}
CORR = {"tipo": "CORRELATIVO", "configuracion": {"largo": 5}}


def invariante_libro(api):
    """Para toda existencia, el saldo es la suma de sus movimientos; y el valor en libro no queda con residuo."""
    with api.sesion() as s:
        sumas = dict(s.execute(select(MovimientoInventario.existencia_id, func.sum(MovimientoInventario.cantidad))
                               .group_by(MovimientoInventario.existencia_id)).all())
        for e in s.scalars(select(Existencia)).unique():
            assert Decimal(str(sumas.get(e.id, 0))) == e.cantidad_fisica, e.codigo_publico
            assert e.cantidad_fisica >= 0


# ---------------------------------------------------------------- plantillas

def test_segmentos_y_vista_previa():
    ctx = ContextoLote(fecha=datetime(2026, 10, 6, 14, 5), producto="FUNG-X", familia="FITO", subfamilia="FUNG", bodega="FIT",
                       empresa="EMP", temporada="2026-2027", usuario="jperez", turno="A", proceso="PROC1", manuales={"origen": "ab"})
    seg = lambda tipo, **cfg: {"tipo": tipo, "configuracion": cfg}  # noqa: E731
    assert renderizar([seg("SUBFAMILIA"), SEP, seg("ANIO", digitos=2), SEP, CORR], ctx, 125) == "FUNG-26-00125"
    assert renderizar([seg("TEXTO", valor="FIT"), SEP, seg("FECHA", formato="YYYYMMDD"), SEP,
                       seg("CORRELATIVO", largo=4)], ctx, 1) == "FIT-20261006-0001"
    esperados = {"YYYYMMDD": "20261006", "DDMMYYYY": "06102026", "YYMMDD": "261006", "YYYY-MM-DD": "2026-10-06", "DD-MM-YYYY": "06-10-2026"}
    for fmt, esperado in esperados.items():
        assert renderizar([seg("FECHA", formato=fmt)], ctx, None) == esperado
    assert [renderizar([seg("MES", formato=f)], ctx, None) for f in ("NUMERO", "ABREV", "NOMBRE")] == ["10", "OCT", "OCTUBRE"]
    assert renderizar([seg("ANIO", digitos=4), seg("DIA"), seg("FECHA_HORA")], ctx, None) == "202606202610061405"
    assert renderizar([seg("PRODUCTO"), SEP, seg("FAMILIA"), SEP, seg("BODEGA"), SEP, seg("EMPRESA"), SEP, seg("TEMPORADA"),
                       SEP, seg("USUARIO", largo=3), SEP, seg("TURNO"), SEP, seg("PROCESO"), SEP, seg("MANUAL", clave="origen")],
                      ctx, None) == "FUNGX-FITO-FIT-EMP-20262027-JPE-A-PROC1-AB"
    assert renderizar([seg("CORRELATIVO", largo=3, inicio=100)], ctx, 1) == "100"


def test_validacion_detecta_colisiones():
    anio = {"tipo": "ANIO", "configuracion": {"digitos": 2}}
    sub = {"tipo": "SUBFAMILIA", "configuracion": {}}
    ok = validar_plantilla("AUTOMATICO", [sub, SEP, anio, SEP, CORR], ["SUBFAMILIA"], "ANUAL")
    assert not ok["errores"] and ok["ejemplos"][0].startswith("FUNG-")
    # Reinicio anual sin el anio en el codigo: el 1 de enero se repetiria el lote 00001.
    r = validar_plantilla("AUTOMATICO", [sub, SEP, CORR], ["SUBFAMILIA"], "ANUAL")
    assert r["errores"] and "Colision" in r["errores"][0] and "reinicia" in r["errores"][0]
    # Correlativo separado por producto, pero el codigo no identifica al producto.
    r = validar_plantilla("AUTOMATICO", [{"tipo": "TEXTO", "configuracion": {"valor": "L"}}, CORR], ["PRODUCTO"], "NUNCA")
    assert r["errores"] and "alcance" in r["errores"][0]
    assert not validar_plantilla("AUTOMATICO", [{"tipo": "TEXTO", "configuracion": {"valor": "L"}}, CORR], [], "NUNCA")["errores"]
    assert validar_plantilla("AUTOMATICO", [sub, SEP, anio], [], "NUNCA")["errores"]  # sin correlativo
    assert validar_plantilla("AUTOMATICO", [CORR, CORR], [], "NUNCA")["errores"]
    assert validar_plantilla("AUTOMATICO", [], [], "NUNCA")["errores"]
    assert validar_plantilla("AUTOMATICO", [{"tipo": "INVENTADO", "configuracion": {}}], [], "NUNCA")["errores"]
    corto = validar_plantilla("AUTOMATICO", [sub, {"tipo": "CORRELATIVO", "configuracion": {"largo": 2}}], ["SUBFAMILIA"], "NUNCA")
    assert not corto["errores"] and any("desborda" in a for a in corto["advertencias"])
    for reinicio, falta in (("DIARIO", [sub, SEP, anio, SEP, CORR]), ("MENSUAL", [sub, SEP, anio, SEP, CORR])):
        assert validar_plantilla("AUTOMATICO", falta, ["SUBFAMILIA"], reinicio)["errores"]


def test_plantilla_invalida_no_se_activa_y_versionado(api, base):
    mala = api.crear("/plantillas-lotes", {"codigo": "MALA", "nombre": "Mala", "reinicio": "ANUAL", "segmentos": [CORR]})
    r = api.post(f"/plantillas-lotes/{mala['id']}/activar", espera=400)
    assert r["codigo"] == "PLANTILLA_INVALIDA"
    vp = api.post("/plantillas-lotes/vista-previa", {"segmentos": base["plantilla"]["borrador"]["segmentos"],
                                                     "alcance": ["SUBFAMILIA"], "reinicio": "ANUAL"}, espera=200)
    assert vp["vista_previa"].startswith("FUNG-") and vp["vista_previa"].endswith("-00001") and not vp["errores"]

    pl = api.crear("/plantillas-lotes", {"codigo": "VER", "nombre": "Versionada",
                                         "segmentos": [{"tipo": "TEXTO", "configuracion": {"valor": "A"}}, CORR]})
    assert pl["activa"] is False and pl["borrador"]["version"] == 1
    v1 = api.post(f"/plantillas-lotes/{pl['id']}/activar", espera=200)
    assert v1["version_vigente"] == 1 and v1["borrador"] is None
    # Editar una plantilla activa no toca la version vigente: crea un borrador.
    v = api.put(f"/plantillas-lotes/{pl['id']}", {"segmentos": [{"tipo": "TEXTO", "configuracion": {"valor": "B"}}, CORR]})
    assert v["version_vigente"] == 1 and v["borrador"]["version"] == 2 and v["vigente"]["segmentos"][0]["configuracion"]["valor"] == "A"
    v2 = api.post(f"/plantillas-lotes/{pl['id']}/activar", espera=200)
    estados = {x["version"]: x for x in v2["versiones"]}
    assert estados[1]["estado"] == "RETIRADA" and estados[1]["vigente_hasta"] and estados[2]["estado"] == "VIGENTE"
    assert api.post(f"/plantillas-lotes/{pl['id']}/desactivar", espera=200)["activa"] is False


# ---------------------------------------------------------------- ingresos

def test_ingreso_por_envase_valoriza_y_genera_lote(api, base):
    p = base["producto"]("ING1", "Fungicida X")
    doc = base["ingreso"](p["id"], cantidad=2, precio=170000)
    assert doc["estado"] == "CONFIRMADO" and doc["costo_total"] == 340000
    linea = doc["detalles"][0]
    assert linea["cantidad_base"] == 40 and linea["costo_unitario_base"] == 8500 and linea["unidad"] == "bidon"
    anio = date.today().strftime("%y")
    assert linea["lote"].startswith(f"FUNG-{anio}-")
    ex = doc["existencias"]
    assert len(ex) == 2 and all(e["cantidad_fisica"] == 20 and e["costo_unitario"] == 8500 for e in ex)
    assert all(e["codigo_publico"].startswith("INV-") and e["ubicacion"] == "FIT-R01-N01-P01" for e in ex)
    assert ex[0]["codigo_publico"] != ex[1]["codigo_publico"] and ex[0]["lote"] == ex[1]["lote"]  # un lote, dos existencias
    movs = api.get("/movimientos", producto_id=p["id"])["items"]
    assert len(movs) == 2 and all(m["tipo"] == "INGRESO" and m["cantidad"] == 20 and m["costo_total"] == 170000 for m in movs)
    invariante_libro(api)


def test_granularidades(api, base):
    def existencias(granularidad, **linea):
        p = base["producto"](f"GR{granularidad[:6]}{len(linea)}", granularidad=granularidad)
        return base["ingreso"](p["id"], **linea)["existencias"]

    assert [e["cantidad_fisica"] for e in existencias("POR_ENVASE", cantidad=20, precio=1000)] == [20] * 20
    consolidada = existencias("CONSOLIDADA", cantidad=20, precio=1000)
    assert [(e["cantidad_fisica"], e["envases"]) for e in consolidada] == [(400, 20)]
    assert [e["cantidad_fisica"] for e in existencias("POR_LOTE", cantidad=20, precio=1000)] == [400]
    pallet = existencias("UNIDAD_LOGISTICA", cantidad=20, precio=1000)
    assert [(e["cantidad_fisica"], e["envases"], e["granularidad"]) for e in pallet] == [(400, 20, "UNIDAD_LOGISTICA")]
    dos_pallets = existencias("UNIDAD_LOGISTICA", cantidad=20, precio=1000, bultos=2)
    assert [(e["cantidad_fisica"], e["envases"]) for e in dos_pallets] == [(200, 10), (200, 10)]
    # Ingreso en unidad base con cantidad de envases explicita.
    en_litros = existencias("POR_ENVASE", cantidad=100, precio=50, unidad="L", bultos=4)
    assert [e["cantidad_fisica"] for e in en_litros] == [25] * 4
    invariante_libro(api)


def test_reparto_sin_residuo_de_redondeo(api, base):
    p = base["producto"]("RED1")
    doc = base["ingreso"](p["id"], cantidad=100, precio=333.33, unidad="L", bultos=3)
    ex = doc["existencias"]
    assert round(sum(e["cantidad_fisica"] for e in ex), 6) == 100
    movs = api.get("/movimientos", producto_id=p["id"])["items"]
    assert round(sum(m["costo_total"] for m in movs), 2) == 33333.0 == doc["costo_total"]


def test_capas_de_costo_se_conservan(api, base):
    p = base["producto"]("CAPA1")
    base["ingreso"](p["id"], cantidad=10, precio=8000, unidad="L")
    base["ingreso"](p["id"], cantidad=20, precio=9000, unidad="L")
    fila = api.get("/stock", producto_id=p["id"])[0]
    assert fila["stock_fisico"] == 30 and fila["valor_inventario"] == 260000 and fila["existencias"] == 2
    costos = sorted(e["costo_unitario"] for e in api.get("/existencias", producto_id=p["id"])["items"])
    assert costos == [8000, 9000]
    assert len(api.get("/stock", producto_id=p["id"], agrupar="lote")) == 2


def test_validaciones_de_ingreso(api, base):
    p = base["producto"]("VAL1")
    assert base["ingreso"](p["id"], precio=None, espera=400)["codigo"] == "COSTO_REQUERIDO"
    assert base["ingreso"](p["id"], cantidad=0, espera=400)["codigo"] == "CANTIDAD"
    assert base["ingreso"](p["id"], unidad="saco", espera=400)["codigo"] == "SIN_CONVERSION"
    assert base["ingreso"](p["id"], ubicacion="FIT-R01", espera=400)["codigo"] == "UBICACION"  # un rack no almacena
    api.put(f"/productos/{p['id']}", {"requiere_ubicacion": True})
    assert base["ingreso"](p["id"], ubicacion=None, espera=400)["codigo"] == "UBICACION_REQUERIDA"
    assert base["ingreso"](p["id"], fecha="2031-01-01T00:00:00", espera=400)["codigo"] == "FECHA"
    # Compra exige numero de documento.
    r = api.post("/documentos", {"clase": "INGRESO", "motivo_id": base["motivos"][("INGRESO", "COMPRA")],
                                 "bodega_id": base["bodega"]["id"], "confirmar": True,
                                 "detalles": [{"producto_id": p["id"], "cantidad": 1, "precio_unitario": 10}]}, espera=400)
    assert r["codigo"] == "DOCUMENTO_REQUERIDO"
    assert api.get("/existencias", producto_id=p["id"])["total"] == 0  # nada quedo a medias
    base["ingreso"](p["id"], como="lector", espera=403)


def test_correlativo_y_lote_manual(api, base):
    p = base["producto"]("COR1")
    lotes = [base["ingreso"](p["id"])["detalles"][0]["lote"] for _ in range(3)]
    numeros = [int(x.split("-")[-1]) for x in lotes]
    assert numeros[1] == numeros[0] + 1 and numeros[2] == numeros[1] + 1
    # Producto sin plantilla: el lote interno se digita y debe ser unico.
    sub = api.crear("/subfamilias", {"familia_id": base["familia"]["id"], "codigo": "MANU", "nombre": "Sin plantilla"})
    m = api.crear("/productos", {"codigo": "MAN1", "nombre": "Manual", "subfamilia_id": sub["id"], "unidad_base_id": base["u"]["L"]})
    assert base["ingreso"](m["id"], unidad="L", espera=400)["codigo"] == "LOTE_REQUERIDO"
    doc = base["ingreso"](m["id"], unidad="L", lote_manual="lote-a1", referencia_externa="PROV-778")
    assert doc["detalles"][0]["lote"] == "LOTE-A1"
    assert base["ingreso"](m["id"], unidad="L", lote_manual="LOTE-A1", espera=409)["codigo"] == "LOTE_DUPLICADO"
    lote = api.get("/lotes", q="LOTE-A1")["items"][0]
    assert lote["referencia_externa"] == "PROV-778" and lote["cantidad_inicial"] == 1 and lote["valor_inicial"] == 170000
    # Producto que no usa lote: stock agregado sin lote.
    s = api.crear("/productos", {"codigo": "SINL", "nombre": "Sin lote", "subfamilia_id": sub["id"],
                                 "unidad_base_id": base["u"]["un"], "usa_lote": False})
    assert base["ingreso"](s["id"], unidad="un", cantidad=50, precio=100)["existencias"][0]["lote"] is None


def test_vencimiento_manual_y_calculado(api, base):
    assert calcular_vencimiento({"vida_util_meses": 24, "prioridad_vencimiento": "CALCULADA"}, None, date(2026, 1, 1)) == date(2028, 1, 1)
    assert calcular_vencimiento({"vida_util_meses": 1}, None, date(2026, 1, 31)) == date(2026, 2, 28)
    manual, fab = date(2027, 5, 5), date(2026, 1, 1)
    assert calcular_vencimiento({"vida_util_meses": 24, "prioridad_vencimiento": "MANUAL"}, manual, fab) == manual
    assert calcular_vencimiento({"vida_util_meses": 24, "prioridad_vencimiento": "CALCULADA"}, manual, fab) == date(2028, 1, 1)
    p = base["producto"]("VEN1", usa_vencimiento=True, vida_util_meses=24)
    assert base["ingreso"](p["id"], espera=400)["codigo"] == "VENCIMIENTO_REQUERIDO"
    doc = base["ingreso"](p["id"], fecha_fabricacion="2026-01-01")
    assert doc["existencias"][0]["fecha_vencimiento"] == "2028-01-01"


def test_borrador_editable_y_confirmado_inmutable(api, base):
    p = base["producto"]("BOR1")
    d = {"clase": "INGRESO", "motivo_id": base["motivos"][("INGRESO", "COMPRA")], "numero_documento": "F-9",
         "bodega_id": base["bodega"]["id"], "detalles": [{"producto_id": p["id"], "cantidad": 1, "unidad_id": base["u"]["bidon"],
                                                          "precio_unitario": 100000}]}
    doc = api.crear("/documentos", d)
    assert doc["estado"] == "BORRADOR" and api.get("/existencias", producto_id=p["id"])["total"] == 0
    d["detalles"][0]["cantidad"] = 3
    doc = api.put(f"/documentos/{doc['id']}", d)
    assert doc["detalles"][0]["cantidad"] == 3 and doc["estado"] == "BORRADOR"
    doc = api.post(f"/documentos/{doc['id']}/confirmar", espera=200)
    assert doc["estado"] == "CONFIRMADO" and len(doc["existencias"]) == 3
    assert api.put(f"/documentos/{doc['id']}", d, espera=409)["codigo"] == "ESTADO"
    assert api.post(f"/documentos/{doc['id']}/confirmar", espera=409)["codigo"] == "ESTADO"


def test_anular_ingreso_revierte_sin_borrar(api, base):
    p = base["producto"]("ANU1")
    doc = base["ingreso"](p["id"], cantidad=2)
    api.post(f"/documentos/{doc['id']}/anular", {"motivo": ""}, espera=400)
    api.post(f"/documentos/{doc['id']}/anular", {"motivo": "x"}, espera=403, como="digitador")
    anulado = api.post(f"/documentos/{doc['id']}/anular", {"motivo": "Factura duplicada"}, espera=200)
    assert anulado["estado"] == "ANULADO" and anulado["motivo_anulacion"] == "Factura duplicada"
    assert api.get("/stock", producto_id=p["id"]) == []
    movs = api.get("/movimientos", producto_id=p["id"])["items"]
    assert sorted(m["tipo"] for m in movs) == ["ANULACION", "ANULACION", "INGRESO", "INGRESO"]  # la historia se conserva
    assert sum(m["cantidad"] for m in movs) == 0 and sum(m["costo_total"] for m in movs) == 0
    assert all(e["estado"] == "ANULADA" for e in api.get("/existencias", producto_id=p["id"], con_stock=False)["items"])
    assert api.get("/lotes", q=doc["detalles"][0]["lote"])["items"][0]["estado"] == "ANULADO"
    api.post(f"/documentos/{doc['id']}/anular", {"motivo": "otra vez"}, espera=409)
    invariante_libro(api)


# ---------------------------------------------------------------- QR

def test_qr_resuelve_existencia_y_etiquetas(api, base):
    p = base["producto"]("QR1", "Producto con QR")
    e = base["ingreso"](p["id"])["existencias"][0]
    det = api.get(f"/existencias/{e['id']}")
    token = det["token_qr"]
    assert len(token) == 26 and token != e["codigo_publico"] and str(e["id"]) not in token
    for leido in (token, token.lower(), f"https://wms.ejemplo.cl/q/{token}", f"http://otro-host/q/{token}/", e["codigo_publico"]):
        assert api.get("/existencias/por-codigo", codigo=leido)["id"] == e["id"]
    assert api.get("/existencias/por-codigo", espera=404, codigo="NOEXISTE")["codigo"] == "QR_DESCONOCIDO"
    svg = api.get(f"/existencias/{e['id']}/qr")
    assert svg.headers["content-type"].startswith("image/svg") and b"<svg" in svg.content
    pdf = api.get("/etiquetas", existencias=str(e["id"]))
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content[:4] == b"%PDF"
    assert api.get(f"/existencias/{e['id']}")["etiquetas_impresas"] == 1
    assert api.c.get(f"/q/{token}", follow_redirects=False).headers["location"] == f"/existencia/?token={token}"
    api.get("/etiquetas", espera=403, como="lector", existencias=str(e["id"]))


def test_lector_sin_permiso_de_costos_no_ve_valores(api, base):
    p = base["producto"]("OCU1")
    e = base["ingreso"](p["id"])["existencias"][0]
    visto = api.get(f"/existencias/{e['id']}", como="lector")
    assert visto["costo_unitario"] is None and visto["valor_disponible"] is None and visto["cantidad_fisica"] == 20
    assert api.get("/stock", producto_id=p["id"], como="lector")[0]["valor_inventario"] is None
    assert api.get("/stock", producto_id=p["id"], como="jefe")[0]["valor_inventario"] == 170000


# ---------------------------------------------------------------- concurrencia

def test_generacion_concurrente_de_lotes_sin_duplicados(api, base):
    p = base["producto"]("CONC1")
    resultados, errores = [], []

    def trabajo():
        try:
            with nucleo_db.nueva_sesion() as s, s.begin():
                producto = s.get(Producto, p["id"])
                resultados.append(crear_lote(s, None, producto, fecha=datetime(2026, 9, 1)).codigo)
        except Exception as e:  # noqa: BLE001
            errores.append(repr(e))

    hilos = [threading.Thread(target=trabajo) for _ in range(16)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not errores, errores
    numeros = sorted(int(c.split("-")[-1]) for c in resultados)
    assert len(set(resultados)) == 16 and numeros == list(range(numeros[0], numeros[0] + 16))  # unicos y sin saltos
    with api.sesion() as s:
        assert s.scalar(select(func.count()).select_from(Lote).where(Lote.codigo.in_(resultados))) == 16
