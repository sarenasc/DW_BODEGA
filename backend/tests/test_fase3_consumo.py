"""Fase 3: consumo rapido, FIFO / FEFO, costo exacto, idempotencia, anulaciones y concurrencia."""
import threading
from decimal import Decimal

import pytest

from app.core import db as nucleo_db
from app.core.errores import ErrorNegocio
from app.modelos import Existencia
from app.servicios import inventario as svc

from .test_fase2_lotes_inventario import invariante_libro

VIEJA, NUEVA = "2026-09-01T10:00:00", "2026-09-20T10:00:00"


@pytest.fixture(scope="module")
def proceso(api):
    p = api.crear("/procesos", {"codigo": "PROC-T3", "especie": "Cereza", "kilos_procesados": 30000})
    return api.post(f"/procesos/{p['id']}/abrir", espera=200)


def par(base, codigo, nombre=None, **producto):
    """Producto con dos existencias: A ingresada el 01-09 y B el 20-09."""
    p = base["producto"](codigo, nombre, **producto)
    a = base["ingreso"](p["id"], fecha=VIEJA, precio=160000)["existencias"][0]
    b = base["ingreso"](p["id"], fecha=NUEVA, precio=190000, ubicacion="FIT-R01-N02-P02")["existencias"][0]
    return p, a, b


def consumir(api, proceso, existencia, cantidad, espera=201, como="admin", **extra):
    return api.post("/consumos", {"proceso_id": proceso["id"], "existencia_id": existencia["id"], "cantidad": cantidad, **extra},
                    espera=espera, como=como)


def test_escaneo_entrega_ficha_y_advertencia(api, base, proceso):
    p, a, b = par(base, "ESC1", "Fungicida Escaneo")
    token = api.get(f"/existencias/{a['id']}")["token_qr"]
    ficha = api.get("/consumo/escanear", codigo=f"https://x/q/{token}", proceso_id=proceso["id"])
    assert ficha["producto"] == "Fungicida Escaneo" and ficha["cantidad_fisica"] == 20 and ficha["unidad"] == "L"
    assert ficha["lote"] and ficha["fecha_ingreso"].startswith("2026-09-01") and ficha["fifo"] is None and ficha["bloqueo"] is None
    nueva = api.get("/consumo/escanear", codigo=b["codigo_publico"], proceso_id=proceso["id"])
    f = nueva["fifo"]
    assert f["existencia_id"] == a["id"] and "más antiguo" in f["mensaje"]
    # La advertencia muestra producto, lote recomendado, fecha de ingreso, cantidad, bodega y ubicacion.
    assert f["producto"] == "Fungicida Escaneo" and f["lote"] == a["lote"] and f["fecha_ingreso"].startswith("2026-09-01")
    assert f["cantidad_disponible"] == 20 and f["bodega"] == "Bodega Fitosanitarios" and f["ubicacion"] == "FIT-R01-N01-P01"


def test_politica_solo_advertir(api, base, proceso):
    p, a, b = par(base, "ADV1")
    r = consumir(api, proceso, b, 4, espera=409)
    assert r["codigo"] == "FIFO_ADVERTENCIA" and r["datos"]["codigo_publico"] == a["codigo_publico"]
    assert api.get(f"/existencias/{b['id']}")["cantidad_fisica"] == 20  # nada se desconto
    ok = consumir(api, proceso, b, 4, confirmar_fifo=True)
    assert ok["fuera_de_orden"] is True and ok["existencia"]["cantidad_fisica"] == 16
    alertas = api.get("/alertas", tipo="CONSUMO_FUERA_FIFO")["items"]
    assert any(x["entidad_id"] == ok["movimiento"]["id"] for x in alertas)
    assert consumir(api, proceso, a, 4)["fuera_de_orden"] is False  # la mas antigua no advierte


def test_politica_bloquear_justificar_y_permiso(api, base, proceso):
    p, a, b = par(base, "BLO1", politica_fifo="BLOQUEAR")
    assert consumir(api, proceso, b, 1, espera=409, confirmar_fifo=True)["codigo"] == "FIFO_BLOQUEADO"
    consumir(api, proceso, a, 1)

    p, a, b = par(base, "JUS1", politica_fifo="JUSTIFICAR")
    assert consumir(api, proceso, b, 1, espera=409, confirmar_fifo=True)["codigo"] == "FIFO_JUSTIFICACION"
    assert consumir(api, proceso, b, 1, justificacion="Envase A inaccesible")["fuera_de_orden"] is True

    p, a, b = par(base, "PER1", politica_fifo="PERMISO")
    assert consumir(api, proceso, b, 1, espera=403, como="digitador", confirmar_fifo=True)["codigo"] == "FIFO_PERMISO"
    assert consumir(api, proceso, b, 1, como="jefe", confirmar_fifo=True)["fuera_de_orden"] is True
    excepciones = api.get("/reportes/excepciones_fifo")["filas"]
    assert {"JUSTIFICAR", "PERMISO"} <= {x["politica"] for x in excepciones}


