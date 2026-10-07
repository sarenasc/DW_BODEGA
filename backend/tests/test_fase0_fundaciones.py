"""Fase 0: instalacion, autenticacion, RBAC, alcance y auditoria."""
import shutil
import tempfile
from pathlib import Path

from sqlalchemy import inspect, select

from app.core import db as nucleo_db
from app.core.config import ajustes
from app.core.seguridad import cifrar, descifrar, hash_clave, token_qr, verificar_clave
from app.modelos import Empresa, Permiso, Usuario
from app.modulos.instalacion import DatosAdmin, DatosBD, DatosEmpresa, DatosInstalacion, instalar

from .conftest import CLAVE


def test_salud_y_estado(api):
    assert api.get("/salud", como=None)["instalado"] is True
    estado = api.get("/instalacion/estado", como=None)
    assert {m["codigo"] for m in estado["motores"]} == {"sqlserver", "postgresql", "mysql", "demo"}


def test_login_correcto_e_incorrecto(api):
    r = api.c.post("/api/auth/login", json={"usuario": "admin", "clave": CLAVE})
    assert r.status_code == 200 and r.json()["usuario"]["usuario"] == "admin"
    assert "wms_sesion" in r.cookies and "httponly" in r.headers["set-cookie"].lower()
    assert api.c.post("/api/auth/login", json={"usuario": "admin", "clave": "mala"}).status_code == 401
    assert api.c.post("/api/auth/login", json={"usuario": "noexiste", "clave": CLAVE}).status_code == 401


def test_sin_token_no_hay_acceso(api):
    assert api.c.get("/api/productos").status_code == 401
    assert api.c.get("/api/productos", headers={"Authorization": "Bearer falso"}).status_code == 401


def test_refresco_rota_la_sesion(api):
    r = api.c.post("/api/auth/login", json={"usuario": "lector", "clave": CLAVE})
    cookie = r.cookies["wms_sesion"]
    r2 = api.c.post("/api/auth/refrescar", cookies={"wms_sesion": cookie})
    assert r2.status_code == 200 and r2.json()["token"]
    nueva = r2.cookies["wms_sesion"]
    assert nueva != cookie
    # Dos pestanas renovando a la vez con la misma cookie: la segunda entra dentro de la ventana de gracia.
    api.c.cookies.clear()
    assert api.c.post("/api/auth/refrescar", cookies={"wms_sesion": cookie}).status_code == 200
    # Pasada la gracia, la sesion rotada ya no sirve.
    from app.modulos import auth
    previa, auth.GRACIA_ROTACION = auth.GRACIA_ROTACION, -1
    try:
        api.c.cookies.clear()
        assert api.c.post("/api/auth/refrescar", cookies={"wms_sesion": cookie}).status_code == 401
    finally:
        auth.GRACIA_ROTACION = previa
    # Cerrar sesion la invalida de inmediato, sin gracia.
    api.c.cookies.clear()
    assert api.c.post("/api/auth/salir", cookies={"wms_sesion": nueva}).status_code == 200
    api.c.cookies.clear()
    assert api.c.post("/api/auth/refrescar", cookies={"wms_sesion": nueva}).status_code == 401
    api.c.cookies.clear()


def test_limite_de_intentos(api):
    a = ajustes()
    previo, a.intentos_login = a.intentos_login, 3
    try:
        codigos = [api.c.post("/api/auth/login", json={"usuario": "fuerza", "clave": "x"}).status_code for _ in range(5)]
    finally:
        a.intentos_login = previo
    assert codigos[:3] == [401, 401, 401] and codigos[3:] == [429, 429]


def test_permisos_por_rol(api):
    assert api.get("/productos", como="lector")["total"] == 0
    datos = {"codigo": "X", "nombre": "X"}
    api.post("/familias", datos, espera=403, como="lector")
    api.post("/familias", datos, espera=403, como="digitador")
    api.get("/usuarios", espera=403, como="jefe")
    api.get("/auditoria", espera=403, como="digitador")
    assert "costos:ver" not in api.get("/auth/yo", como="digitador")["permisos"]
    assert "costos:ver" in api.get("/auth/yo", como="jefe")["permisos"]


def test_roles_son_configurables(api):
    permisos = [p["codigo"] for p in api.get("/permisos")]
    assert "fifo:omitir" in permisos and "costos:ver" in permisos
    rol = api.crear("/roles", {"codigo": "bodeguero", "nombre": "Bodeguero", "permisos": ["inventario:ver", "catalogo:ver"]})
    u = api.crear("/usuarios", {"usuario": "bode1", "nombre": "Bode Uno", "clave": CLAVE, "roles": [rol["id"]]})
    assert api.get("/productos", como="bode1")["total"] == 0
    api.post("/familias", {"codigo": "Y", "nombre": "Y"}, espera=403, como="bode1")
    api.put(f"/roles/{rol['id']}", {"permisos": ["inventario:ver", "catalogo:ver", "catalogo:administrar"]})
    api.crear("/familias", {"codigo": "Y", "nombre": "Y"}, como="bode1")  # el cambio de permisos rige de inmediato
    api.put(f"/usuarios/{u['id']}", {"activo": False})
    assert api.c.get("/api/productos", headers={"Authorization": f"Bearer {api.token('bode1')}"}).status_code == 401


