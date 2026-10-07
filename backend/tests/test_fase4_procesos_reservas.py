"""Fase 4: procesos, costo total, base de costeo, costo por kilo, reservas y stock comprometido."""
from datetime import timedelta

import pytest

from app.core.util import ahora
from app.modelos import ReservaStock
from app.servicios.alertas import evaluar_reglas

from .test_fase2_lotes_inventario import invariante_libro

F1, F2 = "2026-09-01T10:00:00", "2026-09-02T10:00:00"


def consumir(api, proceso, existencia, cantidad, espera=201, como="admin", **extra):
    return api.post("/consumos", {"proceso_id": proceso["id"], "existencia_id": existencia["id"], "cantidad": cantidad,
                                  "confirmar_fifo": True, **extra}, espera=espera, como=como)


def abrir(api, **datos):
    p = api.crear("/procesos", datos)
    return api.post(f"/procesos/{p['id']}/abrir", espera=200)


def test_ciclo_de_vida_y_costo_del_proceso(api, base):
    """Ejemplo del requerimiento: $85.000 + $42.500 + $22.500 = $150.000; 30.000 kg -> $5/kg."""
    a = base["producto"]("FUNA", "Fungicida A")
    b = base["producto"]("DESB", "Desinfectante B")
    c = base["producto"]("PROC", "Producto C")
    ea = base["ingreso"](a["id"], precio=170000, fecha=F1)["existencias"][0]   # $8.500/L
    eb = base["ingreso"](b["id"], precio=85000, fecha=F1)["existencias"][0]    # $4.250/L
    ec = base["ingreso"](c["id"], precio=45000, fecha=F1)["existencias"][0]    # $2.250/L

    p = api.crear("/procesos", {"codigo": "PROC-000125", "especie": "Cereza", "variedad": "Lapins", "productor": "Agricola Sur",
                                "kilos_procesados": 30000, "kilos_recepcionados": 32000})
    assert p["estado"] == "BORRADOR" and p["estado_kilos"] == "PROVISORIO" and p["temporada_id"]
    assert consumir(api, p, ea, 1, espera=409)["codigo"] == "PROCESO_NO_ABIERTO"
    p = api.post(f"/procesos/{p['id']}/abrir", espera=200)
    assert p["estado"] == "ABIERTO" and p["abierto_por_nombre"] == "Admin"
    api.post(f"/procesos/{p['id']}/abrir", espera=409)

    consumir(api, p, ea, 10)
    consumir(api, p, eb, 10)
    consumir(api, p, ec, 10)
    d = api.get(f"/procesos/{p['id']}")
    assert d["costo_total"] == 150000 and d["kilos_base"] == 30000 and d["costo_por_kilo"] == 5
    assert d["base_costeo_efectiva"] == "kilos_procesados" and d["costos"]["estado_kilos"] == "PROVISORIO"
    assert [(x["producto"], x["costo"]) for x in d["costos"]["por_producto"]] == [
        ("Fungicida A", 85000), ("Desinfectante B", 42500), ("Producto C", 22500)]
    assert d["costos"]["por_familia"] == [{"familia": "Fitosanitarios", "costo": 150000, "costo_por_kilo": 5}]
    filas = api.get(f"/procesos/{p['id']}/consumos")
    assert len(filas) == 3 and {f["codigo_publico"] for f in filas} == {ea["codigo_publico"], eb["codigo_publico"], ec["codigo_publico"]}
    assert all(f["lote"] and f["usuario"] == "Admin" and f["bodega"] and f["ubicacion"] for f in filas)

    # Los kilos cambian mientras el proceso esta abierto; cada cambio queda auditado.
    d = api.put(f"/procesos/{p['id']}", {"kilos_procesados": 28450})
    assert d["costo_por_kilo"] == pytest.approx(150000 / 28450)
    cambio = d["cambios"][0]
    assert (cambio["campo"], cambio["origen"], cambio["usuario"]) == ("kilos_procesados", "MANUAL", "Admin")
    assert float(cambio["valor_anterior"]) == 30000 and float(cambio["valor_nuevo"]) == 28450

    # Una anulacion reduce el costo del proceso sin borrar el consumo.
    ultimo = api.get("/consumos/recientes", proceso_id=p["id"])[0]
    api.post(f"/movimientos/{ultimo['id']}/anular", {"motivo": "No se utilizo"}, espera=200)
    assert api.get(f"/procesos/{p['id']}")["costo_total"] == 127500

    cerrado = api.post(f"/procesos/{p['id']}/cerrar", {}, espera=200)
    assert cerrado["estado"] == "CERRADO" and cerrado["estado_kilos"] == "DEFINITIVO" and cerrado["kilos_definitivos"] == 28450
    assert cerrado["modo_cierre"] == "MANUAL" and cerrado["cerrado_sincronizado"] is None  # proceso sin origen externo
    assert cerrado["cerrado_por_nombre"] == "Admin" and cerrado["cerrado_en"]
    assert consumir(api, p, ea, 1, espera=409)["codigo"] == "PROCESO_NO_ABIERTO"
    api.put(f"/procesos/{p['id']}", {"kilos_procesados": 1}, espera=409)
    api.post(f"/movimientos/{api.get('/consumos/recientes', proceso_id=p['id'])[1]['id']}/anular", {"motivo": "x"}, espera=409)

    api.post(f"/procesos/{p['id']}/reabrir", {"motivo": "Faltaba un consumo"}, espera=403, como="digitador")
    reabierto = api.post(f"/procesos/{p['id']}/reabrir", {"motivo": "Faltaba un consumo"}, espera=200)
    assert reabierto["estado"] == "ABIERTO" and reabierto["estado_kilos"] == "PROVISORIO"
    invariante_libro(api)