def test_fifo_usa_fecha_de_ingreso_no_numero_de_lote(api, base, proceso):
    p = base["producto"]("FECH1")
    # Se registra primero el ingreso mas reciente: recibe el numero de lote MENOR.
    reciente = base["ingreso"](p["id"], fecha=NUEVA)["existencias"][0]
    antigua = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    assert int(reciente["lote"].split("-")[-1]) < int(antigua["lote"].split("-")[-1])
    r = consumir(api, proceso, reciente, 1, espera=409)
    assert r["codigo"] == "FIFO_ADVERTENCIA" and r["datos"]["existencia_id"] == antigua["id"]
    assert consumir(api, proceso, antigua, 1)["fuera_de_orden"] is False


def test_fefo_y_estrategia_combinada(api, base, proceso):
    p = base["producto"]("FEFO1", estrategia_salida="FEFO", usa_vencimiento=True)
    lejos = base["ingreso"](p["id"], fecha=VIEJA, fecha_vencimiento="2027-06-30")["existencias"][0]
    pronto = base["ingreso"](p["id"], fecha=NUEVA, fecha_vencimiento="2027-01-31")["existencias"][0]
    r = consumir(api, proceso, lejos, 1, espera=409)  # FIFO diria "lejos"; FEFO exige el que vence antes
    assert r["datos"]["existencia_id"] == pronto["id"] and "vencimiento" in r["datos"]["mensaje"]
    assert consumir(api, proceso, pronto, 1)["fuera_de_orden"] is False

    p = base["producto"]("FEFI1", estrategia_salida="FEFO_FIFO", usa_vencimiento=True)
    a = base["ingreso"](p["id"], fecha=VIEJA, fecha_vencimiento="2027-03-31")["existencias"][0]
    b = base["ingreso"](p["id"], fecha=NUEVA, fecha_vencimiento="2027-03-31")["existencias"][0]
    assert consumir(api, proceso, b, 1, espera=409)["datos"]["existencia_id"] == a["id"]  # mismo vencimiento: desempata el ingreso

    p, a, b = par(base, "SINR1", estrategia_salida="SIN_RECOMENDACION")
    assert consumir(api, proceso, b, 1)["fuera_de_orden"] is False


def test_tolerancia_mismo_dia_no_es_desviacion(api, base, proceso):
    p = base["producto"]("TOL1")
    a = base["ingreso"](p["id"], fecha="2026-09-10T08:00:00")["existencias"][0]
    b = base["ingreso"](p["id"], fecha="2026-09-10T17:00:00")["existencias"][0]
    assert consumir(api, proceso, b, 1)["fuera_de_orden"] is False
    assert a["id"] != b["id"]


def test_costo_exacto_de_la_existencia(api, base, proceso):
    p = base["producto"]("COS1")
    base["ingreso"](p["id"], fecha=VIEJA, precio=160000)  # A: 20 L a $8.000
    b = base["ingreso"](p["id"], fecha=NUEVA, precio=190000)["existencias"][0]  # B: 20 L a $9.500
    r = consumir(api, proceso, b, 5, confirmar_fifo=True)
    m = r["movimiento"]
    assert (m["cantidad"], m["costo_unitario"], m["costo_total"]) == (-5, 9500, -47500)  # no se promedia con A
    assert m["proceso"] == "PROC-T3" and m["lote"] == b["lote"] and m["usuario"] == "Admin"
    det = api.get(f"/existencias/{b['id']}")
    assert det["cantidad_fisica"] == 15 and det["valor_disponible"] == 142500 and det["costo_unitario"] == 9500


