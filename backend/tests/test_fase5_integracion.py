"""Fase 5: integracion con la base productiva (simulada con una base SQLite externa de solo lectura)."""
import sqlite3
from pathlib import Path

import pytest

from app.core.config import ajustes
from app.core.errores import ErrorNegocio
from app.modelos import ConexionIntegracion
from app.servicios.integracion import transformar, validar_origen
from app.tareas import tarea_sincronizacion

from .conftest import CLAVE

ARCHIVO = "produccion_pruebas.db"


def origen() -> Path:
    return ajustes().dir_instancia / ARCHIVO


def sql(sentencia: str, *args):
    con = sqlite3.connect(origen())
    con.execute(sentencia, args)
    con.commit()
    con.close()


@pytest.fixture(scope="module")
def fuente(api):
    """Base productiva con nombres de columnas propios: nada coincide con los campos internos."""
    origen().unlink(missing_ok=True)
    con = sqlite3.connect(origen())
    con.executescript("""
        CREATE TABLE packing_corridas (id_corrida INTEGER PRIMARY KEY, n_proceso TEXT, fec_proceso TEXT, nom_productor TEXT,
            cod_productor TEXT, des_especie TEXT, des_variedad TEXT, n_lote TEXT, peso_neto REAL, peso_recepcion TEXT,
            cant_bins INTEGER, des_exportadora TEXT, turno TEXT, estado_corrida TEXT, kilos_embalados REAL, obs TEXT);
        INSERT INTO packing_corridas VALUES (501,'P-501','2026-09-10',' Agricola El Roble ','PR-77','cereza','Santina','L-9001',
            5000,'5.200,50',40,'Exportadora Andes','A','EN PROCESO',4100,'nota libre');
        INSERT INTO packing_corridas VALUES (502,'P-502','2026-09-11','Fundo Los Aromos','PR-12','Ciruela','Angeleno','L-9002',
            8000,'8.300',64,'Exportadora Andes','B','EN PROCESO',7000,NULL);
        INSERT INTO packing_corridas VALUES (503,'P-503','2026-09-12','Fundo Los Aromos','PR-12','Ciruela','Larry Ann','L-9003',
            1000,'1.050',8,'Frutas del Sur','A','EN PROCESO',900,NULL);
        CREATE VIEW vw_corridas AS SELECT * FROM packing_corridas;
    """)
    con.commit()
    con.close()
    c = api.crear("/integraciones/conexiones", {"nombre": "Produccion", "motor": "demo", "base_datos": ARCHIVO,
                                                "usuario": "lector_wms", "clave": "S3creta-bd"})
    f = api.crear("/integraciones/fuentes", {
        "conexion_id": c["id"], "nombre": "Corridas de packing", "tipo": "CONSULTA", "columna_id": "id_corrida",
        "columna_fecha": "fec_proceso", "origen": "SELECT * FROM packing_corridas WHERE estado_corrida <> 'ANULADA'",
        "mapeos": [
            {"columna_externa": "n_proceso", "campo_interno": "codigo"},
            {"columna_externa": "fec_proceso", "campo_interno": "fecha", "transformacion": "FECHA"},
            {"columna_externa": "nom_productor", "campo_interno": "productor", "politica_actualizacion": "SOLO_IMPORTAR"},
            {"columna_externa": "cod_productor", "campo_interno": "codigo_productor"},
            {"columna_externa": "des_especie", "campo_interno": "especie", "transformacion": "MAYUSCULAS"},
            {"columna_externa": "des_variedad", "campo_interno": "variedad", "politica_actualizacion": "MANUAL"},
            {"columna_externa": "n_lote", "campo_interno": "lote_productivo"},
            {"columna_externa": "peso_neto", "campo_interno": "kilos_procesados"},
            {"columna_externa": "peso_recepcion", "campo_interno": "kilos_recepcionados", "transformacion": "NUMERO"},
            {"columna_externa": "cant_bins", "campo_interno": "bins"},
            {"columna_externa": "des_exportadora", "campo_interno": "exportadora"},
            {"columna_externa": "turno", "campo_interno": "turno"},
            {"columna_externa": "estado_corrida", "campo_interno": "estado_externo"},
            {"columna_externa": "kilos_embalados", "campo_interno": "extra.kilos_embalados", "transformacion": "NUMERO"}]})
    return {"conexion": c, "fuente": f}


def importar(api, fuente, id_externo, abrir=True):
    r = api.post(f"/integraciones/fuentes/{fuente['fuente']['id']}/importar", {"ids": [str(id_externo)], "abrir": abrir}, espera=200)
    assert r["importados"], r
    return api.get(f"/procesos/{r['importados'][0]['id']}")


