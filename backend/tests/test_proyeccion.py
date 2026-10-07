"""Proyeccion de insumos por especie y rebaja por aseo / lavado de linea."""
import pytest

F = "2026-09-01T10:00:00"


@pytest.fixture(scope="module")
def historia(api, base):
    """Cereza: 2 procesos cerrados, 40.000 kg, 80 L de fungicida y 20 L de cera. Kiwi: 1 proceso, 10.000 kg, 5 L de fungicida."""
    fung = base["producto"]("PRY-FUNG", "Fungicida Proyeccion")
    cera = base["producto"]("PRY-CERA", "Cera Proyeccion")
    ef = base["ingreso"](fung["id"], cantidad=6, precio=200000, fecha=F)["existencias"]   # 120 L a $10.000
    ec = base["ingreso"](cera["id"], cantidad=2, precio=60000, fecha=F)["existencias"]    # 40 L a $3.000

    def proceso(codigo, especie, kilos, consumos, cerrar=True):
        p = api.crear("/procesos", {"codigo": codigo, "especie": especie, "kilos_procesados": kilos, "fecha": "2026-09-10"})
        api.post(f"/procesos/{p['id']}/abrir", espera=200)
        for existencia, cantidad in consumos:
            api.post("/consumos", {"proceso_id": p["id"], "existencia_id": existencia["id"], "cantidad": cantidad, "confirmar_fifo": True}, espera=201)
        if cerrar:
            api.post(f"/procesos/{p['id']}/cerrar", {}, espera=200)
        return p

    proceso("PRY-1", "Cereza", 10000, [(ef[0], 20), (ec[0], 20)])
    proceso("PRY-2", "Cereza", 30000, [(ef[1], 20), (ef[2], 20), (ef[3], 20)])   # no uso cera: baja el promedio
    proceso("PRY-3", "Kiwi", 10000, [(ef[4], 5)])
    proceso("PRY-4", "Cereza", 10000, [(ef[4], 10)], cerrar=False)
    return dict(fung=fung, cera=cera, ef=ef)


def test_historial_por_especie(api, historia):
    h = {x["especie"]: x for x in api.get("/proyeccion/historial")}
    assert (h["Cereza"]["procesos"], h["Cereza"]["kilos"], h["Cereza"]["costo"], h["Cereza"]["costo_por_kilo"]) == (2, 40000, 860000, 21.5)
    assert h["Kiwi"]["kilos"] == 10000 and h["Kiwi"]["productos"] == 1
    con_abiertos = {x["especie"]: x for x in api.get("/proyeccion/historial", solo_cerrados=False)}
    assert con_abiertos["Cereza"]["procesos"] == 3 and con_abiertos["Cereza"]["kilos"] == 50000
    assert api.get("/proyeccion/historial", como="digitador")[0]["costo_por_kilo"] is None


def test_receta_para_los_kilos_pendientes(api, historia):
    r = api.post("/proyeccion", {"pendientes": [{"especie": "Cereza", "kilos": 20000}, {"especie": "Kiwi", "kilos": 4000}]}, espera=200)
    p = {x["producto"]: x for x in r["productos"]}
    # Cereza: 80 L / 40.000 kg = 2 L por 1.000 kg -> 40 L. Kiwi: 0,5 L por 1.000 kg -> 2 L. Total 42 L.
    f = p["Fungicida Proyeccion"]
    assert f["cantidad_requerida"] == pytest.approx(42) and f["unidad"] == "L"
    assert f["stock_disponible"] == 25 and f["faltante"] == pytest.approx(17) and f["alcanza"] is False   # 120 - 95 consumidos
    assert f["costo_estimado"] == pytest.approx(420000) and f["cobertura"] == pytest.approx(25 / 42)
    # Cera: 20 L / 40.000 kg (se promedia tambien con el proceso que no la uso) -> 10 L; hay 20 L.
    c = p["Cera Proyeccion"]
    assert c["cantidad_requerida"] == pytest.approx(10) and c["faltante"] == 0 and c["alcanza"] is True
    d = {(x["especie"], x["producto"]): x for x in r["detalle"]}
    assert d[("Cereza", "Fungicida Proyeccion")]["por_1000_kg"] == pytest.approx(2)
    assert d[("Kiwi", "Fungicida Proyeccion")]["cantidad"] == pytest.approx(2)
    assert r["resumen"]["kilos_pendientes"] == 24000 and r["resumen"]["con_faltante"] == 1
    assert r["resumen"]["costo_estimado"] == pytest.approx(450000) and r["resumen"]["costo_por_kilo"] == pytest.approx(18.75)
    assert r["productos"][0]["producto"] == "Fungicida Proyeccion"  # primero lo que no alcanza


def test_reservas_y_casos_borde(api, historia):
    api.crear("/reservas", {"producto_id": historia["fung"]["id"], "cantidad": 15})
    f = api.post("/proyeccion", {"pendientes": [{"especie": "Cereza", "kilos": 10000}]}, espera=200)["productos"]
    fung = next(x for x in f if x["producto"] == "Fungicida Proyeccion")
    assert (fung["stock_fisico"], fung["stock_reservado"], fung["stock_disponible"]) == (25, 15, 10) and fung["faltante"] == pytest.approx(10)
    r = api.post("/proyeccion", {"pendientes": [{"especie": "Cereza", "kilos": 1000}, {"especie": "Mango", "kilos": 500}]}, espera=200)
    assert r["sin_historial"] == ["Mango"] and r["resumen"]["kilos_pendientes"] == 1000
    assert api.post("/proyeccion", {"pendientes": [{"especie": "Mango", "kilos": 500}]}, espera=400)["codigo"] == "SIN_HISTORIAL"
    api.post("/proyeccion", {"pendientes": [{"especie": "Cereza", "kilos": 0}]}, espera=422)
    sin = api.post("/proyeccion", {"pendientes": [{"especie": "Cereza", "kilos": 1000}]}, espera=200, como="digitador")
    assert sin["resumen"]["costo_estimado"] is None and sin["productos"][0]["cantidad_requerida"] > 0


def test_rebaja_por_aseo_de_linea(api, historia):
    """El aseo o lavado de linea es un tipo de rebaja propio: no exige proceso y no altera la receta por especie."""
    motivos = {m["codigo"]: m for m in api.get("/catalogos")["motivos"] if m["clase"] == "SALIDA"}
    assert motivos["ASEO_LINEA"]["nombre"] == "Aseo / lavado de linea" and motivos["ASEO_LINEA"]["requiere_proceso"] is False
    antes = {x["especie"]: x["costo"] for x in api.get("/proyeccion/historial")}
    e = historia["ef"][5]
    r = api.post("/consumos", {"existencia_id": e["id"], "cantidad": 3, "motivo_codigo": "ASEO_LINEA", "confirmar_fifo": True,
                               "observacion": "Lavado linea 1 fin de turno"}, espera=201)
    assert r["movimiento"]["tipo"] == "CONSUMO" and r["movimiento"]["proceso_id"] is None and r["movimiento"]["costo_total"] == -30000
    assert {x["especie"]: x["costo"] for x in api.get("/proyeccion/historial")} == antes
    fila = next(f for f in api.get("/reportes/consumos", producto_id=historia["fung"]["id"])["filas"] if f["id"] == r["movimiento"]["id"])
    assert fila["rebaja"] == "Aseo / lavado de linea" and fila["costo_total"] == 30000 and fila["proceso"] is None
