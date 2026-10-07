"""Fase 7 y 8: traslados, inventario fisico, prestamos, fraccionamiento, apertura de envase, adjuntos y plano de bodega."""
from datetime import date, timedelta

import pytest

from .test_fase2_lotes_inventario import invariante_libro

F1 = "2026-09-01T10:00:00"


def trasladar(api, base, existencia, cantidad, destino_bodega=None, destino_ubicacion=None, espera=201, como="admin"):
    return api.post("/documentos", {
        "clase": "TRASLADO", "bodega_id": existencia["bodega_id"], "bodega_destino_id": destino_bodega, "confirmar": True,
        "detalles": [{"existencia_id": existencia["id"], "cantidad": cantidad,
                      "ubicacion_destino_id": base["ubic"].get(destino_ubicacion) if destino_ubicacion else None}]},
        espera=espera, como=como)


# ---------------------------------------------------------------- traslados

def test_traslado_total_conserva_existencia_y_qr(api, base):
    p = base["producto"]("TRA1")
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    token = api.get(f"/existencias/{e['id']}")["token_qr"]
    doc = trasladar(api, base, e, 20, destino_ubicacion="FIT-R01-N02-P03")
    assert doc["estado"] == "CONFIRMADO" and doc["numero"].startswith("TRA-")
    d = api.get(f"/existencias/{e['id']}")
    assert d["ubicacion"] == "FIT-R01-N02-P03" and d["cantidad_fisica"] == 20 and d["token_qr"] == token
    movs = api.get("/movimientos", existencia_id=e["id"])["items"]
    assert [m["tipo"] for m in movs] == ["TRASLADO_ENTRADA", "TRASLADO_SALIDA", "INGRESO"]  # salida y entrada relacionadas
    assert movs[0]["documento_id"] == movs[1]["documento_id"] == doc["id"]
    assert movs[1]["ubicacion_origen_id"] == base["ubic"]["FIT-R01-N01-P01"] and movs[1]["ubicacion_destino_id"] == base["ubic"]["FIT-R01-N02-P03"]
    assert sum(m["cantidad"] for m in movs) == 20 and sum(m["costo_total"] for m in movs) == 170000
    assert trasladar(api, base, e, 20, destino_ubicacion="FIT-R01-N02-P03", espera=400)["codigo"] == "MISMO_DESTINO"
    invariante_libro(api)


def test_traslado_parcial_entre_bodegas_hereda_costo_y_antiguedad(api, base):
    p = base["producto"]("TRA2")
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    trasladar(api, base, e, 8, destino_bodega=base["bodega2"]["id"])
    todas = api.get("/existencias", producto_id=p["id"])["items"]
    origen = next(x for x in todas if x["id"] == e["id"])
    hija = next(x for x in todas if x["id"] != e["id"])
    assert origen["cantidad_fisica"] == 12 and hija["cantidad_fisica"] == 8 and hija["bodega"] == "Bodega Mantencion"
    # La parte trasladada hereda lote, costo y fecha de ingreso (el traslado no rejuvenece el stock), con QR propio.
    assert hija["lote"] == origen["lote"] and hija["costo_unitario"] == 8500 and hija["fecha_ingreso"] == origen["fecha_ingreso"]
    assert hija["existencia_padre_id"] == e["id"] and hija["codigo_publico"] != origen["codigo_publico"]
    por_bodega = {f["bodega"]: f["stock_fisico"] for f in api.get("/stock", producto_id=p["id"], agrupar="bodega")}
    assert por_bodega == {"Bodega Fitosanitarios": 12, "Bodega Mantencion": 8}
    assert api.get("/stock", producto_id=p["id"])[0]["valor_inventario"] == 170000  # el valor total no cambia
    assert trasladar(api, base, e, 50, destino_bodega=base["bodega2"]["id"], espera=409)["codigo"] == "STOCK_INSUFICIENTE"
    trasladar(api, base, e, 1, destino_bodega=base["bodega2"]["id"], espera=403, como="lector")
    api.post(f"/documentos/{api.get('/documentos', clase='TRASLADO')['items'][0]['id']}/anular", {"motivo": "x"}, espera=400)
    invariante_libro(api)