def test_base_de_costeo_configurable(api, base):
    x = base["producto"]("BASE1")
    e = base["ingreso"](x["id"], precio=200000, fecha=F1)["existencias"][0]  # $10.000/L
    p = abrir(api, codigo="PROC-BASE", kilos_recepcionados=50000, kilos_procesados=40000, kilos_producidos=36000,
              kilos_despachados=30000, datos_adicionales={"kilos_exportables": 25000})
    consumir(api, p, e, 10)  # $100.000
    esperado = {"kilos_procesados": 2.5, "kilos_recepcionados": 2.0, "kilos_despachados": 100000 / 30000, "extra.kilos_exportables": 4.0}
    for base_costeo, costo_kg in esperado.items():
        d = api.put(f"/procesos/{p['id']}", {"base_costeo": base_costeo})
        assert d["costo_por_kilo"] == pytest.approx(costo_kg), base_costeo
    api.put(f"/procesos/{p['id']}", {"base_costeo": "kilos_inventados"}, espera=400)
    # Sin base propia rige el parametro general; el predeterminado es kilos procesados.
    api.put(f"/procesos/{p['id']}", {"base_costeo": None})
    assert api.get(f"/procesos/{p['id']}")["base_costeo_efectiva"] == "kilos_procesados"
    api.put("/configuraciones/costeo.base_kilos", {"valor": "kilos_producidos"})
    d = api.get(f"/procesos/{p['id']}")
    assert d["base_costeo_nombre"] == "Kilos producidos" and d["costo_por_kilo"] == pytest.approx(100000 / 36000)
    # Al cerrar se congela la base usada: cambiar la configuracion despues no altera el costo historico.
    cerrado = api.post(f"/procesos/{p['id']}/cerrar", {}, espera=200)
    api.put("/configuraciones/costeo.base_kilos", {"valor": "kilos_procesados"})
    d = api.get(f"/procesos/{p['id']}")
    assert cerrado["kilos_definitivos"] == 36000 and d["costo_por_kilo"] == pytest.approx(100000 / 36000)


def test_cierre_manual_con_kilos_digitados_y_proceso_sin_kilos(api, base):
    p = abrir(api, codigo="PROC-SANIT", tipo="Sanitizacion")
    assert api.get(f"/procesos/{p['id']}")["costo_por_kilo"] is None  # sin kilos no hay division
    cerrado = api.post(f"/procesos/{p['id']}/cerrar", {"kilos": 1200, "observacion": "Kilos informados por jefe de turno"}, espera=200)
    assert cerrado["kilos_definitivos"] == 1200 and cerrado["kilos_procesados"] == 1200
    api.post(f"/procesos/{p['id']}/cerrar", {}, espera=409)
    api.post("/procesos", {"codigo": "PROC-SANIT"}, espera=409)
    api.post("/procesos", {"codigo": "X"}, espera=403, como="lector")


