"""Modo Demo: los datos ficticios se generan con las reglas reales y permiten recorrer el escenario comercial completo."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.main import crear_app
from app.modelos import Base, Existencia, MovimientoInventario
from app.semilla.demo import CLAVE_DEMO, crear_demo
from app.servicios import inventario as svc_inv

from .conftest import _DIR, Api


class ApiDemo(Api):
    def token(self, usuario: str) -> str:
        if usuario not in self._tokens:
            r = self.c.post("/api/auth/login", json={"usuario": usuario, "clave": CLAVE_DEMO})
            assert r.status_code == 200, r.text
            self._tokens[usuario] = r.json()["token"]
        return self._tokens[usuario]


@pytest.fixture(scope="module")
def demo():
    a = ajustes()
    a.url_bd = f"sqlite:///{(_DIR / 'demo_prueba.db').as_posix()}"
    nucleo_db.reiniciar_motor()
    svc_inv.limpiar_cache()
    Base.metadata.create_all(nucleo_db.motor())
    with nucleo_db.nueva_sesion() as s, s.begin():
        crear_demo(s)
    with TestClient(crear_app()) as cliente:
        yield ApiDemo(cliente)
    nucleo_db.reiniciar_motor()
    a.url_bd = ""


def test_contenido_del_demo(demo):
    cat = demo.get("/catalogos")
    assert {b["codigo"] for b in cat["bodegas"]} == {"FIT", "MAN"} and len(cat["familias"]) == 2 and len(cat["subfamilias"]) == 7
    assert demo.get("/productos", tam=100)["total"] == 14 and demo.get("/lotes", tam=1)["total"] >= 12
    assert demo.get("/existencias", tam=1)["total"] >= 30 and demo.get("/movimientos", tam=1)["total"] >= 70
    estados = [p["estado"] for p in demo.get("/procesos", tam=100)["items"]]
    assert estados.count("CERRADO") == 6 and estados.count("ABIERTO") == 3
    assert demo.get("/reservas", estado="ACTIVA")["total"] == 2 and demo.get("/reservas", estado="VENCIDA")["total"] == 1
    tipos = demo.get("/alertas/resumen")["por_tipo"]
    assert {"STOCK_BAJO", "STOCK_CRITICO", "PRODUCTO_VENCIDO", "PROXIMO_A_VENCER", "STOCK_ANTIGUO", "CONSUMO_FUERA_FIFO", "LOTE_CUARENTENA",
            "PROCESO_SIN_SINCRONIZAR", "PRESTAMO_VENCIDO", "RESERVA_VENCIDA"} <= set(tipos)
    # Cuatro usuarios, uno por rol; el digitador opera sin ver costos.
    assert "costos:ver" not in demo.get("/auth/yo", como="bodega")["permisos"]
    assert demo.get("/dashboard", como="lector")["valor_total_inventario"] is None
    with demo.sesion() as s:  # el libro cuadra: saldo de cada existencia = suma de sus movimientos
        sumas = dict(s.execute(select(MovimientoInventario.existencia_id, func.sum(MovimientoInventario.cantidad)).group_by(MovimientoInventario.existencia_id)).all())
        assert all(sumas[e.id] == e.cantidad_fisica for e in s.scalars(select(Existencia)).unique())


def test_escenario_de_demostracion_completo(demo):
    """Los 26 pasos del guion comercial, de punta a punta por la API."""
    # 1-2. Entrar y ver el dashboard.
    d0 = demo.get("/dashboard")
    assert d0["valor_total_inventario"] > 0 and d0["alertas"]["abiertas"] > 0 and d0["costo_por_especie"]
    cat = demo.get("/catalogos")
    u = {x["codigo"]: x["id"] for x in cat["unidades"]}
    fit = next(b for b in cat["bodegas"] if b["codigo"] == "FIT")
    # 3-4. Ver una bodega en 2D / 3D.
    plano = demo.get(f"/bodegas/{fit['id']}/plano")
    assert sum(1 for e in plano["elementos"] if e["tipo"] == "RACK") == 5 and len(plano["ubicaciones"]) > 80
    assert demo.get(f"/bodegas/{fit['id']}/ocupacion")
    # 5-7. Crear familia, subfamilia y producto.
    fam = demo.crear("/familias", {"codigo": "EPP", "nombre": "Proteccion personal", "usa_lote": True, "granularidad": "POR_ENVASE", "estrategia_salida": "FIFO"})
    sub = demo.crear("/subfamilias", {"familia_id": fam["id"], "codigo": "GUAN", "nombre": "Guantes"})
    # 8. Configurar el lote.
    seg = [{"tipo": "SUBFAMILIA", "configuracion": {}}, {"tipo": "SEPARADOR", "configuracion": {"valor": "-"}},
           {"tipo": "FECHA", "configuracion": {"formato": "YYMMDD"}}, {"tipo": "SEPARADOR", "configuracion": {"valor": "-"}},
           {"tipo": "CORRELATIVO", "configuracion": {"largo": 3}}]
    assert not demo.post("/plantillas-lotes/vista-previa", {"segmentos": seg, "alcance": ["SUBFAMILIA"], "reinicio": "DIARIO"}, espera=200)["errores"]
    pl = demo.crear("/plantillas-lotes", {"codigo": "LOTE-EPP", "nombre": "Lote EPP", "segmentos": seg, "alcance": ["SUBFAMILIA"], "reinicio": "DIARIO"})
    demo.post(f"/plantillas-lotes/{pl['id']}/activar", espera=200)
    demo.put(f"/subfamilias/{sub['id']}", {"plantilla_lote_id": pl["id"]})
    prod = demo.crear("/productos", {"codigo": "GUA-NIT", "nombre": "Guante de nitrilo", "subfamilia_id": sub["id"], "unidad_base_id": u["un"], "stock_minimo": 100})
    demo.crear("/conversiones", {"producto_id": prod["id"], "unidad_origen_id": u["caja"], "unidad_destino_id": u["un"], "factor": 100})
    demo.put(f"/productos/{prod['id']}", {"unidad_compra_id": u["caja"]})
    # 9-12. Registrar ingreso con costo unitario: genera lote y existencias.
    ubic = {x["codigo_completo"]: x["id"] for x in demo.get("/ubicaciones", bodega_id=fit["id"], almacenable=True)}
    motivos = {(m["clase"], m["codigo"]): m["id"] for m in cat["motivos"]}
    doc = demo.crear("/documentos", {"clase": "INGRESO", "motivo_id": motivos[("INGRESO", "COMPRA")], "tipo_documento": "FACTURA", "numero_documento": "F-9001",
                                     "bodega_id": fit["id"], "confirmar": True, "detalles": [{"producto_id": prod["id"], "cantidad": 3, "unidad_id": u["caja"],
                                                                                         "precio_unitario": 12000, "ubicacion_id": ubic["FIT-R05-N01-P01"]}]})
    assert doc["detalles"][0]["lote"].startswith("GUAN-") and doc["detalles"][0]["costo_unitario_base"] == 120 and len(doc["existencias"]) == 3
    # 13. Imprimir QR.
    ids = ",".join(str(e["id"]) for e in doc["existencias"])
    assert demo.get("/etiquetas", existencias=ids).content[:4] == b"%PDF"
    # 14. Ver stock.
    assert demo.get("/stock", producto_id=prod["id"])[0]["stock_fisico"] == 300
    # 15. Reservar stock.
    abierto = next(p for p in demo.get("/procesos", estado="ABIERTO")["items"] if p["codigo"] == "PK-1008")
    demo.crear("/reservas", {"producto_id": prod["id"], "cantidad": 120, "proceso_id": abierto["id"], "motivo": "Turno tarde"})
    fila = demo.get("/stock", producto_id=prod["id"])[0]
    assert (fila["stock_fisico"], fila["stock_reservado"], fila["stock_disponible"]) == (300, 120, 180)
    # 16. Abrir proceso: importar desde la base productiva simulada.
    fuente = demo.get("/integraciones/fuentes")[0]
    pendientes = [d["id_externo"] for d in demo.get(f"/integraciones/fuentes/{fuente['id']}/disponibles") if not d["importado"]]
    assert pendientes == ["1010", "1009"] or set(pendientes) == {"1009", "1010"}
    imp = demo.post(f"/integraciones/fuentes/{fuente['id']}/importar", {"ids": ["1009"], "abrir": True}, espera=200)
    assert imp["importados"][0]["codigo"] == "PK-1009"
    # 17-18. Escanear el QR de la existencia mas nueva del fungicida: advertencia FIFO.
    fungicida = next(p for p in demo.get("/productos", q="FUNG-001")["items"])
    ex = demo.get("/existencias", producto_id=fungicida["id"])["items"]  # ordenadas por fecha de ingreso
    vieja, nueva = ex[0], ex[-1]
    token = demo.get(f"/existencias/{nueva['id']}")["token_qr"]
    ficha = demo.get("/consumo/escanear", codigo=f"http://localhost:8000/q/{token}", proceso_id=abierto["id"], como="bodega")
    assert ficha["fifo"]["existencia_id"] == vieja["id"] and "más antiguo" in ficha["fifo"]["mensaje"] and ficha["costo_unitario"] is None
    assert demo.post("/consumos", {"proceso_id": abierto["id"], "existencia_id": nueva["id"], "cantidad": 3}, espera=409, como="bodega")["codigo"] == "FIFO_ADVERTENCIA"
    # 19. Consumir.
    antes = demo.get(f"/procesos/{abierto['id']}")["costo_total"]
    r = demo.post("/consumos", {"proceso_id": abierto["id"], "existencia_id": nueva["id"], "cantidad": 3, "confirmar_fifo": True,
                                "clave_idempotencia": "demo-paso-19"}, espera=201, como="bodega")
    assert r["fuera_de_orden"] is True
    demo.post("/consumos", {"proceso_id": abierto["id"], "existencia_id": doc["existencias"][0]["id"], "cantidad": 40}, espera=201, como="bodega")
    assert demo.get("/reservas", proceso_id=abierto["id"], producto_id=prod["id"])["items"][0]["cantidad_consumida"] == 40
    # 20-21. Costo del proceso y costo por kilo (kilos provisorios).
    p = demo.get(f"/procesos/{abierto['id']}")
    assert p["costo_total"] == antes + 3 * 9500 + 40 * 120 and p["kilos_base"] == 5000 and p["costos"]["estado_kilos"] == "PROVISORIO"
    assert p["costo_por_kilo"] == pytest.approx(p["costo_total"] / 5000)
    # 22. Sincronizar: produccion avanzo de 5.000 a 15.000 kg.
    s = demo.post(f"/procesos/{abierto['id']}/actualizar", espera=200)
    assert s["kilos_procesados"] == 15000 and s["sincronizacion"]["cambios"] >= 1
    assert any(c["campo"] == "kilos_procesados" and float(c["valor_anterior"]) == 5000 for c in s["cambios"])
    # 23. Cerrar (actualizar y cerrar).
    c = demo.post(f"/procesos/{abierto['id']}/cerrar", {"actualizar": True}, espera=200)
    assert c["estado"] == "CERRADO" and c["kilos_definitivos"] == 15000 and c["cerrado_sincronizado"] is True
    assert c["costo_por_kilo"] == pytest.approx(c["costo_total"] / 15000)
    assert demo.get("/reservas", proceso_id=abierto["id"], producto_id=prod["id"])["items"][0]["estado"] == "LIBERADA"
    # 24. Dashboard actualizado.
    d1 = demo.get("/dashboard")
    assert d1["consumo_del_dia"]["costo"] == d0["consumo_del_dia"]["costo"] + 3 * 9500 + 40 * 120
    assert d1["valor_total_inventario"] == pytest.approx(d0["valor_total_inventario"] + 36000 - 3 * 9500 - 40 * 120)
    # 25. Alertas.
    demo.post("/alertas/evaluar", espera=200)
    assert any(a["tipo"] == "CONSUMO_FUERA_FIFO" and a["entidad_id"] == r["movimiento"]["id"] for a in demo.get("/alertas", tipo="CONSUMO_FUERA_FIFO")["items"])
    # 26. Trazabilidad completa en ambos sentidos.
    t = demo.get(f"/trazabilidad/lote/{doc['detalles'][0]['lote_id']}")
    assert t["resumen"] == {"documento": 1, "lote": 1, "existencia": 3, "movimiento": 4, "proceso": 1}
    atras = demo.get(f"/trazabilidad/proceso/{abierto['id']}")
    assert atras["resumen"]["documento"] >= 3 and {"Guante de nitrilo", "Fungicida Fludioxonil 230 SC"} <= {x["producto"] for x in atras["productos"]}