def test_asignar_ubicacion_despues_del_ingreso(api, base):
    p = base["producto"]("UBI1")
    e = base["ingreso"](p["id"], ubicacion=None)["existencias"][0]
    assert e["ubicacion"] is None and api.get("/existencias", producto_id=p["id"], sin_ubicacion=True)["total"] == 1
    d = api.post(f"/existencias/{e['id']}/ubicar", {"ubicacion_id": base["ubic"]["FIT-R01-N01-P02"]}, espera=200)
    assert d["ubicacion"] == "FIT-R01-N01-P02"
    api.post(f"/existencias/{e['id']}/ubicar", {"ubicacion_id": base["ubic"]["FIT-R01"]}, espera=400)  # un rack no almacena


def test_ajuste_por_documento(api, base):
    p = base["producto"]("AJU1")
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    d = {"clase": "AJUSTE", "bodega_id": e["bodega_id"], "confirmar": True, "detalles": [{"existencia_id": e["id"], "cantidad": -2.5}]}
    assert api.post("/documentos", d, espera=400)["codigo"] == "MOTIVO"
    api.post("/documentos", {**d, "observaciones": "Derrame"}, espera=403, como="digitador")
    api.post("/documentos", {**d, "observaciones": "Derrame"}, espera=201, como="jefe")
    api.post("/documentos", {**d, "observaciones": "Sobrante", "detalles": [{"existencia_id": e["id"], "cantidad": 1}]}, espera=201)
    movs = api.get("/movimientos", existencia_id=e["id"])["items"]
    assert [(m["tipo"], m["cantidad"], m["costo_total"]) for m in movs[:2]] == [("AJUSTE_POSITIVO", 1, 8500), ("AJUSTE_NEGATIVO", -2.5, -21250)]
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 18.5


# ---------------------------------------------------------------- inventario fisico

def test_inventario_fisico_completo(api, base):
    bod = api.crear("/bodegas", {"codigo": "CNT", "nombre": "Bodega Conteo"})
    u1 = api.crear("/ubicaciones", {"bodega_id": bod["id"], "codigo": "Z1"})
    u2 = api.crear("/ubicaciones", {"bodega_id": bod["id"], "codigo": "Z2"})
    p = base["producto"]("CNT1", "Producto Conteo")

    def ingreso(ubicacion_id):
        return api.post("/documentos", {"clase": "INGRESO", "motivo_id": base["motivos"][("INGRESO", "ACTUALIZACION_STOCK")],
                                        "bodega_id": bod["id"], "confirmar": True, "detalles": [{
                                            "producto_id": p["id"], "cantidad": 1, "unidad_id": base["u"]["bidon"],
                                            "precio_unitario": 100000, "ubicacion_id": ubicacion_id}]}, espera=201)["existencias"][0]

    a, b, c, fuera = ingreso(u1["id"]), ingreso(u1["id"]), ingreso(u1["id"]), ingreso(u2["id"])
    conteo = api.crear("/conteos", {"bodega_id": bod["id"], "ubicacion_id": u1["id"]}, como="digitador")
    assert conteo["estado"] == "ABIERTO" and conteo["lineas"] == 3 and conteo["numero"].startswith("CNT-")
    token = api.get(f"/existencias/{a['id']}")["token_qr"]
    r = api.post(f"/conteos/{conteo['id']}/contar", {"codigo": token, "cantidad": 20}, espera=200, como="digitador")  # escaneo QR
    assert r["linea"]["diferencia"] == 0 and r["linea"]["valor_diferencia"] is None  # el digitador no ve costos
    r = api.post(f"/conteos/{conteo['id']}/contar", {"existencia_id": b["id"], "cantidad": 17.5}, espera=200)
    assert (r["linea"]["cantidad_sistema"], r["linea"]["cantidad_contada"], r["linea"]["diferencia"]) == (20, 17.5, -2.5)
    assert r["linea"]["valor_diferencia"] == -12500
    r = api.post(f"/conteos/{conteo['id']}/contar", {"existencia_id": fuera["id"], "cantidad": 21}, espera=200)
    assert "fuera de su ubicacion" in r["linea"]["observacion"] and r["conteo"]["lineas"] == 4
    api.post(f"/conteos/{conteo['id']}/contar", {"existencia_id": a["id"], "cantidad": -1}, espera=422)

    # Hasta la autorizacion nada cambia en el stock.
    api.post(f"/conteos/{conteo['id']}/autorizar", espera=409)
    revision = api.post(f"/conteos/{conteo['id']}/cerrar", espera=200, como="digitador")
    assert revision["estado"] == "EN_REVISION" and revision["con_diferencia"] == 2 and revision["contadas"] == 3
    assert api.get(f"/existencias/{b['id']}")["cantidad_fisica"] == 20
    alerta = api.get("/alertas", tipo="DIFERENCIA_INVENTARIO", abiertas=True)["items"][0]
    assert alerta["entidad_id"] == conteo["id"] and "2 existencia" in alerta["descripcion"]
    api.post(f"/conteos/{conteo['id']}/contar", {"existencia_id": c["id"], "cantidad": 1}, espera=409)
    api.post(f"/conteos/{conteo['id']}/autorizar", espera=403, como="digitador")

    final = api.post(f"/conteos/{conteo['id']}/autorizar", espera=200, como="jefe")
    assert final["estado"] == "AUTORIZADO" and final["ajustes_generados"] == 2
    assert api.get(f"/existencias/{b['id']}")["cantidad_fisica"] == 17.5 and api.get(f"/existencias/{fuera['id']}")["cantidad_fisica"] == 21
    assert api.get(f"/existencias/{c['id']}")["cantidad_fisica"] == 20  # no contada: no se ajusta
    ajuste = api.get("/movimientos", existencia_id=b["id"])["items"][0]
    assert (ajuste["tipo"], ajuste["cantidad"], ajuste["motivo_texto"]) == ("AJUSTE_NEGATIVO", -2.5, f"Inventario fisico {conteo['numero']}")
    assert not api.get("/alertas", tipo="DIFERENCIA_INVENTARIO", abiertas=True)["items"]
    reporte = api.get("/reportes/inventario_fisico", bodega_id=bod["id"])["filas"]
    assert len(reporte) == 4 and sum(1 for f in reporte if f["ajustado"] == "SI") == 2
    invariante_libro(api)

    # Variante: lo no encontrado se registra en cero.
    otro = api.crear("/conteos", {"bodega_id": bod["id"], "ubicacion_id": u1["id"]})
    api.post(f"/conteos/{otro['id']}/contar", {"existencia_id": a["id"], "cantidad": 20}, espera=200)
    cerrado = api.post(f"/conteos/{otro['id']}/cerrar?no_contadas_en_cero=true", espera=200)
    assert cerrado["con_diferencia"] == 2
    assert api.post(f"/conteos/{otro['id']}/anular", espera=200)["estado"] == "ANULADO"
    assert api.get(f"/existencias/{c['id']}")["cantidad_fisica"] == 20