def test_costeo_multidimensional(api, base):
    x = base["producto"]("MULT1", "Fungicida Multi")
    e = base["ingreso"](x["id"], cantidad=5, precio=200000, fecha=F1)["existencias"]  # $10.000/L
    p1 = abrir(api, codigo="PM-1", fecha="2026-09-07", especie="Arandano", variedad="Duke", productor="Prod Uno",
               exportadora="Expo A", kilos_procesados=10000)
    p2 = abrir(api, codigo="PM-2", fecha="2026-09-15", especie="Arandano", variedad="Legacy", productor="Prod Dos",
               exportadora="Expo A", kilos_procesados=30000)
    p3 = abrir(api, codigo="PM-3", fecha="2026-10-01", especie="Kiwi", variedad="Hayward", productor="Prod Uno",
               exportadora="Expo B", kilos_procesados=5000)
    consumir(api, p1, e[0], 4)   # $40.000
    consumir(api, p2, e[1], 6)   # $60.000
    consumir(api, p3, e[2], 2)   # $20.000

    def analisis(dimension, **f):
        return {r["clave"]: r for r in api.get("/costos", dimension=dimension, **f) if r["clave"] in claves}

    claves = {"Arandano", "Kiwi"}
    esp = analisis("especie")
    assert (esp["Arandano"]["costo"], esp["Arandano"]["kilos"], esp["Arandano"]["costo_por_kilo"]) == (100000, 40000, 2.5)
    assert esp["Kiwi"]["costo_por_kilo"] == 4 and esp["Kiwi"]["estado_kilos"] == "PROVISORIO"
    claves = {"Prod Uno", "Prod Dos"}
    prod = analisis("productor")
    assert prod["Prod Uno"]["costo"] == 60000 and prod["Prod Uno"]["procesos"] == 2 and prod["Prod Dos"]["costo_por_kilo"] == 2
    claves = {"PM-1", "PM-2", "PM-3"}
    assert analisis("proceso")["PM-2"]["costo_por_kilo"] == 2
    claves = {"2026-09", "2026-10"}
    mes = analisis("mes", productor="Prod Uno")
    assert mes["2026-09"]["costo"] == 40000 and mes["2026-10"]["costo"] == 20000
    claves = {"Fungicida Multi"}
    assert analisis("producto", especie="Arandano")["Fungicida Multi"]["costo"] == 100000
    for dimension in ("variedad", "exportadora", "temporada", "semana", "familia", "subfamilia", "bodega", "lote_productivo"):
        assert api.get("/costos", dimension=dimension)
    api.get("/costos", espera=400, dimension="color")
    api.get("/costos", espera=403, como="digitador", dimension="especie")
    api.post(f"/procesos/{p3['id']}/cerrar", {}, espera=200)
    claves = {"Kiwi"}
    assert analisis("especie")["Kiwi"]["estado_kilos"] == "DEFINITIVO"


# ---------------------------------------------------------------- reservas

