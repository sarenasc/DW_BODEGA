"""Linea de comandos: `wms demo`, `wms servir`, `wms migrar`, `wms alertas`, `wms reiniciar-demo`."""
import argparse
import os
import sys


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wms", description="WMS Bodegas")
    sub = p.add_subparsers(dest="comando", required=True)
    for nombre, ayuda in (("servir", "Inicia el servidor (API + frontend si esta compilado)"),
                          ("demo", "Inicia el Modo Demo con datos ficticios sobre SQLite")):
        s = sub.add_parser(nombre, help=ayuda)
        s.add_argument("--host", default="127.0.0.1")
        s.add_argument("--puerto", type=int, default=8000)
        s.add_argument("--recargar", action="store_true", help="Recarga automatica (desarrollo)")
    sub.add_parser("reiniciar-demo", help="Borra la base del Modo Demo para regenerarla en el proximo inicio")
    sub.add_parser("migrar", help="Aplica las migraciones pendientes a la base configurada")
    sub.add_parser("alertas", help="Evalua ahora las reglas de alerta")
    sub.add_parser("verificar", help="Comprueba que el saldo de cada existencia coincide con la suma de sus movimientos")
    args = p.parse_args(argv)

    if args.comando in ("servir", "demo"):
        if args.comando == "demo":
            os.environ["WMS_MODO_DEMO"] = "1"
        import uvicorn
        print(f"\n  WMS Bodegas{' (Modo Demo)' if args.comando == 'demo' else ''}: http://{args.host}:{args.puerto}\n")
        uvicorn.run("app.main:app", host=args.host, port=args.puerto, reload=args.recargar)
        return 0

    from app.core import db as nucleo_db
    from app.core.config import ajustes
    if args.comando == "reiniciar-demo":
        nucleo_db.reiniciar_motor()
        for nombre in ("demo.db", "demo.db-wal", "demo.db-shm", "produccion_demo.db"):
            (ajustes().dir_instancia / nombre).unlink(missing_ok=True)
        print("Base del Modo Demo eliminada. Se regenerara al iniciar `wms demo`.")
        return 0
    if not nucleo_db.url_activa():
        print("El sistema no esta instalado.", file=sys.stderr)
        return 1
    if args.comando == "migrar":
        from app.core.migraciones import migrar
        migrar(nucleo_db.url_activa())
        print("Migraciones aplicadas.")
    elif args.comando == "alertas":
        from app.tareas import tarea_alertas
        print(tarea_alertas())
    elif args.comando == "verificar":
        from sqlalchemy import func, select

        from app.modelos import Existencia, MovimientoInventario
        with nucleo_db.nueva_sesion() as s:
            sumas = dict(s.execute(select(MovimientoInventario.existencia_id, func.sum(MovimientoInventario.cantidad))
                                   .group_by(MovimientoInventario.existencia_id)).all())
            malas = [e.codigo_publico for e in s.scalars(select(Existencia)).unique()
                     if (sumas.get(e.id) or 0) != e.cantidad_fisica]
        print(f"Existencias revisadas correctamente." if not malas else f"DESCUADRE en: {', '.join(malas)}")
        return 1 if malas else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