# ---------------------------------------------------------------- prestamos

def test_prestamo_y_devolucion(api, base):
    p = base["producto"]("PRE1", "Producto Prestado")
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    espera = (date.today() + timedelta(days=3)).isoformat()
    pr = api.crear("/prestamos", {"existencia_id": e["id"], "cantidad": 6, "persona": "Maria Rojas", "area": "Mantencion",
                                  "fecha_devolucion_esperada": espera, "observacion": "Para prueba de linea"})
    assert (pr["estado"], pr["pendiente"], pr["persona"], pr["area"], pr["vencido"]) == ("ACTIVO", 6, "Maria Rojas", "Mantencion", False)
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 14
    api.post(f"/prestamos/{pr['id']}/devolver", {"cantidad": 7}, espera=400)
    parcial = api.post(f"/prestamos/{pr['id']}/devolver", {"cantidad": 2}, espera=200)
    assert (parcial["estado"], parcial["pendiente"]) == ("PARCIAL", 4)
    total = api.post(f"/prestamos/{pr['id']}/devolver", {}, espera=200)
    assert total["estado"] == "DEVUELTO" and total["fecha_devolucion_real"] and total["pendiente"] == 0
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 20
    tipos = [m["tipo"] for m in api.get("/movimientos", existencia_id=e["id"])["items"]]
    assert tipos == ["DEVOLUCION_PRESTAMO", "DEVOLUCION_PRESTAMO", "PRESTAMO", "INGRESO"]
    api.post(f"/prestamos/{pr['id']}/devolver", {}, espera=409)
    api.post("/prestamos", {"existencia_id": e["id"], "cantidad": 30, "persona": "X"}, espera=409)
    api.post("/prestamos", {"existencia_id": e["id"], "cantidad": 1, "persona": " "}, espera=400)
    api.post("/prestamos", {"existencia_id": e["id"], "cantidad": 1, "persona": "X"}, espera=403, como="lector")
    assert api.get("/reportes/prestamos", producto_id=p["id"])["filas"][0]["estado"] == "DEVUELTO"
    invariante_libro(api)


# ---------------------------------------------------------------- fraccionamiento y apertura

