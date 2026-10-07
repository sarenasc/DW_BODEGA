"""Fase 1: maestros parametrizables, herencia de configuracion, conversiones y ubicaciones."""
import pytest


def test_herencia_familia_subfamilia_producto(api, base):
    p = base["producto"]("HER1")
    pol = api.get(f"/productos/{p['id']}/detalle")["politica"]
    assert pol["usa_lote"] is True and pol["origen"]["usa_lote"] == "FAMILIA"
    assert pol["plantilla_lote_id"] == base["plantilla"]["id"] and pol["origen"]["plantilla_lote_id"] == "SUBFAMILIA"
    assert pol["usa_vencimiento"] is False and pol["origen"]["usa_vencimiento"] == "GLOBAL"
    # La subfamilia sobreescribe a la familia y el producto a la subfamilia.
    api.put(f"/subfamilias/{base['subfamilia']['id']}", {"usa_vencimiento": True})
    api.put(f"/productos/{p['id']}", {"usa_lote": False, "estrategia_salida": "FEFO"})
    pol = api.get(f"/productos/{p['id']}/detalle")["politica"]
    assert (pol["usa_lote"], pol["origen"]["usa_lote"]) == (False, "PRODUCTO")
    assert (pol["usa_vencimiento"], pol["origen"]["usa_vencimiento"]) == (True, "SUBFAMILIA")
    assert pol["estrategia_salida"] == "FEFO"
    # Volver a heredar: el valor nulo significa "heredar".
    api.put(f"/productos/{p['id']}", {"usa_lote": None})
    assert api.get(f"/productos/{p['id']}/detalle")["politica"]["origen"]["usa_lote"] == "FAMILIA"
    api.put(f"/subfamilias/{base['subfamilia']['id']}", {"usa_vencimiento": None})


def test_valores_de_politica_validados(api, base):
    api.put(f"/familias/{base['familia']['id']}", {"granularidad": "POR_CAJON"}, espera=400)
    api.put(f"/familias/{base['familia']['id']}", {"politica_fifo": "IGNORAR"}, espera=400)
    for g in ("POR_ENVASE", "POR_LOTE", "CONSOLIDADA", "UNIDAD_LOGISTICA"):
        api.put(f"/familias/{base['familia']['id']}", {"granularidad": g})
    api.put(f"/familias/{base['familia']['id']}", {"granularidad": "POR_ENVASE"})


def test_codigo_duplicado_rechazado(api, base):
    base["producto"]("DUP1")
    api.post("/productos", {"codigo": "dup1", "nombre": "Otro", "subfamilia_id": base["subfamilia"]["id"],
                            "unidad_base_id": base["u"]["L"]}, espera=409)


def test_conversion_por_producto_y_universal(api, base):
    u = base["u"]
    p = base["producto"]("CONV1")
    r = api.get(f"/productos/{p['id']}/convertir", cantidad=3, unidad_id=u["bidon"])
    assert r["cantidad_base"] == 60 and r["factor"] == 20
    # Conversion universal L <-> ml y encadenada bidon -> L -> ml.
    api.crear("/conversiones", {"unidad_origen_id": u["L"], "unidad_destino_id": u["ml"], "factor": 1000})
    assert api.get("/conversiones-calcular", cantidad=250, unidad_origen_id=u["ml"], unidad_destino_id=u["L"])["resultado"] == 0.25
    assert api.get("/conversiones-calcular", cantidad=1, unidad_origen_id=u["bidon"], unidad_destino_id=u["ml"],
                   producto_id=p["id"])["resultado"] == 20000
    # Otro producto puede tener un bidon de distinto contenido: la conversion no esta en el codigo.
    p2 = api.crear("/productos", {"codigo": "CONV2", "nombre": "Bidon de 5", "subfamilia_id": base["subfamilia"]["id"],
                                  "unidad_base_id": u["L"]})
    api.crear("/conversiones", {"producto_id": p2["id"], "unidad_origen_id": u["bidon"], "unidad_destino_id": u["L"], "factor": 5})
    assert api.get(f"/productos/{p2['id']}/convertir", cantidad=3, unidad_id=u["bidon"])["cantidad_base"] == 15


def test_conversion_inexistente_y_factor_invalido(api, base):
    u = base["u"]
    p = base["producto"]("CONV3")
    api.get(f"/productos/{p['id']}/convertir", espera=400, cantidad=1, unidad_id=u["saco"])
    api.post("/conversiones", {"producto_id": p["id"], "unidad_origen_id": u["saco"], "unidad_destino_id": u["L"], "factor": 0}, espera=400)
    api.post("/conversiones", {"producto_id": p["id"], "unidad_origen_id": u["L"], "unidad_destino_id": u["L"], "factor": 2}, espera=400)
    # No se puede fijar una unidad de compra sin conversion configurada.
    api.put(f"/productos/{p['id']}", {"unidad_compra_id": u["saco"]}, espera=400)


def test_rack_genera_ubicaciones_con_codigo_jerarquico(api, base):
    codigos = set(base["ubic"])
    assert {"FIT-R01", "FIT-R01-N01", "FIT-R01-N02-P03"} <= codigos and len(codigos) == 1 + 2 + 6
    posiciones = api.get("/ubicaciones", bodega_id=base["bodega"]["id"], almacenable=True)
    assert len(posiciones) == 6 and all(x["tipo"] == "POSICION" for x in posiciones)


def test_jerarquia_libre_y_codigo_unico(api, base):
    bod = base["bodega2"]["id"]
    pas = api.crear("/ubicaciones", {"bodega_id": bod, "codigo": "A", "tipo": "PASILLO", "almacenable": False})
    est = api.crear("/ubicaciones", {"bodega_id": bod, "codigo": "E1", "tipo": "ESTANTE", "padre_id": pas["id"]})
    assert est["codigo_completo"] == "MAN-A-E1" and est["nivel"] == 1
    api.post("/ubicaciones", {"bodega_id": bod, "codigo": "E1", "padre_id": pas["id"]}, espera=409)
    plana = api.crear("/ubicaciones", {"bodega_id": bod, "codigo": "PISO1"})  # la jerarquia no es obligatoria
    assert plana["codigo_completo"] == "MAN-PISO1"


def test_temporada_actual_unica(api):
    api.crear("/temporadas", {"codigo": "2027-2028", "nombre": "T 27-28", "fecha_inicio": "2027-07-01",
                              "fecha_termino": "2028-06-30", "actual": True})
    actuales = [t["codigo"] for t in api.get("/temporadas")["items"] if t["actual"]]
    assert actuales == ["2027-2028"]
    api.post("/temporadas", {"codigo": "MAL", "nombre": "x", "fecha_inicio": "2027-07-01", "fecha_termino": "2027-01-01"}, espera=400)
    vieja = next(t for t in api.get("/temporadas")["items"] if t["codigo"] == "2026-2027")
    api.put(f"/temporadas/{vieja['id']}", {"actual": True})


@pytest.mark.parametrize("ruta", ["/unidades", "/proveedores", "/tipos-bodega", "/motivos-movimiento", "/tipos-movimiento"])
def test_catalogos_listan(api, ruta):
    assert api.get(ruta)["total"] >= 0


def test_baja_logica_conserva_registro(api, base):
    p = base["producto"]("BAJA1")
    api.delete(f"/productos/{p['id']}")
    assert api.get(f"/productos/{p['id']}")["activo"] is False
    assert all(x["codigo"] != "BAJA1" for x in api.get("/productos", activo=True, tam=500)["items"])