def test_reserva_no_descuenta_y_distingue_fisico_reservado_disponible(api, base):
    x = base["producto"]("RSV1", "Fungicida Reserva")
    e = base["ingreso"](x["id"], cantidad=2, fecha=F1)["existencias"]  # 40 L
    p = abrir(api, codigo="PROC-RSV1")
    r = api.crear("/reservas", {"producto_id": x["id"], "cantidad": 20, "proceso_id": p["id"], "area": "Packing",
                                "motivo": "Aplicacion programada", "documento_referencia": "OT-55"})
    assert r["estado"] == "ACTIVA" and r["pendiente"] == 20 and r["proceso"] == "PROC-RSV1" and r["numero"].startswith("RES-")
    fila = api.get("/stock", producto_id=x["id"])[0]
    assert (fila["stock_fisico"], fila["stock_reservado"], fila["stock_disponible"], fila["stock_comprometido"]) == (40, 20, 20, 20)
    # Reservar no genera movimiento: la salida fisica ocurre solo con el consumo.
    assert [m["tipo"] for m in api.get("/movimientos", producto_id=x["id"])["items"]] == ["INGRESO", "INGRESO"]
    assert api.get("/reservas/disponibilidad", producto_id=x["id"])["stock_disponible"] == 20

    # No se puede reservar mas que el disponible.
    exceso = api.post("/reservas", {"producto_id": x["id"], "cantidad": 21}, espera=409)
    assert exceso["codigo"] == "SIN_DISPONIBLE" and exceso["datos"]["stock_disponible"] == 20
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 0}, espera=400)
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 1}, espera=403, como="lector")

    # Otro proceso no puede consumir lo reservado...
    otro = abrir(api, codigo="PROC-RSV2")
    consumir(api, otro, e[0], 20)
    bloqueado = consumir(api, otro, e[1], 5, espera=409)
    assert bloqueado["codigo"] == "STOCK_RESERVADO" and bloqueado["datos"] == {"disponible": 0, "fisico": 20}
    # ...pero el proceso dueno de la reserva si, y su consumo la reduce (sin doble descuento).
    consumir(api, p, e[1], 8)
    r = api.get("/reservas", proceso_id=p["id"])["items"][0]
    assert (r["estado"], r["cantidad_consumida"], r["pendiente"]) == ("ACTIVA", 8, 12)
    fila = api.get("/stock", producto_id=x["id"])[0]
    assert (fila["stock_fisico"], fila["stock_reservado"], fila["stock_disponible"]) == (12, 12, 0)
    consumir(api, p, e[1], 12)
    r = api.get("/reservas", proceso_id=p["id"])["items"][0]
    assert r["estado"] == "CONSUMIDA" and r["pendiente"] == 0 and r["fecha_cierre"]
    invariante_libro(api)


def test_anular_consumo_devuelve_la_reserva(api, base):
    x = base["producto"]("RSV2")
    e = base["ingreso"](x["id"], fecha=F1)["existencias"][0]
    p = abrir(api, codigo="PROC-RSV3")
    api.crear("/reservas", {"producto_id": x["id"], "cantidad": 10, "proceso_id": p["id"]})
    m = consumir(api, p, e, 10)["movimiento"]
    assert api.get("/reservas", proceso_id=p["id"])["items"][0]["estado"] == "CONSUMIDA"
    api.post(f"/movimientos/{m['id']}/anular", {"motivo": "Error"}, espera=200)
    r = api.get("/reservas", proceso_id=p["id"])["items"][0]
    assert (r["estado"], r["cantidad_consumida"]) == ("ACTIVA", 0)


def test_reserva_por_bodega_lote_y_existencia(api, base):
    x = base["producto"]("RSV3")
    fit = base["ingreso"](x["id"], fecha=F1)["existencias"][0]
    man = base["ingreso"](x["id"], fecha=F2, bodega_id=base["bodega2"]["id"], ubicacion=None)["existencias"][0]
    api.crear("/reservas", {"producto_id": x["id"], "cantidad": 15, "bodega_id": base["bodega"]["id"]})
    por_bodega = {f["bodega"]: f for f in api.get("/stock", producto_id=x["id"], agrupar="bodega")}
    assert por_bodega["Bodega Fitosanitarios"]["stock_disponible"] == 5 and por_bodega["Bodega Mantencion"]["stock_disponible"] == 20
    assert api.post("/reservas", {"producto_id": x["id"], "cantidad": 6, "bodega_id": base["bodega"]["id"]}, espera=409)["codigo"] == "SIN_DISPONIBLE"
    # Reserva sobre una existencia concreta: hereda su bodega y lote.
    r = api.crear("/reservas", {"producto_id": x["id"], "cantidad": 20, "existencia_id": man["id"]})
    assert r["existencia"] == man["codigo_publico"] and r["lote"] == man["lote"] and r["bodega"] == "Bodega Mantencion"
    det = api.get(f"/existencias/{man['id']}")
    assert (det["cantidad_fisica"], det["cantidad_reservada"], det["cantidad_disponible"]) == (20, 20, 0)
    por_lote = {f["lote"]: f for f in api.get("/stock", producto_id=x["id"], agrupar="lote")}
    assert por_lote[man["lote"]]["stock_reservado"] == 20 and por_lote[fit["lote"]]["stock_reservado"] == 0
    assert api.get("/reservas/disponibilidad", producto_id=x["id"])["stock_disponible"] == 5
    assert len(api.get("/stock", producto_id=x["id"], agrupar="ubicacion")) == 2
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 1, "existencia_id": man["id"]}, espera=409)