def test_fraccionamiento_con_sublotes(api, base):
    """Tambor de 200 L -> 4 bidones de 50 L."""
    p = base["producto"]("FRA1", granularidad="CONSOLIDADA")
    tambor = base["ingreso"](p["id"], cantidad=200, precio=1000, unidad="L", fecha=F1)["existencias"][0]
    r = api.post(f"/existencias/{tambor['id']}/fraccionar", {"partes": [{"cantidad": 50}] * 4}, espera=201)
    assert r["origen"]["cantidad_fisica"] == 0 and r["origen"]["estado"] == "AGOTADA"
    lote = tambor["lote"]
    assert [n["lote"] for n in r["nuevas"]] == [f"{lote}-01", f"{lote}-02", f"{lote}-03", f"{lote}-04"]
    assert all(n["cantidad_fisica"] == 50 and n["costo_unitario"] == 1000 and n["existencia_padre_id"] == tambor["id"] for n in r["nuevas"])
    assert all(n["fecha_ingreso"] == tambor["fecha_ingreso"] for n in r["nuevas"])  # conserva la antiguedad
    assert api.get("/stock", producto_id=p["id"])[0]["valor_inventario"] == 200000
    detalle = api.get(f"/lotes/{tambor['lote_id']}")
    assert len(detalle["sublotes"]) == 4 and detalle["cantidad_disponible"] == 0
    aud = api.get("/auditoria", entidad="existencia", entidad_id=str(tambor["id"]), accion="FRACCIONAR")["items"][0]
    assert aud["valor_nuevo"]["lote_origen"] == lote and aud["valor_nuevo"]["cantidad_origen"] == 200 and len(aud["valor_nuevo"]["partes"]) == 4
    traza = api.get(f"/trazabilidad/lote/{tambor['lote_id']}")
    assert traza["resumen"]["lote"] == 5 and traza["resumen"]["existencia"] == 5
    invariante_libro(api)


def test_fraccionamiento_parcial_sin_sublotes(api, base):
    p = base["producto"]("FRA2", permite_sublotes=False)
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    api.post(f"/existencias/{e['id']}/fraccionar", {"partes": [{"cantidad": 15}, {"cantidad": 10}]}, espera=409)
    r = api.post(f"/existencias/{e['id']}/fraccionar", {"partes": [{"cantidad": 5}, {"cantidad": 5, "ubicacion_id": base["ubic"]["FIT-R01-N02-P02"]}]}, espera=201)
    assert r["origen"]["cantidad_fisica"] == 10 and [n["lote"] for n in r["nuevas"]] == [e["lote"]] * 2
    assert r["nuevas"][1]["ubicacion"] == "FIT-R01-N02-P02"
    api.post(f"/existencias/{e['id']}/fraccionar", {"partes": []}, espera=422)
    api.post(f"/existencias/{e['id']}/fraccionar", {"partes": [{"cantidad": 1}]}, espera=403, como="lector")


def test_apertura_de_envase_y_vida_util(api, base):
    p = base["producto"]("APE1", vida_util_abierto_dias=30)
    e = base["ingreso"](p["id"], fecha=F1)["existencias"][0]
    proc = api.crear("/procesos", {"codigo": "PROC-APE"})
    api.post(f"/procesos/{proc['id']}/abrir", espera=200)
    api.post("/consumos", {"proceso_id": proc["id"], "existencia_id": e["id"], "cantidad": 6}, espera=201)
    d = api.post(f"/existencias/{e['id']}/abrir", espera=200, como="digitador")
    assert d["fecha_apertura"] and d["vence_abierta"] == (date.today() + timedelta(days=30)).isoformat()
    aud = api.get("/auditoria", entidad="existencia", entidad_id=str(e["id"]), accion="ABRIR_ENVASE")["items"][0]
    assert aud["valor_nuevo"]["cantidad_restante"] == 14 and aud["usuario"] == "Digitador"
    api.post(f"/existencias/{e['id']}/abrir", espera=409)
    # Vencida la vida util tras apertura, el consumo exige el permiso de vencidos.
    from app.modelos import Existencia
    with api.sesion() as s:
        s.get(Existencia, e["id"]).vence_abierta = date.today() - timedelta(days=1)
        s.commit()
    r = api.post("/consumos", {"proceso_id": proc["id"], "existencia_id": e["id"], "cantidad": 1}, espera=403, como="digitador")
    assert r["codigo"] == "LOTE_VENCIDO"
    sin_regla = base["producto"]("APE2")
    e2 = base["ingreso"](sin_regla["id"], fecha=F1)["existencias"][0]
    assert api.post(f"/existencias/{e2['id']}/abrir", espera=200)["vence_abierta"] is None