def test_clave_debil_y_cambio(api):
    api.post("/usuarios", {"usuario": "debil", "nombre": "D", "clave": "123"}, espera=400)
    api.crear("/usuarios", {"usuario": "cambia", "nombre": "C", "clave": CLAVE})
    api.post("/auth/cambiar-clave", {"clave_actual": "otra", "clave_nueva": "Nueva1234"}, espera=400, como="cambia")
    api.post("/auth/cambiar-clave", {"clave_actual": CLAVE, "clave_nueva": "Nueva1234"}, espera=200, como="cambia")
    assert api.c.post("/api/auth/login", json={"usuario": "cambia", "clave": "Nueva1234"}).status_code == 200


def test_auditoria_registra_usuario_y_valores(api):
    f = api.crear("/familias", {"codigo": "AUD", "nombre": "Auditada"})
    api.put(f"/familias/{f['id']}", {"nombre": "Auditada 2"})
    filas = api.get("/auditoria", entidad="familia", entidad_id=str(f["id"]))["items"]
    assert [x["accion"] for x in filas] == ["EDITAR", "CREAR"]
    assert filas[0]["valor_anterior"]["nombre"] == "Auditada" and filas[0]["valor_nuevo"]["nombre"] == "Auditada 2"
    assert filas[0]["usuario"] == "Admin" and filas[0]["ip"]


def test_alcance_por_bodega_y_familia(api):
    b1 = api.crear("/bodegas", {"codigo": "B1", "nombre": "Bodega Uno"})
    b2 = api.crear("/bodegas", {"codigo": "B2", "nombre": "Bodega Dos"})
    f1 = api.crear("/familias", {"codigo": "F1", "nombre": "Familia Uno"})
    api.crear("/familias", {"codigo": "F2", "nombre": "Familia Dos"})
    rol = next(r for r in api.get("/roles") if r["codigo"] == "LECTOR")
    api.crear("/usuarios", {"usuario": "acotado", "nombre": "Acotado", "clave": CLAVE, "roles": [rol["id"]],
                            "todas_bodegas": False, "bodegas": [b1["id"]], "todas_familias": False, "familias": [f1["id"]]})
    assert [b["codigo"] for b in api.get("/bodegas", como="acotado")["items"]] == ["B1"]
    api.get(f"/bodegas/{b2['id']}", espera=404, como="acotado")
    assert [f["codigo"] for f in api.get("/familias", como="acotado")["items"]] == ["F1"]
    assert {b["codigo"] for b in api.get("/catalogos", como="acotado")["bodegas"]} == {"B1"}


def test_seguridad_primitivas():
    h = hash_clave("Secreta123")
    assert h.startswith("$argon2") and verificar_clave("Secreta123", h) and not verificar_clave("otra", h)
    assert descifrar(cifrar("clave-bd")) == "clave-bd" and cifrar("clave-bd") != "clave-bd"
    tokens = {token_qr() for _ in range(500)}
    assert len(tokens) == 500 and all(len(t) == 26 for t in tokens)


def test_cabeceras_de_seguridad(api):
    r = api.c.get("/api/salud")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"


def test_asistente_de_instalacion_crea_estructura_y_administrador():
    """Instalacion completa sobre una base vacia usando migraciones Alembic (motor demo = SQLite)."""
    a = ajustes()
    previo_dir, previo_url = a.dir_instancia, a.url_bd
    tmp = Path(tempfile.mkdtemp(prefix="wms_inst_"))
    a.dir_instancia, a.url_bd = tmp, ""
    nucleo_db.reiniciar_motor()
    try:
        from app.modulos.instalacion import instalado
        assert instalado() is False
        r = instalar(DatosInstalacion(
            empresa=DatosEmpresa(codigo="ACME", nombre="Acme Ltda."), bd=DatosBD(motor="demo", base_datos="instalada.db"),
            admin=DatosAdmin(usuario="root", nombre="Administrador", clave="Segura123"), temporada="2026-2027"))
        assert r["ok"] and "Tablas, indices y relaciones creados" in r["pasos"]
        assert (tmp / "config.json").exists() and "Segura123" not in (tmp / "config.json").read_text()
        assert instalado() is True
        tablas = set(inspect(nucleo_db.motor()).get_table_names())
        assert {"existencias", "movimientos_inventario", "lotes", "procesos", "reservas_stock", "alertas"} <= tablas
        with nucleo_db.nueva_sesion() as s:
            assert s.scalar(select(Empresa.codigo)) == "ACME"
            admin = s.scalar(select(Usuario).where(Usuario.usuario == "root"))
            assert "usuarios:administrar" in admin.permisos and len(admin.permisos) == len(s.scalars(select(Permiso)).all())
    finally:
        nucleo_db.reiniciar_motor()
        a.dir_instancia, a.url_bd = previo_dir, previo_url
        shutil.rmtree(tmp, ignore_errors=True)
