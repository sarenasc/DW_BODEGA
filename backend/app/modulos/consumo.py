"""Consumo rapido (movil / lector QR) e impresion de etiquetas."""
from decimal import Decimal
from io import BytesIO

import segno
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.config import ajustes
from app.core.db import get_db
from app.core.dependencias import Contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.parametros import parametro
from app.core.util import json_valor, ocultar_costos
from app.modelos import Existencia, MotivoMovimiento, MovimientoInventario, PlantillaEtiqueta, Proceso, TipoMovimiento
from app.servicios import inventario as svc
from app.servicios.catalogo import a_unidad_base, politica_efectiva

from .inventario import existencia_dict, movimiento_dict, obtener_existencia, resolver_codigo

router = APIRouter(prefix="/api", tags=["Consumo rapido y QR"])


def _proceso_abierto(db: Session, ctx: Contexto, proceso_id: int, tocar: bool = False) -> Proceso:
    p = db.get(Proceso, proceso_id)
    if not p or p.empresa_id != ctx.empresa_id:
        raise no_encontrado("Proceso")
    if tocar:
        # Toma el bloqueo de la fila solo si sigue ABIERTO: un cierre simultaneo no puede colarse.
        r = db.execute(update(Proceso).where(Proceso.id == p.id, Proceso.estado == "ABIERTO").values(version=Proceso.version + 1))
        if r.rowcount == 0:
            db.refresh(p)
            raise ErrorNegocio("PROCESO_NO_ABIERTO", f"El proceso {p.codigo} esta {p.estado}: no admite consumos.", 409)
        db.refresh(p)
    elif p.estado != "ABIERTO":
        raise ErrorNegocio("PROCESO_NO_ABIERTO", f"El proceso {p.codigo} esta {p.estado}: no admite consumos.", 409)
    return p


@router.get("/consumo/escanear")
def escanear(codigo: str, proceso_id: int | None = None, db: Session = Depends(get_db),
             ctx: Contexto = Depends(requiere("movimientos:crear"))):
    """Paso 2-3 del flujo: resuelve el QR y entrega la ficha con la advertencia FIFO/FEFO si corresponde."""
    e = resolver_codigo(db, ctx, codigo)
    d = existencia_dict(db, e, detalle=True)
    avisos, bloqueo = [], None
    try:
        avisos = svc.validar_estado_consumible(ctx, e)
    except ErrorNegocio as err:
        bloqueo = {"codigo": err.codigo, "mensaje": err.mensaje}
    if e.cantidad_fisica <= 0:
        bloqueo = bloqueo or {"codigo": "STOCK_INSUFICIENTE", "mensaje": "Esta existencia no tiene stock."}
    pol = politica_efectiva(e.producto)
    d["fifo"] = svc.evaluar_orden(db, e, pol) if not bloqueo else None
    d["politica_fifo"], d["estrategia"] = pol["politica_fifo"], pol["estrategia_salida"]
    d["puede_omitir_fifo"] = ctx.puede("fifo:omitir")
    d["avisos"], d["bloqueo"] = avisos, bloqueo
    d["disponible_para_proceso"] = float(svc.disponible_para(db, e, proceso_id))
    return ocultar_costos(d, ctx.ver_costos)


class ConsumoEntrada(BaseModel):
    proceso_id: int | None = None
    existencia_id: int | None = None
    codigo: str | None = None  # alternativa a existencia_id: lo leido por el lector
    cantidad: Decimal
    unidad_id: int | None = None
    confirmar_fifo: bool = False
    justificacion: str | None = None
    motivo_codigo: str = "PROCESO"  # motivo de salida configurable
    observacion: str | None = None
    clave_idempotencia: str | None = None