def test_solo_se_admite_un_select():
    assert validar_origen("VISTA", "dbo.vw_procesos") == "dbo.vw_procesos"
    assert validar_origen("CONSULTA", "SELECT a, b FROM t WHERE c = 1;").startswith("SELECT")
    assert validar_origen("CONSULTA", "WITH x AS (SELECT 1 AS a) SELECT * FROM x")
    for mala in ("DELETE FROM procesos", "SELECT 1; DROP TABLE procesos", "UPDATE t SET a = 1", "SELECT * INTO copia FROM t",
                 "EXEC xp_cmdshell 'dir'", "SELECT 1 -- x\n; DELETE FROM t", "", "select * from t where a in (select 1); select 2"):
        with pytest.raises(ErrorNegocio):
            validar_origen("CONSULTA", mala)
    for mala in ("t; DROP TABLE x", "vw_procesos WHERE 1=1; delete from t"):
        with pytest.raises(ErrorNegocio):
            validar_origen("VISTA", mala)


def test_transformaciones():
    assert transformar("5.200,50", "kilos_recepcionados", "NUMERO", None) == pytest.approx(5200.5)
    assert transformar("1,5", "extra", "NUMERO", 1000) == 1500
    assert transformar(" hola ", "productor", None, None) == "hola"
    assert transformar("cereza", "especie", "MAYUSCULAS", None) == "CEREZA"
    assert str(transformar("10/09/2026", "fecha", None, None)) == "2026-09-10"
    assert transformar(None, "kilos_procesados", None, None) is None
    with pytest.raises(ErrorNegocio):
        transformar("abc", "kilos_procesados", None, None)


def test_credenciales_cifradas_y_nunca_devueltas(api, fuente):
    c = api.get("/integraciones/conexiones")[0]
    assert "clave" not in c and "clave_cifrada" not in c and c["tiene_clave"] is True
    with api.sesion() as s:
        guardada = s.get(ConexionIntegracion, c["id"]).clave_cifrada
    assert guardada and "S3creta-bd" not in guardada
    assert "S3creta-bd" not in str(api.get("/auditoria", entidad="conexion_integracion")["items"])
    assert api.post(f"/integraciones/conexiones/{c['id']}/probar", espera=200)["ok"] is True
    api.get("/integraciones/conexiones", espera=403, como="jefe")
    api.post("/integraciones/fuentes", {"conexion_id": c["id"], "nombre": "Mala", "origen": "DELETE FROM packing_corridas",
                                        "columna_id": "id_corrida"}, espera=400)
    api.post("/integraciones/fuentes", {"conexion_id": c["id"], "nombre": "Mala", "origen": "SELECT 1", "columna_id": "id; drop"}, espera=400)
    api.put(f"/integraciones/fuentes/{fuente['fuente']['id']}", {"mapeos": [{"columna_externa": "x", "campo_interno": "inventado"}]}, espera=400)


def test_mapeo_visual_columnas_y_vista_previa(api, fuente):
    fid = fuente["fuente"]["id"]
    cols = api.get(f"/integraciones/fuentes/{fid}/columnas")["columnas"]
    assert {"id_corrida", "peso_neto", "nom_productor", "kilos_embalados"} <= set(cols)  # leidas del origen, no asumidas
    vp = api.get(f"/integraciones/fuentes/{fid}/vista-previa")
    fila = next(f for f in vp["filas"] if f["origen"]["id_corrida"] == 501)
    assert fila["mapeado"]["kilos_recepcionados"] == 5200.5 and fila["mapeado"]["especie"] == "CEREZA"
    assert fila["mapeado"]["productor"] == "Agricola El Roble" and fila["adicionales"]["kilos_embalados"] == 4100
    disponibles = api.get(f"/integraciones/fuentes/{fid}/disponibles")
    assert [d["id_externo"] for d in disponibles] == ["503", "502", "501"] and not any(d["importado"] for d in disponibles)
    assert len(api.get(f"/integraciones/fuentes/{fid}/disponibles", desde="2026-09-12")) == 1


def test_importar_copia_el_proceso_a_la_base_local(api, fuente):
    p = importar(api, fuente, 501)
    assert p["codigo"] == "P-501" and p["id_externo"] == "501" and p["estado"] == "ABIERTO" and p["tiene_fuente"]
    assert (p["especie"], p["variedad"], p["productor"], p["codigo_productor"]) == ("CEREZA", "Santina", "Agricola El Roble", "PR-77")
    assert (p["kilos_procesados"], p["kilos_recepcionados"], p["bins"], p["turno"]) == (5000, 5200.5, 40, "A")
    assert p["fecha"] == "2026-09-10" and p["temporada_codigo"] == "2026-2027" and p["ultima_sincronizacion"]
    assert p["datos_adicionales"]["kilos_embalados"] == 4100 and p["datos_adicionales"]["obs"] == "nota libre"  # no mapeada: se conserva
    captura = api.get(f"/procesos/{p['id']}/capturas")[0]["datos"]
    assert captura["peso_recepcion"] == "5.200,50" and captura["nom_productor"] == " Agricola El Roble "  # snapshot crudo
    r = api.post(f"/integraciones/fuentes/{fuente['fuente']['id']}/importar", {"ids": ["501", "999"]}, espera=200)
    assert not r["importados"] and {o["id_externo"] for o in r["omitidos"]} == {"501", "999"}
    assert next(d for d in api.get(f"/integraciones/fuentes/{fuente['fuente']['id']}/disponibles") if d["id_externo"] == "501")["importado"]


