"""Reportes con exportacion (Excel, CSV, PDF) y buscador general."""
from datetime import date

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.db import get_db
from app.core.dependencias import Contexto, contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado, sin_permiso
from app.modelos import DocumentoInventario, Empresa, Existencia, Lote, Proceso, Producto, Subfamilia, Ubicacion
from app.servicios import reportes as svc

router = APIRouter(prefix="/api", tags=["Reportes"])


def filtros_de(ctx: Contexto, desde: date | None = None, hasta: date | None = None, bodega_id: int | None = None,
               familia_id: int | None = None, subfamilia_id: int | None = None, producto_id: int | None = None,
               proceso_id: int | None = None, temporada_id: int | None = None, especie: str | None = None,
               productor: str | None = None, proveedor_id: int | None = None, dias: int | None = None) -> svc.Filtros:
    if bodega_id:
        ctx.exigir_bodega(bodega_id)
    if familia_id:
        ctx.exigir_familia(familia_id)
    return svc.Filtros(empresa_id=ctx.empresa_id, desde=desde, hasta=hasta, bodega_id=bodega_id, familia_id=familia_id,
                       subfamilia_id=subfamilia_id, producto_id=producto_id, proceso_id=proceso_id, temporada_id=temporada_id,
                       especie=especie or None, productor=productor or None, proveedor_id=proveedor_id, dias=dias,
                       bodegas=ctx.bodegas, familias=ctx.familias)


@router.get("/reportes")
def listar(ctx: Contexto = Depends(requiere("reportes:ver"))):
    return [{"codigo": r.codigo, "titulo": r.titulo, "requiere_costos": r.requiere_costos}
            for r in svc.REPORTES.values() if ctx.ver_costos or not r.requiere_costos]


MEDIOS = {"csv": ("text/csv; charset=utf-8", svc.a_csv), "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", svc.a_xlsx),
          "pdf": ("application/pdf", None)}


@router.get("/reportes/{codigo}")
def ejecutar(codigo: str, formato: str = "json", desde: date | None = None, hasta: date | None = None,
             bodega_id: int | None = None, familia_id: int | None = None, subfamilia_id: int | None = None,
             producto_id: int | None = None, proceso_id: int | None = None, temporada_id: int | None = None,
             especie: str | None = None, productor: str | None = None, proveedor_id: int | None = None,
             dias: int | None = None, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("reportes:ver"))):
    rep = svc.REPORTES.get(codigo)
    if not rep:
        raise no_encontrado("Reporte")
    if rep.requiere_costos and not ctx.ver_costos:
        raise sin_permiso("Este reporte requiere el permiso para ver costos.")
    f = filtros_de(ctx, desde, hasta, bodega_id, familia_id, subfamilia_id, producto_id, proceso_id, temporada_id, especie,
                   productor, proveedor_id, dias)
    resultado = svc.ejecutar(db, codigo, f, ctx.ver_costos)
    if formato == "json":
        resultado.pop("_crudo")
        return resultado
    if formato not in MEDIOS:
        raise ErrorNegocio("FORMATO", "Formato no valido: json, csv, xlsx o pdf.")
    ctx.exigir("reportes:exportar")
    contenido = svc.a_pdf(resultado, db.get(Empresa, ctx.empresa_id).nombre) if formato == "pdf" else MEDIOS[formato][1](resultado)
    auditar(db, ctx, "reporte", codigo, "EXPORTAR", nuevo={"formato": formato, "filas": len(resultado["filas"])})
    return Response(contenido, media_type=MEDIOS[formato][0],
                    headers={"Content-Disposition": f'attachment; filename="{codigo}_{date.today():%Y%m%d}.{formato}"'})