def test_ultima_salida_no_deja_residuo(api, base, proceso):
    p = base["producto"]("RES1")
    # 3 L por $100 en total: costo unitario periodico de $33,333333.
    e = base["ingreso"](p["id"], cantidad=3, precio=33.333333, unidad="L", bultos=1, fecha=VIEJA)["existencias"][0]
    costos = [consumir(api, proceso, e, 1)["movimiento"]["costo_total"] for _ in range(3)]
    movs = api.get("/movimientos", existencia_id=e["id"])["items"]
    assert round(sum(m["costo_total"] for m in movs), 2) == 0  # entradas y salidas cuadran exactamente
    assert costos == [-33.33, -33.33, -33.34]  # la ultima salida absorbe el remanente
    assert api.get(f"/existencias/{e['id']}")["estado"] == "AGOTADA"


def test_stock_insuficiente_y_cantidad_invalida(api, base, proceso):
    p = base["producto"]("INS1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    r = consumir(api, proceso, e, 25, espera=409)
    assert r["codigo"] == "STOCK_INSUFICIENTE" and r["datos"]["disponible"] == 20
    assert consumir(api, proceso, e, 0, espera=400)["codigo"] == "CANTIDAD"
    assert consumir(api, proceso, e, -3, espera=400)["codigo"] == "CANTIDAD"
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 20


def test_conversion_de_unidad_en_consumo(api, base, proceso):
    p = base["producto"]("UNI1")
    api.crear("/conversiones", {"unidad_origen_id": base["u"]["L"], "unidad_destino_id": base["u"]["ml"], "factor": 1000})
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    r = consumir(api, proceso, e, 500, unidad_id=base["u"]["ml"])
    assert r["movimiento"]["cantidad"] == -0.5 and r["existencia"]["cantidad_fisica"] == 19.5


def test_doble_envio_no_duplica(api, base, proceso):
    p = base["producto"]("IDE1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    primero = consumir(api, proceso, e, 4, clave_idempotencia="tel-123-abc")
    segundo = consumir(api, proceso, e, 4, clave_idempotencia="tel-123-abc")  # reintento por mala senal
    assert primero["duplicado"] is False and segundo["duplicado"] is True
    assert segundo["movimiento"]["id"] == primero["movimiento"]["id"]
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 16
    assert len([m for m in api.get("/movimientos", existencia_id=e["id"])["items"] if m["tipo"] == "CONSUMO"]) == 1


def test_proceso_debe_estar_abierto(api, base):
    p = base["producto"]("ABI1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    borrador = api.crear("/procesos", {"codigo": "PROC-BORR"})
    assert consumir(api, borrador, e, 1, espera=409)["codigo"] == "PROCESO_NO_ABIERTO"
    r = api.post("/consumos", {"existencia_id": e["id"], "cantidad": 1}, espera=400)
    assert r["codigo"] == "PROCESO_REQUERIDO"
    # Otros motivos de salida configurables no exigen proceso.
    merma = api.post("/consumos", {"existencia_id": e["id"], "cantidad": 1, "motivo_codigo": "MERMA"}, espera=201)
    assert merma["movimiento"]["tipo"] == "MERMA" and merma["movimiento"]["proceso_id"] is None


def test_ultimos_consumos_y_anulacion_por_movimiento_inverso(api, base, proceso):
    p = base["producto"]("ANC1", "Desinfectante B")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    m = consumir(api, proceso, e, 3, como="digitador")["movimiento"]
    assert m["costo_total"] is None  # el digitador opera sin ver costos
    recientes = api.get("/consumos/recientes", proceso_id=proceso["id"], como="digitador")
    assert recientes[0]["id"] == m["id"] and recientes[0]["producto"] == "Desinfectante B" and recientes[0]["cantidad"] == -3
    assert recientes[0]["puede_anular"] is False
    api.post(f"/movimientos/{m['id']}/anular", {"motivo": "error"}, espera=403, como="digitador")
    api.post(f"/movimientos/{m['id']}/anular", {"motivo": " "}, espera=400, como="jefe")
    inverso = api.post(f"/movimientos/{m['id']}/anular", {"motivo": "Cantidad mal digitada"}, espera=200, como="jefe")
    assert inverso["tipo"] == "ANULACION" and inverso["cantidad"] == 3 and inverso["movimiento_anulado_id"] == m["id"]
    assert inverso["proceso_id"] == proceso["id"] and inverso["costo_total"] == 25500
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 20
    movs = api.get("/movimientos", existencia_id=e["id"])["items"]
    assert [x["tipo"] for x in movs] == ["ANULACION", "CONSUMO", "INGRESO"]  # el original sigue en el libro
    assert next(x for x in movs if x["id"] == m["id"])["anulado"] is True
    api.post(f"/movimientos/{m['id']}/anular", {"motivo": "otra vez"}, espera=409, como="jefe")
    assert any(a["accion"] == "ANULAR" for a in api.get("/auditoria", entidad="movimiento", entidad_id=str(m["id"]))["items"])
    invariante_libro(api)


def test_lote_bloqueado_cuarentena_y_vencido(api, base, proceso):
    p = base["producto"]("BLQ1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    api.post(f"/lotes/{e['lote_id']}/estado", {"estado": "BLOQUEADO", "motivo": "Retencion de calidad"}, espera=200, como="jefe")
    assert consumir(api, proceso, e, 1, espera=403, como="digitador")["codigo"] == "LOTE_BLOQUEADO"
    assert api.get("/consumo/escanear", codigo=e["codigo_publico"], como="digitador")["bloqueo"]["codigo"] == "LOTE_BLOQUEADO"
    assert consumir(api, proceso, e, 1, como="jefe")["avisos"]  # permiso especial: se permite y se avisa
    api.post(f"/lotes/{e['lote_id']}/estado", {"estado": "CUARENTENA", "motivo": "Analisis"}, espera=200)
    assert consumir(api, proceso, e, 1, espera=403, como="digitador")["codigo"] == "LOTE_BLOQUEADO"
    api.post(f"/lotes/{e['lote_id']}/estado", {"estado": "DISPONIBLE", "motivo": "Liberado"}, espera=200)
    consumir(api, proceso, e, 1, como="digitador")
    api.post(f"/lotes/{e['lote_id']}/estado", {"estado": "AGOTADO", "motivo": "x"}, espera=400)
    historial = [h["estado_nuevo"] for h in api.get(f"/lotes/{e['lote_id']}")["historial"]]
    assert historial == ["DISPONIBLE", "BLOQUEADO", "CUARENTENA", "DISPONIBLE"]

    v = base["producto"]("VENC1", usa_vencimiento=True)
    ev = base["ingreso"](v["id"], fecha=VIEJA, fecha_vencimiento="2026-09-30")["existencias"][0]
    assert consumir(api, proceso, ev, 1, espera=403, como="digitador")["codigo"] == "LOTE_VENCIDO"
    # Un lote bloqueado o vencido no cuenta como "mas antiguo disponible" para la advertencia FIFO.
    sano = base["ingreso"](v["id"], fecha=NUEVA, fecha_vencimiento="2027-09-30")["existencias"][0]
    assert consumir(api, proceso, sano, 1, como="digitador")["fuera_de_orden"] is False


def test_alcance_por_bodega_en_consumo(api, base, proceso):
    from .conftest import CLAVE
    p = base["producto"]("ALC1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    rol = next(r for r in api.get("/roles") if r["codigo"] == "DIGITADOR")
    api.crear("/usuarios", {"usuario": "solo_man", "nombre": "Solo Mantencion", "clave": CLAVE, "roles": [rol["id"]],
                            "todas_bodegas": False, "bodegas": [base["bodega2"]["id"]]})
    assert consumir(api, proceso, e, 1, espera=403, como="solo_man")["codigo"] == "SIN_PERMISO"
    api.get("/consumo/escanear", espera=403, como="solo_man", codigo=e["codigo_publico"])
    assert api.get("/existencias", producto_id=p["id"], como="solo_man")["total"] == 0


def test_consumo_concurrente_nunca_deja_stock_negativo(api, base, proceso):
    """Doce usuarios intentan consumir 3 L de la misma existencia de 20 L: solo seis pueden."""
    p = base["producto"]("RACE1")
    e = base["ingreso"](p["id"], fecha=VIEJA)["existencias"][0]
    ok, rechazados, otros = [], [], []
    barrera = threading.Barrier(12)

    def trabajo():
        barrera.wait()
        try:
            with nucleo_db.nueva_sesion() as s, s.begin():
                ex = s.get(Existencia, e["id"])
                m, _ = svc.registrar_salida(s, None, ex, Decimal(3), "CONSUMO")
                ok.append(m.id)
        except ErrorNegocio as err:
            rechazados.append(err.codigo)
        except Exception as err:  # noqa: BLE001
            otros.append(repr(err))

    hilos = [threading.Thread(target=trabajo) for _ in range(12)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    assert not otros, otros
    assert len(ok) == 6 and rechazados == ["STOCK_INSUFICIENTE"] * 6
    assert api.get(f"/existencias/{e['id']}")["cantidad_fisica"] == 2
    invariante_libro(api)