def test_actualizar_registra_valor_anterior_nuevo_y_usuario(api, fuente):
    p = next(x for x in api.get("/procesos", q="P-501")["items"])
    sql("UPDATE packing_corridas SET peso_neto = 15000, des_variedad = 'OTRA', nom_productor = 'CAMBIADO', kilos_embalados = 12000 WHERE id_corrida = 501")
    r = api.post(f"/procesos/{p['id']}/actualizar", espera=200, como="jefe")
    assert r["kilos_procesados"] == 15000 and r["sincronizacion"]["cambios"] == 2
    # Politicas por campo: SOLO_IMPORTAR y MANUAL no se sobrescriben al actualizar.
    assert r["productor"] == "Agricola El Roble" and r["variedad"] == "Santina"
    cambios = {c["campo"]: c for c in r["cambios"]}
    k = cambios["kilos_procesados"]
    assert (float(k["valor_anterior"]), float(k["valor_nuevo"]), k["usuario"], k["origen"]) == (5000, 15000, "Jefe", "SINCRONIZACION")
    assert float(cambios["extra.kilos_embalados"]["valor_nuevo"]) == 12000
    sql("UPDATE packing_corridas SET peso_neto = 28450 WHERE id_corrida = 501")
    r = api.post(f"/procesos/{p['id']}/actualizar", espera=200)
    assert r["kilos_procesados"] == 28450 and r["capturas"] == 3
    assert api.post(f"/procesos/{p['id']}/actualizar", espera=200)["sincronizacion"]["cambios"] == 0  # sin cambios no se inventa historia
    api.post(f"/procesos/{p['id']}/actualizar", espera=403, como="digitador")


def test_actualizar_y_cerrar_toma_los_kilos_definitivos(api, fuente):
    p = next(x for x in api.get("/procesos", q="P-501")["items"])
    sql("UPDATE packing_corridas SET peso_neto = 28900, estado_corrida = 'TERMINADA' WHERE id_corrida = 501")
    api.post(f"/procesos/{p['id']}/cerrar", {"actualizar": True, "kilos": 1}, espera=400)  # un cierre sincronizado no admite kilos digitados
    c = api.post(f"/procesos/{p['id']}/cerrar", {"actualizar": True}, espera=200)
    assert c["estado"] == "CERRADO" and c["kilos_definitivos"] == 28900 and c["estado_kilos"] == "DEFINITIVO"
    assert c["modo_cierre"] == "SINCRONIZADO" and c["cerrado_sincronizado"] is True and c["estado_externo"] == "TERMINADA"
    assert c["ultima_sincronizacion"] and c["cerrado_por_nombre"] == "Admin"
    # Cerrado: la operacion ya no depende del origen ni vuelve a consultarlo.
    sql("UPDATE packing_corridas SET peso_neto = 1 WHERE id_corrida = 501")
    api.post(f"/procesos/{p['id']}/actualizar", espera=409)
    assert api.get(f"/procesos/{p['id']}")["kilos_definitivos"] == 28900


def test_cerrar_sin_actualizar_exige_permiso_y_queda_marcado(api, fuente):
    p = importar(api, fuente, 502)
    rol = api.crear("/roles", {"codigo": "cerrador", "nombre": "Cerrador", "permisos": ["procesos:ver", "procesos:cerrar"]})
    api.crear("/usuarios", {"usuario": "cerrador", "nombre": "Cerrador", "clave": CLAVE, "roles": [rol["id"]]})
    r = api.post(f"/procesos/{p['id']}/cerrar", {"actualizar": False}, espera=403, como="cerrador")
    assert "permiso especial" in r["mensaje"]
    c = api.post(f"/procesos/{p['id']}/cerrar", {"actualizar": False, "kilos": 8100, "observacion": "Produccion sin conexion"}, espera=200)
    assert c["modo_cierre"] == "MANUAL" and c["cerrado_sincronizado"] is False and c["kilos_definitivos"] == 8100
    alerta = api.get("/alertas", tipo="PROCESO_CERRADO_SIN_SINCRONIZACION")["items"][0]
    assert alerta["entidad_id"] == p["id"] and alerta["severidad"] == "ALTA" and alerta["enlace"].endswith(str(p["id"]))
    auditoria = api.get("/auditoria", entidad="proceso", entidad_id=str(p["id"]), accion="CERRAR")["items"][0]
    assert auditoria["valor_nuevo"]["modo_cierre"] == "MANUAL" and auditoria["motivo"] == "Produccion sin conexion"