@router.get("/buscar")
def buscar(q: str, db: Session = Depends(get_db), ctx: Contexto = Depends(contexto)):
    """Buscador general: producto, codigo, lote, QR, ubicacion, documento y proceso."""
    q = q.strip()
    if len(q) < 2:
        return []
    token = q.rstrip("/").split("/")[-1]
    patron = f"%{q.lower()}%"
    salida: list[dict] = []
    p = ctx.permisos

    def agregar(tipo, items):
        salida.extend({"tipo": tipo, **i} for i in items)

    if "catalogo:ver" in p:
        c = select(Producto).where(Producto.empresa_id == ctx.empresa_id, or_(
            func.lower(Producto.nombre).like(patron), func.lower(Producto.codigo).like(patron),
            func.lower(Producto.codigo_barras).like(patron), func.lower(Producto.codigo_externo).like(patron)))
        if ctx.familias is not None:
            c = c.join(Subfamilia, Producto.subfamilia_id == Subfamilia.id).where(Subfamilia.familia_id.in_(ctx.familias))
        agregar("producto", [{"id": x.id, "titulo": x.nombre, "detalle": x.codigo, "enlace": f"/productos/detalle/?id={x.id}"}
                             for x in db.scalars(c.limit(8)).unique()])
    if "lotes:ver" in p:
        agregar("lote", [{"id": x.id, "titulo": x.codigo, "detalle": f"{x.producto.nombre} · {x.estado}",
                          "enlace": f"/lotes/detalle/?id={x.id}"}
                         for x in db.scalars(select(Lote).where(Lote.empresa_id == ctx.empresa_id, func.lower(Lote.codigo).like(patron)).limit(8)).unique()])
    if "inventario:ver" in p:
        c = select(Existencia).where(Existencia.empresa_id == ctx.empresa_id, or_(
            func.lower(Existencia.codigo_publico).like(patron), Existencia.token_qr == token.upper()))
        if ctx.bodegas is not None:
            c = c.where(Existencia.bodega_id.in_(ctx.bodegas))
        agregar("existencia", [{"id": x.id, "titulo": x.codigo_publico,
                                "detalle": f"{x.producto.nombre} · {x.cantidad_fisica.normalize():f} {x.unidad.codigo}",
                                "enlace": f"/existencia/?id={x.id}"} for x in db.scalars(c.limit(8)).unique()])
        c = select(DocumentoInventario).where(DocumentoInventario.empresa_id == ctx.empresa_id, or_(
            func.lower(DocumentoInventario.numero).like(patron), func.lower(DocumentoInventario.numero_documento).like(patron)))
        if ctx.bodegas is not None:
            c = c.where(DocumentoInventario.bodega_id.in_(ctx.bodegas))
        agregar("documento", [{"id": x.id, "titulo": x.numero,
                               "detalle": f"{x.clase} · {x.tipo_documento or ''} {x.numero_documento or ''} · {x.estado}".strip(),
                               "enlace": f"/documentos/detalle/?id={x.id}"} for x in db.scalars(c.limit(8)).unique()])
    if "bodegas:ver" in p:
        c = select(Ubicacion).where(func.lower(Ubicacion.codigo_completo).like(patron), Ubicacion.activo.is_(True))
        if ctx.bodegas is not None:
            c = c.where(Ubicacion.bodega_id.in_(ctx.bodegas))
        agregar("ubicacion", [{"id": x.id, "titulo": x.codigo_completo, "detalle": x.tipo.capitalize(),
                               "enlace": f"/bodegas/plano/?id={x.bodega_id}&ubicacion={x.id}"} for x in db.scalars(c.limit(8))])
    if "procesos:ver" in p:
        agregar("proceso", [{"id": x.id, "titulo": x.codigo,
                             "detalle": " · ".join(v for v in (x.especie, x.productor, x.estado) if v),
                             "enlace": f"/procesos/detalle/?id={x.id}"}
                            for x in db.scalars(select(Proceso).where(Proceso.empresa_id == ctx.empresa_id, or_(
                                func.lower(Proceso.codigo).like(patron), func.lower(Proceso.numero).like(patron),
                                func.lower(Proceso.productor).like(patron), func.lower(Proceso.lote_productivo).like(patron))).limit(8))])
    return salida
