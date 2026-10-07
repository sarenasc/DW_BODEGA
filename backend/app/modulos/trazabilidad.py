"""Trazabilidad navegable hacia adelante (lote -> procesos) y hacia atras (proceso -> documentos)."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import no_encontrado
from app.core.util import json_valor, ocultar_costos
from app.modelos import (DetalleDocumentoInventario, DocumentoInventario, Existencia, Lote, MovimientoInventario, Proceso,
                         Producto, Proveedor, Usuario)

router = APIRouter(prefix="/api/trazabilidad", tags=["Trazabilidad"])
ORDEN = ("documento", "lote", "existencia", "movimiento", "proceso")


class Grafo:
    """Acumula nodos (entidades), enlaces entre ellos y la linea de tiempo de eventos."""

    def __init__(self, db: Session):
        self.db = db
        self.nodos: dict[str, dict] = {}
        self.enlaces: set[tuple[str, str]] = set()
        self.eventos: list[dict] = []
        self._usuarios: dict[int, str] | None = None

    def usuario(self, id_: int | None) -> str | None:
        if self._usuarios is None:
            self._usuarios = dict(self.db.execute(select(Usuario.id, Usuario.nombre)).all())
        return self._usuarios.get(id_)

    def nodo(self, tipo: str, id_: int, titulo: str, detalle: str = "", enlace: str | None = None, **extra) -> str:
        clave = f"{tipo}:{id_}"
        self.nodos.setdefault(clave, {"clave": clave, "tipo": tipo, "id": id_, "titulo": titulo, "detalle": detalle,
                                      "enlace": enlace, **extra})
        return clave

    def unir(self, origen: str | None, destino: str | None) -> None:
        if origen and destino:
            self.enlaces.add((origen, destino))

    def documento(self, doc: DocumentoInventario) -> str:
        prov = self.db.get(Proveedor, doc.proveedor_id).nombre if doc.proveedor_id else None
        ref = " ".join(x for x in (doc.tipo_documento, doc.numero_documento) if x)
        return self.nodo("documento", doc.id, doc.numero, " · ".join(x for x in (doc.clase.capitalize(), ref, prov) if x),
                         f"/documentos/detalle/?id={doc.id}", estado=doc.estado, fecha=json_valor(doc.fecha))

    def lote(self, lote: Lote) -> str:
        return self.nodo("lote", lote.id, lote.codigo, f"{lote.producto.nombre} · {lote.estado}", f"/lotes/detalle/?id={lote.id}",
                         estado=lote.estado, fecha_vencimiento=json_valor(lote.fecha_vencimiento))

    def existencia(self, e: Existencia) -> str:
        return self.nodo("existencia", e.id, e.codigo_publico,
                         f"{e.producto.nombre} · {e.cantidad_fisica.normalize():f}/{e.cantidad_inicial.normalize():f} {e.unidad.codigo}"
                         f" · {e.ubicacion.codigo_completo if e.ubicacion else e.bodega.nombre}", f"/existencia/?id={e.id}",
                         estado=e.estado, costo_unitario=float(e.costo_unitario), fecha=json_valor(e.fecha_ingreso))

    def proceso(self, p: Proceso) -> str:
        return self.nodo("proceso", p.id, p.codigo, " · ".join(x for x in (p.especie, p.variedad, p.productor, p.estado) if x),
                         f"/procesos/detalle/?id={p.id}", estado=p.estado, fecha=json_valor(p.fecha))

    def movimiento(self, m: MovimientoInventario, clave_existencia: str) -> str:
        e = m.existencia
        clave = self.nodo("movimiento", m.id, f"{m.tipo.nombre} {abs(m.cantidad).normalize():f} {e.unidad.codigo}",
                          f"{m.fecha:%d-%m-%Y %H:%M} · {self.usuario(m.usuario_id) or 'sistema'}", None, tipo_codigo=m.tipo.codigo,
                          cantidad=float(m.cantidad), costo_total=float(m.costo_total), fecha=json_valor(m.fecha),
                          anula_a=m.movimiento_anulado_id)
        self.unir(clave_existencia, clave)
        self.eventos.append({"fecha": json_valor(m.fecha), "tipo": m.tipo.codigo, "titulo": f"{m.tipo.nombre}: {e.producto.nombre}",
                             "detalle": f"{m.cantidad.normalize():f} {e.unidad.codigo} · {e.codigo_publico}"
                                        + (f" · lote {e.lote.codigo}" if e.lote else ""),
                             "usuario": self.usuario(m.usuario_id), "costo_total": float(m.costo_total), "nodo": clave,
                             "motivo": m.motivo_texto})
        return clave

    def cadena_existencia(self, e: Existencia, hacia_adelante: bool = True) -> str:
        """Agrega la existencia con su lote, su documento de ingreso y (opcionalmente) sus movimientos y procesos."""
        ce = self.existencia(e)
        if e.lote:
            self.unir(self.lote(e.lote), ce)
        if e.detalle_origen_id:
            det = self.db.get(DetalleDocumentoInventario, e.detalle_origen_id)
            cd = self.documento(self.db.get(DocumentoInventario, det.documento_id))
            self.unir(cd, self.lote(e.lote) if e.lote else ce)
        if e.existencia_padre_id:
            padre = self.db.get(Existencia, e.existencia_padre_id)
            self.unir(self.cadena_existencia(padre, hacia_adelante=False), ce)
        if hacia_adelante:
            for m in self.db.scalars(select(MovimientoInventario).where(MovimientoInventario.existencia_id == e.id)
                                     .order_by(MovimientoInventario.id)).unique():
                cm = self.movimiento(m, ce)
                if m.proceso_id:
                    self.unir(cm, self.proceso(self.db.get(Proceso, m.proceso_id)))
            for hija in self.db.scalars(select(Existencia).where(Existencia.existencia_padre_id == e.id)).unique():
                if f"existencia:{hija.id}" not in self.nodos:
                    self.unir(ce, self.cadena_existencia(hija))
        return ce

    def salida(self, raiz: str, ver_costos: bool) -> dict:
        columnas = [{"tipo": t, "nodos": sorted((n for n in self.nodos.values() if n["tipo"] == t), key=lambda n: n["id"])} for t in ORDEN]
        datos = {"raiz": raiz, "columnas": [c for c in columnas if c["nodos"]],
                 "enlaces": [{"origen": o, "destino": d} for o, d in sorted(self.enlaces)],
                 "linea_tiempo": sorted(self.eventos, key=lambda ev: ev["fecha"]),
                 "resumen": {t: sum(1 for n in self.nodos.values() if n["tipo"] == t) for t in ORDEN}}
        return ocultar_costos(datos, ver_costos)


@router.get("/lote/{id_}")
def desde_lote(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("trazabilidad:ver"))):
    """Lote -> ingreso -> documento -> existencias -> movimientos -> consumos -> procesos."""
    lote = db.get(Lote, id_)
    if not lote or lote.empresa_id != ctx.empresa_id:
        raise no_encontrado("Lote")
    ctx.exigir_familia(lote.producto.subfamilia.familia_id)
    g = Grafo(db)
    raiz = g.lote(lote)
    if lote.lote_padre_id:
        g.unir(g.lote(db.get(Lote, lote.lote_padre_id)), raiz)
    for sub in db.scalars(select(Lote).where(Lote.lote_padre_id == lote.id)).unique():
        g.unir(raiz, g.lote(sub))
        for e in db.scalars(select(Existencia).where(Existencia.lote_id == sub.id)).unique():
            g.cadena_existencia(e)
    for e in db.scalars(select(Existencia).where(Existencia.lote_id == lote.id).order_by(Existencia.id)).unique():
        g.cadena_existencia(e)
    return g.salida(raiz, ctx.ver_costos)


@router.get("/proceso/{id_}")
def desde_proceso(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("trazabilidad:ver"))):
    """Proceso -> consumos -> productos -> existencias -> lotes -> ingresos -> documentos."""
    p = db.get(Proceso, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Proceso")
    g = Grafo(db)
    raiz = g.proceso(p)
    productos: dict[int, dict] = {}
    for m in db.scalars(select(MovimientoInventario).where(MovimientoInventario.proceso_id == p.id)
                        .order_by(MovimientoInventario.id)).unique():
        e = m.existencia
        ce = g.cadena_existencia(e, hacia_adelante=False)
        g.unir(g.movimiento(m, ce), raiz)
        fila = productos.setdefault(e.producto_id, {"producto_id": e.producto_id, "producto": e.producto.nombre,
                                                    "unidad": e.unidad.codigo, "cantidad": 0.0, "costo": 0.0, "lotes": set()})
        fila["cantidad"] -= float(m.cantidad)
        fila["costo"] -= float(m.costo_total)
        if e.lote:
            fila["lotes"].add(e.lote.codigo)
    datos = g.salida(raiz, ctx.ver_costos)
    datos["productos"] = ocultar_costos([{**f, "lotes": sorted(f["lotes"])} for f in productos.values()], ctx.ver_costos)
    return datos


@router.get("/existencia/{id_}")
def desde_existencia(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("trazabilidad:ver"))):
    e = db.get(Existencia, id_)
    if not e or e.empresa_id != ctx.empresa_id:
        raise no_encontrado("Existencia")
    ctx.exigir_bodega(e.bodega_id)
    g = Grafo(db)
    return g.salida(g.cadena_existencia(e), ctx.ver_costos)


@router.get("/producto/{id_}")
def desde_producto(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("trazabilidad:ver"))):
    """Lotes de un producto, como punto de entrada a la trazabilidad."""
    p = db.get(Producto, id_)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Producto")
    return [{"id": x.id, "codigo": x.codigo, "estado": x.estado, "fecha_ingreso": json_valor(x.fecha_ingreso),
             "fecha_vencimiento": json_valor(x.fecha_vencimiento)}
            for x in db.scalars(select(Lote).where(Lote.producto_id == p.id).order_by(Lote.id.desc()).limit(200)).unique()]