def test_liberar_anular_y_exceder_con_permiso(api, base):
    x = base["producto"]("RSV4")
    base["ingreso"](x["id"], fecha=F1)
    r = api.crear("/reservas", {"producto_id": x["id"], "cantidad": 20})
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 5}, espera=409)
    liberada = api.post(f"/reservas/{r['id']}/liberar", {"motivo": "Se cancelo la aplicacion"}, espera=200)
    assert liberada["estado"] == "LIBERADA" and "cancelo" in liberada["observacion"]
    api.post(f"/reservas/{r['id']}/liberar", {}, espera=409)
    r2 = api.crear("/reservas", {"producto_id": x["id"], "cantidad": 20})  # el stock volvio al disponible
    assert api.post(f"/reservas/{r2['id']}/anular", {"motivo": "Duplicada"}, espera=200)["estado"] == "ANULADA"
    # Exceder el disponible exige configuracion explicita Y permiso especial.
    api.put("/configuraciones/reservas.permitir_exceder", {"valor": True})
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 50}, espera=409, como="jefe")  # sin el permiso
    assert api.crear("/reservas", {"producto_id": x["id"], "cantidad": 50})["estado"] == "ACTIVA"  # admin lo tiene
    api.put("/configuraciones/reservas.permitir_exceder", {"valor": False})
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 1}, espera=409)


def test_reserva_vencida_se_libera_y_genera_alerta(api, base):
    x = base["producto"]("RSV5", "Producto Reserva Vencida")
    base["ingreso"](x["id"], fecha=F1)
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 5, "fecha_vencimiento": "2020-01-01T00:00:00"}, espera=400)
    r = api.crear("/reservas", {"producto_id": x["id"], "cantidad": 12, "fecha_vencimiento": (ahora() + timedelta(days=1)).isoformat()})
    with api.sesion() as s:  # simula el paso del tiempo
        s.get(ReservaStock, r["id"]).fecha_vencimiento = ahora() - timedelta(minutes=5)
        s.commit()
    with api.sesion() as s, s.begin():
        evaluar_reglas(s, 1)
    assert api.get("/reservas", producto_id=x["id"])["items"][0]["estado"] == "VENCIDA"
    assert api.get("/stock", producto_id=x["id"])[0]["stock_disponible"] == 20
    alertas = api.get("/alertas", tipo="RESERVA_VENCIDA")["items"]
    assert any(a["entidad_id"] == r["id"] and "12 L" in a["descripcion"] for a in alertas)


def test_cerrar_proceso_libera_sus_reservas(api, base):
    x = base["producto"]("RSV6")
    base["ingreso"](x["id"], fecha=F1)
    p = abrir(api, codigo="PROC-RSV6")
    api.crear("/reservas", {"producto_id": x["id"], "cantidad": 10, "proceso_id": p["id"]})
    assert api.get(f"/procesos/{p['id']}")["reservas_activas"] == 1
    api.post(f"/procesos/{p['id']}/cerrar", {}, espera=200)
    assert api.get("/reservas", proceso_id=p["id"])["items"][0]["estado"] == "LIBERADA"
    api.post("/reservas", {"producto_id": x["id"], "cantidad": 1, "proceso_id": p["id"]}, espera=409)


def test_borrador_de_salida_cuenta_como_comprometido(api, base):
    x = base["producto"]("COMP1")
    e = base["ingreso"](x["id"], fecha=F1)["existencias"][0]
    api.crear("/documentos", {"clase": "SALIDA", "motivo_id": base["motivos"][("SALIDA", "MERMA")], "bodega_id": base["bodega"]["id"],
                              "detalles": [{"existencia_id": e["id"], "cantidad": 7}]})
    fila = api.get("/stock", producto_id=x["id"])[0]
    assert (fila["stock_fisico"], fila["stock_reservado"], fila["stock_comprometido"], fila["stock_disponible"]) == (20, 0, 7, 20)