# ---------------------------------------------------------------- adjuntos

def test_adjuntos(api, base):
    p = base["producto"]("ADJ1")
    doc = base["ingreso"](p["id"])
    cab = {"Authorization": f"Bearer {api.token('admin')}"}
    pdf = b"%PDF-1.4\n%factura de prueba\n"

    def subir(nombre, contenido, tipo="FACTURA", entidad="documento", como="admin"):
        return api.c.post("/api/adjuntos", headers={"Authorization": f"Bearer {api.token(como)}"},
                          data={"entidad": entidad, "entidad_id": str(doc["id"]), "tipo": tipo}, files={"archivo": (nombre, contenido)})

    r = subir("../../factura 1001.pdf", pdf)
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["nombre_archivo"] == "factura 1001.pdf" and a["tamano"] == len(pdf) and a["mime"] == "application/pdf" and "ruta" not in a
    lista = api.get("/adjuntos", entidad="documento", entidad_id=doc["id"])
    assert len(lista) == 1 and lista[0]["usuario"] == "Admin" and len(lista[0]["sha256"]) == 64
    bajado = api.c.get(f"/api/adjuntos/{a['id']}/descargar", headers=cab)
    assert bajado.content == pdf and "factura" in bajado.headers["content-disposition"]
    assert subir("virus.exe", b"MZ").status_code == 400
    assert subir("falso.pdf", b"no soy un pdf").status_code == 400
    assert subir("vacio.pdf", b"").status_code == 400
    assert subir("f.pdf", pdf, tipo="INVENTADO").status_code == 400
    assert subir("f.pdf", pdf, entidad="usuarios").status_code == 400
    assert subir("f.pdf", pdf, como="lector").status_code == 403
    assert subir("ficha.png", b"\x89PNG....", tipo="FICHA_TECNICA", entidad="producto").status_code == 201
    api.delete(f"/adjuntos/{a['id']}", espera=403, como="lector")
    api.delete(f"/adjuntos/{a['id']}")
    assert api.c.get(f"/api/adjuntos/{a['id']}/descargar", headers=cab).status_code == 404
    assert api.get("/auditoria", entidad="adjunto", accion="ELIMINAR")["items"][0]["valor_anterior"]["nombre"] == "factura 1001.pdf"


# ---------------------------------------------------------------- plano 2D / 3D

