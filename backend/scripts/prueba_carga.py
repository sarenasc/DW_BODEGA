"""Prueba de carga y concurrencia por HTTP contra un servidor en marcha (use el Modo Demo; modifica datos).

Simula operadores consumiendo a la vez la MISMA existencia mientras otros consultan stock y dashboard.
Verifica que nunca se consuma mas de lo que habia y entrega latencias.

    python scripts/prueba_carga.py --url http://127.0.0.1:8765 --usuarios 20 --consumos 15
"""
import argparse
import statistics
import threading
import time

import httpx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--usuario", default="admin")
    ap.add_argument("--clave", default="Demo1234")
    ap.add_argument("--usuarios", type=int, default=20)
    ap.add_argument("--consumos", type=int, default=15)
    a = ap.parse_args()

    # Un solo inicio de sesion: el limite de intentos de login rechazaria decenas de accesos simultaneos.
    acceso = httpx.post(f"{a.url}/api/auth/login", json={"usuario": a.usuario, "clave": a.clave}, timeout=60)
    acceso.raise_for_status()
    token = acceso.json()["token"]

    def sesion() -> httpx.Client:
        return httpx.Client(base_url=a.url, timeout=60, headers={"Authorization": f"Bearer {token}"})

    admin = sesion()
    proceso = admin.post("/api/procesos", json={"codigo": f"CARGA-{int(time.time())}", "kilos_procesados": 1000}).json()
    admin.post(f"/api/procesos/{proceso['id']}/abrir").raise_for_status()
    existencias = admin.get("/api/existencias", params={"tam": 200}).json()["items"]
    # La existencia con mas stock: todos los hilos compiten por ella.
    objetivo = max((e for e in existencias if e["estado"] == "DISPONIBLE" and e["lote_estado"] in (None, "DISPONIBLE")),
                   key=lambda e: e["cantidad_fisica"])
    inicial = objetivo["cantidad_fisica"]
    intentos = a.usuarios * a.consumos
    cantidad = round(inicial / (intentos * 0.6), 4)  # a proposito no alcanza para todos: debe haber rechazos
    print(f"Existencia {objetivo['codigo_publico']} con {inicial} {objetivo['unidad']}; "
          f"{a.usuarios} usuarios x {a.consumos} consumos de {cantidad} = {round(intentos * cantidad, 2)} solicitados")

    latencias, resultados, errores = [], {"ok": 0, "sin_stock": 0, "otros": 0}, []
    candado, barrera = threading.Lock(), threading.Barrier(a.usuarios)

    def operador(n: int):
        c = sesion()
        barrera.wait()
        for i in range(a.consumos):
            t0 = time.perf_counter()
            r = c.post("/api/consumos", json={"proceso_id": proceso["id"], "existencia_id": objetivo["id"], "cantidad": cantidad,
                                              "confirmar_fifo": True, "justificacion": "prueba de carga",
                                              "clave_idempotencia": f"carga-{proceso['id']}-{n}-{i}"})
            dt = time.perf_counter() - t0
            if i % 5 == 0:
                c.get("/api/stock", params={"producto_id": objetivo["producto_id"]})
            with candado:
                latencias.append(dt)
                if r.status_code == 201:
                    resultados["ok"] += 1
                elif r.status_code == 409 and r.json().get("codigo") in ("STOCK_INSUFICIENTE", "STOCK_RESERVADO"):
                    resultados["sin_stock"] += 1
                else:
                    resultados["otros"] += 1
                    errores.append(f"{r.status_code} {r.text[:150]}")

    def lector():
        c = sesion()
        for _ in range(a.consumos):
            c.get("/api/dashboard")

    hilos = [threading.Thread(target=operador, args=(n,)) for n in range(a.usuarios)] + [threading.Thread(target=lector) for _ in range(3)]
    t0 = time.perf_counter()
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    total = time.perf_counter() - t0

    final = admin.get(f"/api/existencias/{objetivo['id']}").json()
    consumido = round(resultados["ok"] * cantidad, 6)
    movs = [m for m in final["movimientos"] if m["proceso_id"] == proceso["id"]]
    costo = admin.get(f"/api/procesos/{proceso['id']}").json()["costo_total"]
    latencias.sort()
    print(f"Resultado: {resultados} en {total:.1f} s ({len(latencias) / total:.0f} consumos/s)")
    print(f"Latencia consumo: mediana {statistics.median(latencias) * 1000:.0f} ms, p95 {latencias[int(len(latencias) * 0.95)] * 1000:.0f} ms, "
          f"max {latencias[-1] * 1000:.0f} ms")
    print(f"Stock: inicial {inicial}, consumido {consumido}, final {final['cantidad_fisica']}; movimientos del proceso: {len(movs)}; costo {costo}")
    correcto = (final["cantidad_fisica"] >= 0 and abs(inicial - consumido - final["cantidad_fisica"]) < 1e-4
                and len(movs) == resultados["ok"] and resultados["otros"] == 0 and resultados["sin_stock"] > 0)
    for e in errores[:5]:
        print("  error:", e)
    print("VERIFICACION:", "CORRECTA (sin stock negativo, saldo = inicial - consumido, un movimiento por consumo aceptado)" if correcto else "FALLIDA")
    return 0 if correcto else 1


if __name__ == "__main__":
    raise SystemExit(main())