def test_origen_caido_no_detiene_la_operacion_local(api, fuente, base):
    p = importar(api, fuente, 503)
    respaldo = origen().with_suffix(".bak")
    origen().rename(respaldo)
    try:
        r = api.post(f"/procesos/{p['id']}/actualizar", espera=502)
        assert r["codigo"] == "ORIGEN_NO_DISPONIBLE"
        api.post(f"/procesos/{p['id']}/cerrar", {"actualizar": True}, espera=502)
        assert api.get(f"/procesos/{p['id']}")["estado"] == "ABIERTO"  # el cierre fallido no dejo nada a medias
        # El fallo queda registrado aunque la operacion se haya revertido.
        fallos = api.get("/integraciones/ejecuciones", proceso_id=p["id"], estado="ERROR")["items"]
        assert len(fallos) == 2 and fallos[0]["error"]
        assert any(a["entidad_id"] == p["id"] for a in api.get("/alertas", tipo="ERROR_SINCRONIZACION", abiertas=True)["items"])
        # Los consumos siguen funcionando: la aplicacion trabaja sobre su base local.
        x = base["producto"]("INTEG1")
        e = base["ingreso"](x["id"], fecha="2026-09-01T10:00:00")["existencias"][0]
        api.post("/consumos", {"proceso_id": p["id"], "existencia_id": e["id"], "cantidad": 2}, espera=201)
    finally:
        respaldo.rename(origen())
    api.post(f"/procesos/{p['id']}/actualizar", espera=200)
    assert not [a for a in api.get("/alertas", tipo="ERROR_SINCRONIZACION", abiertas=True)["items"] if a["entidad_id"] == p["id"]]


def test_proceso_eliminado_en_origen_conserva_la_copia_local(api, fuente):
    p = next(x for x in api.get("/procesos", q="P-503")["items"])
    sql("UPDATE packing_corridas SET estado_corrida = 'ANULADA' WHERE id_corrida = 503")  # la consulta ya no lo devuelve
    r = api.post(f"/procesos/{p['id']}/actualizar", espera=409)
    assert r["codigo"] == "NO_EXISTE_EN_ORIGEN"
    assert api.get(f"/procesos/{p['id']}")["codigo"] == "P-503"
    sql("UPDATE packing_corridas SET estado_corrida = 'EN PROCESO' WHERE id_corrida = 503")


def test_sincronizacion_automatica_de_procesos_abiertos(api, fuente):
    p = next(x for x in api.get("/procesos", q="P-503")["items"])
    assert tarea_sincronizacion() == 0  # sin intervalo configurado no hay sincronizacion automatica
    api.put(f"/integraciones/fuentes/{fuente['fuente']['id']}", {"intervalo_minutos": 1})
    sql("UPDATE packing_corridas SET peso_neto = 4321 WHERE id_corrida = 503")
    from app.core import db as nucleo_db
    from app.modelos import Proceso
    with nucleo_db.nueva_sesion() as s:
        s.get(Proceso, p["id"]).ultima_sincronizacion = None
        s.commit()
    assert tarea_sincronizacion() == 1
    d = api.get(f"/procesos/{p['id']}")
    assert d["kilos_procesados"] == 4321 and d["cambios"][0]["usuario"] is None  # cambio hecho por el sistema
    api.put(f"/integraciones/fuentes/{fuente['fuente']['id']}", {"intervalo_minutos": 0})


def test_fuente_tipo_vista(api, fuente):
    f = api.crear("/integraciones/fuentes", {"conexion_id": fuente["conexion"]["id"], "nombre": "Vista", "tipo": "VISTA",
                                             "origen": "vw_corridas", "columna_id": "id_corrida",
                                             "mapeos": [{"columna_externa": "N_PROCESO", "campo_interno": "numero"}]})
    assert "des_especie" in api.get(f"/integraciones/fuentes/{f['id']}/columnas")["columnas"]
    assert len(api.get(f"/integraciones/fuentes/{f['id']}/disponibles")) == 3
    r = api.post(f"/integraciones/fuentes/{f['id']}/importar", {"ids": ["502"]}, espera=200)
    p = api.get(f"/procesos/{r['importados'][0]['id']}")
    assert p["codigo"] == "EXT-502" and p["numero"] == "P-502" and p["estado"] == "BORRADOR"  # nombres de columna sin distinguir mayusculas
    api.delete(f"/integraciones/fuentes/{f['id']}")
    assert any(x["id"] == f["id"] and x["activa"] is False for x in api.get("/integraciones/fuentes"))  # con procesos: solo se desactiva