def test_plano_genera_ubicaciones_y_protege_stock(api, base):
    bod = api.crear("/bodegas", {"codigo": "PLA", "nombre": "Bodega Plano", "largo": 30, "ancho": 20, "alto": 8})
    plano = api.put(f"/bodegas/{bod['id']}/plano", {"largo": 30, "ancho": 20, "alto": 8, "elementos": [
        {"tipo": "RACK", "nombre": "R01", "x": 2, "y": 2, "ancho": 6, "fondo": 1.2, "alto": 5, "parametros": {"niveles": 3, "posiciones": 4}},
        {"tipo": "RACK", "nombre": "R02", "x": 2, "y": 6, "ancho": 6, "fondo": 1.2, "alto": 5, "rotacion": 90, "parametros": {"niveles": 2, "posiciones": 2}},
        {"tipo": "ZONA", "nombre": "CUARENTENA", "x": 20, "y": 2, "ancho": 6, "fondo": 6, "alto": 0.1, "color": "#f59e0b"},
        {"tipo": "PISO", "nombre": "PISO1", "x": 12, "y": 12, "ancho": 4, "fondo": 4, "alto": 0.1},
        {"tipo": "PASILLO", "nombre": "Pasillo A", "x": 2, "y": 4, "ancho": 20, "fondo": 1.5, "alto": 0.05},
        {"tipo": "OBSTACULO", "nombre": "Pilar", "x": 15, "y": 8, "ancho": 0.5, "fondo": 0.5, "alto": 8}]})
    assert len(plano["elementos"]) == 6
    codigos = {u["codigo_completo"] for u in plano["ubicaciones"]}
    # Cada posicion fisica corresponde a una ubicacion logica con codigo jerarquico.
    assert {"PLA-R01", "PLA-R01-N03-P04", "PLA-R02-N02-P02", "PLA-CUARENTENA", "PLA-PISO1"} <= codigos
    assert len(codigos) == (1 + 3 + 12) + (1 + 2 + 4) + 2
    r1 = next(e for e in plano["elementos"] if e["nombre"] == "R01")
    assert r1["ubicacion_id"] and r1["parametros"] == {"niveles": 3, "posiciones": 4}

    # Mover, redimensionar y duplicar: reenviar el plano con ids conserva las ubicaciones existentes.
    elementos = [dict(e) for e in plano["elementos"]]
    next(e for e in elementos if e["nombre"] == "R01").update(x=10, y=3, rotacion=90)
    elementos.append({"tipo": "RACK", "nombre": "R03", "x": 2, "y": 10, "ancho": 6, "fondo": 1.2, "alto": 5,
                      "parametros": {"niveles": 3, "posiciones": 4}})
    plano2 = api.put(f"/bodegas/{bod['id']}/plano", {"elementos": elementos})
    r1b = next(e for e in plano2["elementos"] if e["nombre"] == "R01")
    assert (r1b["x"], r1b["rotacion"], r1b["ubicacion_id"]) == (10, 90, r1["ubicacion_id"]) and len(plano2["elementos"]) == 7
    assert "PLA-R03-N01-P01" in {u["codigo_completo"] for u in plano2["ubicaciones"]}

    # Un rack con stock no puede eliminarse; sin stock, sus ubicaciones se desactivan (no se borran).
    p = base["producto"]("PLA1", "Producto Plano")
    pos = next(u for u in plano2["ubicaciones"] if u["codigo_completo"] == "PLA-R01-N02-P03")
    e = api.post("/documentos", {"clase": "INGRESO", "motivo_id": base["motivos"][("INGRESO", "ACTUALIZACION_STOCK")],
                                 "bodega_id": bod["id"], "confirmar": True, "fecha": "2026-08-01T10:00:00", "detalles": [{
                                     "producto_id": p["id"], "cantidad": 1, "unidad_id": base["u"]["bidon"], "precio_unitario": 120000,
                                     "ubicacion_id": pos["id"]}]}, espera=201)["existencias"][0]
    sin_r01 = [x for x in plano2["elementos"] if x["nombre"] != "R01"]
    assert api.put(f"/bodegas/{bod['id']}/plano", {"elementos": sin_r01}, espera=409)["codigo"] == "CON_STOCK"
    sin_r02 = [x for x in plano2["elementos"] if x["nombre"] != "R02"]
    plano3 = api.put(f"/bodegas/{bod['id']}/plano", {"elementos": sin_r02})
    assert "PLA-R02" not in {u["codigo_completo"] for u in plano3["ubicaciones"]}
    assert len(api.get("/ubicaciones", bodega_id=bod["id"], activo=False)) == 7
    fuera = [dict(sin_r02[0], x=500)] + sin_r02[1:]
    assert api.put(f"/bodegas/{bod['id']}/plano", {"elementos": fuera}, espera=400)["codigo"] == "FUERA_DE_PLANO"
    api.put(f"/bodegas/{bod['id']}/plano", {"elementos": sin_r02}, espera=403, como="digitador")

    # Datos para el visor: ocupacion por ubicacion y contenido al hacer clic.
    ocup = api.get(f"/bodegas/{bod['id']}/ocupacion")
    assert ocup == [{"ubicacion_id": pos["id"], "existencias": 1, "cantidad": 20, "valor": 120000,
                     "dias_antiguedad": ocup[0]["dias_antiguedad"], "dias_para_vencer": None, "ocupacion": None}]
    assert ocup[0]["dias_antiguedad"] >= 60
    assert api.get(f"/bodegas/{bod['id']}/ocupacion", como="digitador")[0]["valor"] is None
    contenido = api.get(f"/ubicaciones/{pos['id']}/contenido")
    assert contenido["existencias"][0]["codigo_publico"] == e["codigo_publico"] and contenido["valor"] == 120000
    assert contenido["existencias"][0]["producto"] == "Producto Plano" and contenido["existencias"][0]["lote"]
    rack = api.get(f"/ubicaciones/{r1['ubicacion_id']}/contenido")  # clic en el rack: suma sus posiciones
    assert rack["cantidad_total"] == 20 and rack["capacidad_disponible"] is None
    api.put(f"/ubicaciones/{pos['id']}", {"capacidad": 60})
    assert api.get(f"/ubicaciones/{pos['id']}/contenido")["capacidad_disponible"] == 40
    assert api.get(f"/bodegas/{bod['id']}/ocupacion")[0]["ocupacion"] == pytest.approx(1 / 3)
    api.put(f"/ubicaciones/{pos['id']}", {"activo": False}, espera=409)
