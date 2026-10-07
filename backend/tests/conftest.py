"""Entorno de pruebas: una base SQLite nueva por modulo, con datos base y cuatro usuarios (uno por rol)."""
import os
import tempfile
from datetime import date
from pathlib import Path

_DIR = Path(tempfile.mkdtemp(prefix="wms_pruebas_"))
os.environ.update(WMS_CLAVE_SECRETA="clave-de-pruebas-0123456789-abcdefghij", WMS_PLANIFICADOR="0",
                  WMS_DIR_INSTANCIA=str(_DIR), WMS_INTENTOS_LOGIN="10000", WMS_MODO_DEMO="0",
                  WMS_DIR_FRONTEND=str(_DIR / "sin_frontend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import db as nucleo_db  # noqa: E402
from app.core.config import ajustes  # noqa: E402
from app.core.seguridad import hash_clave  # noqa: E402
from app.main import crear_app  # noqa: E402
from app.modelos import Base, Empresa, Temporada, Usuario  # noqa: E402
from app.semilla.base import sembrar_base, sembrar_empresa  # noqa: E402
from app.servicios import inventario as svc_inv  # noqa: E402

CLAVE = "Prueba123"
_HASH = hash_clave(CLAVE)
_n = 0


class Api:
    """Cliente con sesion por usuario y verificacion del codigo HTTP esperado."""

    def __init__(self, cliente: TestClient):
        self.c = cliente
        self._tokens: dict[str, str] = {}

    def token(self, usuario: str) -> str:
        if usuario not in self._tokens:
            r = self.c.post("/api/auth/login", json={"usuario": usuario, "clave": CLAVE})
            assert r.status_code == 200, r.text
            self._tokens[usuario] = r.json()["token"]
        return self._tokens[usuario]

    def _llamar(self, metodo, ruta, espera, como, **kw):
        cab = {"Authorization": f"Bearer {self.token(como)}"} if como else {}
        r = self.c.request(metodo, "/api" + ruta, headers=cab, **kw)
        if espera is not None:
            assert r.status_code == espera, f"{metodo} {ruta} -> {r.status_code}: {r.text[:600]}"
        return r.json() if r.headers.get("content-type", "").startswith("application/json") else r

    def get(self, ruta, espera=200, como="admin", **params):
        return self._llamar("GET", ruta, espera, como, params={k: v for k, v in params.items() if v is not None})

    def post(self, ruta, datos=None, espera=None, como="admin"):
        r = self._llamar("POST", ruta, espera, como, json=datos or {})
        return r

    def put(self, ruta, datos=None, espera=200, como="admin"):
        return self._llamar("PUT", ruta, espera, como, json=datos or {})

    def delete(self, ruta, espera=200, como="admin"):
        return self._llamar("DELETE", ruta, espera, como)

    def crear(self, ruta, datos, como="admin"):
        return self._llamar("POST", ruta, 201, como, json=datos)

    def sesion(self):
        return nucleo_db.nueva_sesion()


@pytest.fixture(scope="module")
def api():
    global _n
    _n += 1
    a = ajustes()
    a.url_bd = f"sqlite:///{(_DIR / f'prueba_{_n}.db').as_posix()}"
    nucleo_db.reiniciar_motor()
    svc_inv.limpiar_cache()
    Base.metadata.create_all(nucleo_db.motor())
    with nucleo_db.nueva_sesion() as s, s.begin():
        sembrar_base(s)
        emp = Empresa(codigo="EMP", nombre="Empresa de Pruebas")
        s.add(emp)
        s.flush()
        roles = sembrar_empresa(s, emp)
        for usuario, rol in (("admin", "ADMINISTRADOR"), ("jefe", "JEFE_AREA"), ("digitador", "DIGITADOR"), ("lector", "LECTOR")):
            s.add(Usuario(empresa_id=emp.id, usuario=usuario, nombre=usuario.capitalize(), clave_hash=_HASH, roles=[roles[rol]]))
        s.add(Temporada(empresa_id=emp.id, codigo="2026-2027", nombre="Temporada 2026-2027", fecha_inicio=date(2026, 7, 1),
                        fecha_termino=date(2027, 6, 30), actual=True))
    with TestClient(crear_app()) as cliente:
        yield Api(cliente)
    nucleo_db.reiniciar_motor()
    a.url_bd = ""


class Base_:
    """Maestros minimos para las pruebas de inventario."""


@pytest.fixture(scope="module")
def base(api: Api):
    """Familia FITO > subfamilia FUNG con plantilla de lote, producto en litros comprado en bidones, bodega con rack."""
    cat = api.get("/catalogos")
    u = {x["codigo"]: x["id"] for x in cat["unidades"]}
    fam = api.crear("/familias", {"codigo": "FITO", "nombre": "Fitosanitarios", "usa_lote": True, "requiere_qr": True,
                                 "estrategia_salida": "FIFO", "politica_fifo": "ADVERTIR", "granularidad": "POR_ENVASE"})
    sub = api.crear("/subfamilias", {"familia_id": fam["id"], "codigo": "FUNG", "nombre": "Fungicidas"})
    pl = api.crear("/plantillas-lotes", {
        "codigo": "FITO", "nombre": "Lote fitosanitario", "modo": "AUTOMATICO", "alcance": ["SUBFAMILIA"], "reinicio": "ANUAL",
        "segmentos": [{"tipo": "SUBFAMILIA", "configuracion": {}}, {"tipo": "SEPARADOR", "configuracion": {"valor": "-"}},
                      {"tipo": "ANIO", "configuracion": {"digitos": 2}}, {"tipo": "SEPARADOR", "configuracion": {"valor": "-"}},
                      {"tipo": "CORRELATIVO", "configuracion": {"largo": 5}}]})
    api.post(f"/plantillas-lotes/{pl['id']}/activar", espera=200)
    api.put(f"/subfamilias/{sub['id']}", {"plantilla_lote_id": pl["id"]})
    prov = api.crear("/proveedores", {"codigo": "AGRO", "nombre": "Agroquimica Demo"})
    bod = api.crear("/bodegas", {"codigo": "FIT", "nombre": "Bodega Fitosanitarios", "largo": 20, "ancho": 12, "alto": 6})
    rack = api.crear(f"/bodegas/{bod['id']}/racks", {"codigo": "R01", "niveles": 2, "posiciones": 3})
    ubic = {x["codigo_completo"]: x["id"] for x in api.get("/ubicaciones", bodega_id=bod["id"])}
    bod2 = api.crear("/bodegas", {"codigo": "MAN", "nombre": "Bodega Mantencion"})
    datos = dict(u=u, familia=fam, subfamilia=sub, plantilla=pl, proveedor=prov, bodega=bod, bodega2=bod2, rack=rack,
                 ubic=ubic, motivos={(m["clase"], m["codigo"]): m["id"] for m in cat["motivos"]})

    def producto(codigo, nombre=None, **extra):
        p = api.crear("/productos", {"codigo": codigo, "nombre": nombre or f"Producto {codigo}", "subfamilia_id": sub["id"],
                                     "unidad_base_id": u["L"], **extra})
        api.crear("/conversiones", {"producto_id": p["id"], "unidad_origen_id": u["bidon"], "unidad_destino_id": u["L"], "factor": 20})
        api.put(f"/productos/{p['id']}", {"unidad_compra_id": u["bidon"]})
        return p

    def ingreso(producto_id, cantidad=1, precio=170000, unidad="bidon", fecha=None, ubicacion="FIT-R01-N01-P01", como="admin",
                espera=201, bodega_id=None, **linea):
        d = {"clase": "INGRESO", "motivo_id": datos["motivos"][("INGRESO", "COMPRA")], "tipo_documento": "FACTURA",
             "numero_documento": "F-1001", "proveedor_id": prov["id"], "bodega_id": bodega_id or bod["id"], "confirmar": True,
             "detalles": [{"producto_id": producto_id, "cantidad": cantidad, "unidad_id": u[unidad], "precio_unitario": precio,
                           "ubicacion_id": ubic.get(ubicacion) if ubicacion else None, **linea}]}
        if fecha:
            d["fecha"] = fecha
        return api.post("/documentos", d, espera=espera, como=como)

    datos.update(producto=producto, ingreso=ingreso)
    return datos