@router.post("/consumos", status_code=201)
def registrar_consumo(d: ConsumoEntrada, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("movimientos:crear"))):
    """Paso 4-5: el usuario solo indica la cantidad. Descuenta, valoriza y asocia al proceso en una transaccion."""
    e = obtener_existencia(db, ctx, d.existencia_id) if d.existencia_id else resolver_codigo(db, ctx, d.codigo or "")
    motivo = db.scalar(select(MotivoMovimiento).where(MotivoMovimiento.clase == "SALIDA", MotivoMovimiento.codigo == d.motivo_codigo,
                                                      MotivoMovimiento.activo.is_(True)))
    if not motivo:
        raise ErrorNegocio("MOTIVO", "Motivo de salida no valido.")
    proceso = None
    if d.proceso_id:
        proceso = _proceso_abierto(db, ctx, d.proceso_id, tocar=True)
    elif motivo.requiere_proceso:
        raise ErrorNegocio("PROCESO_REQUERIDO", "Debe seleccionar un proceso.")
    base, _ = a_unidad_base(db, e.producto, d.cantidad, d.unidad_id)
    m, info = svc.registrar_salida(
        db, ctx, e, base, motivo.tipo_movimiento.codigo, proceso=proceso, motivo_id=motivo.id,
        justificacion=d.justificacion, confirmar_fifo=d.confirmar_fifo, clave_idempotencia=d.clave_idempotencia,
        cantidad_ingresada=d.cantidad, unidad_ingresada_id=d.unidad_id or e.unidad_id, observacion=d.observacion)
    db.refresh(e)
    return ocultar_costos({"movimiento": movimiento_dict(db, m, True), "duplicado": info["duplicado"],
                           "avisos": info["avisos"], "fuera_de_orden": info["fifo"] is not None,
                           "existencia": existencia_dict(db, e)}, ctx.ver_costos)


@router.get("/consumos/recientes")
def recientes(proceso_id: int | None = None, mios: bool = True, limite: int = Query(15, le=100),
              db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("movimientos:crear"))):
    """Ultimos consumos para la pantalla movil, con indicacion de si pueden anularse."""
    tipos = select(TipoMovimiento.id).where(TipoMovimiento.codigo.in_(("CONSUMO", "SALIDA", "MERMA")))
    c = select(MovimientoInventario).where(MovimientoInventario.empresa_id == ctx.empresa_id,
                                           MovimientoInventario.tipo_movimiento_id.in_(tipos))
    if proceso_id:
        c = c.where(MovimientoInventario.proceso_id == proceso_id)
    if mios:
        c = c.where(MovimientoInventario.usuario_id == ctx.usuario.id)
    filas = db.scalars(c.order_by(MovimientoInventario.id.desc()).limit(limite)).unique().all()
    puede = ctx.puede("movimientos:anular")
    salida = []
    for m in filas:
        d = movimiento_dict(db, m, True)
        d["puede_anular"] = puede and not d["anulado"]
        salida.append(d)
    return ocultar_costos(salida, ctx.ver_costos)


# ---------------------------------------------------------------- QR y etiquetas

def url_qr(db: Session, e: Existencia) -> str:
    base = (parametro(db, "etiquetas.url_base", e.empresa_id, "") or ajustes().url_publica).rstrip("/")
    return f"{base}/q/{e.token_qr}"


@router.get("/existencias/{id_}/qr")
def qr_svg(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:ver"))):
    e = obtener_existencia(db, ctx, id_)
    salida = BytesIO()
    segno.make(url_qr(db, e), error="m").save(salida, kind="svg", scale=4, border=2)
    return Response(salida.getvalue(), media_type="image/svg+xml")


CAMPOS_ETIQUETA = {
    "codigo_publico": lambda e: e.codigo_publico,
    "producto_codigo": lambda e: e.producto.codigo,
    "producto_nombre": lambda e: e.producto.nombre,
    "lote": lambda e: f"Lote: {e.lote.codigo}" if e.lote else None,
    "fecha_ingreso": lambda e: f"Ingreso: {e.fecha_ingreso:%d-%m-%Y}",
    "fecha_vencimiento": lambda e: f"Vence: {e.lote.fecha_vencimiento:%d-%m-%Y}" if e.lote and e.lote.fecha_vencimiento else None,
    "cantidad": lambda e: f"Cantidad: {e.cantidad_inicial.normalize():f} {e.unidad.codigo}",
    "unidad": lambda e: None,  # se imprime junto a la cantidad
    "bodega": lambda e: f"Bodega: {e.bodega.nombre}",
    "ubicacion": lambda e: f"Ubicacion: {e.ubicacion.codigo_completo}" if e.ubicacion else None,
}


def generar_pdf_etiquetas(db: Session, existencias: list[Existencia], plantilla: PlantillaEtiqueta) -> bytes:
    """Una etiqueta por pagina, del tamano de la plantilla. La cantidad impresa es la inicial; el saldo se consulta escaneando."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    ancho, alto = plantilla.ancho_mm * mm, plantilla.alto_mm * mm
    salida = BytesIO()
    pdf = canvas.Canvas(salida, pagesize=(ancho, alto))
    campos = plantilla.campos or list(CAMPOS_ETIQUETA)
    margen = 3 * mm
    lado = min(alto - 2 * margen, ancho * 0.42)
    for e in existencias:
        x_texto = margen
        if "qr" in campos:
            w = QrCodeWidget(url_qr(db, e), barLevel="M")
            b = w.getBounds()
            dibujo = Drawing(lado, lado, transform=[lado / (b[2] - b[0]), 0, 0, lado / (b[3] - b[1]), 0, 0])
            dibujo.add(w)
            renderPDF.draw(dibujo, pdf, margen, alto - margen - lado)
            x_texto = margen + lado + 2 * mm
        y = alto - margen - 4 * mm
        maximo = ancho - x_texto - margen
        for campo in campos:
            if campo == "qr" or campo not in CAMPOS_ETIQUETA:
                continue
            texto = CAMPOS_ETIQUETA[campo](e)
            if not texto:
                continue
            destacado = campo in ("codigo_publico", "producto_nombre")
            fuente, tam = ("Helvetica-Bold", 10 if campo == "codigo_publico" else 9) if destacado else ("Helvetica", 7.5)
            while pdf.stringWidth(texto, fuente, tam) > maximo and len(texto) > 4:
                texto = texto[:-2]
            pdf.setFont(fuente, tam)
            pdf.drawString(x_texto, y, texto)
            y -= (tam + 2.5)
            if y < margen:
                break
        pdf.showPage()
    pdf.save()
    return salida.getvalue()


@router.get("/etiquetas")
def etiquetas(existencias: str = Query(..., description="Ids separados por coma"), plantilla_id: int | None = None,
              db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("inventario:editar"))):
    try:
        ids = [int(x) for x in existencias.split(",") if x.strip()]
    except ValueError as err:
        raise ErrorNegocio("IDS", "Lista de existencias no valida.") from err
    if not ids or len(ids) > 500:
        raise ErrorNegocio("IDS", "Indique entre 1 y 500 existencias.")
    items = [obtener_existencia(db, ctx, i) for i in ids]
    plantilla = db.get(PlantillaEtiqueta, plantilla_id) if plantilla_id else \
        db.scalar(select(PlantillaEtiqueta).order_by(PlantillaEtiqueta.predeterminada.desc(), PlantillaEtiqueta.id))
    if not plantilla:
        raise no_encontrado("Plantilla de etiqueta")
    pdf = generar_pdf_etiquetas(db, items, plantilla)
    for e in items:
        e.etiquetas_impresas += 1
    auditar(db, ctx, "etiqueta", ",".join(str(i) for i in ids[:20]), "IMPRIMIR", nuevo={"cantidad": len(ids)})
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="etiquetas.pdf"'})


__all__ = ["router", "json_valor"]
