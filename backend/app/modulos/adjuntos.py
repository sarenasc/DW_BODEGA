"""Archivos adjuntos (factura, guia, foto, certificado, ficha tecnica, hoja de seguridad) en almacenamiento local."""
import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.auditoria import auditar
from app.core.config import ajustes
from app.core.db import get_db
from app.core.dependencias import Contexto, contexto, requiere
from app.core.errores import ErrorNegocio, no_encontrado
from app.core.util import a_dict
from app.modelos import Adjunto, Usuario

router = APIRouter(prefix="/api", tags=["Adjuntos"])
TIPOS = ("FACTURA", "GUIA", "FOTO", "CERTIFICADO", "FICHA_TECNICA", "HOJA_SEGURIDAD", "OTRO")
ENTIDADES = ("documento", "producto", "lote", "existencia", "proceso", "prestamo", "conteo", "proveedor")
EXTENSIONES = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
               ".webp": "image/webp", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
               ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".csv": "text/csv",
               ".txt": "text/plain"}
MAXIMO = 15 * 1024 * 1024


@router.get("/adjuntos")
def listar(entidad: str, entidad_id: int, db: Session = Depends(get_db), ctx: Contexto = Depends(contexto)):
    nombres = dict(db.execute(select(Usuario.id, Usuario.nombre)).all())
    return [a_dict(a, excluir=("ruta",), usuario=nombres.get(a.usuario_id)) for a in db.scalars(select(Adjunto).where(
        Adjunto.empresa_id == ctx.empresa_id, Adjunto.entidad == entidad, Adjunto.entidad_id == entidad_id).order_by(Adjunto.id))]


@router.post("/adjuntos", status_code=201)
async def subir(entidad: str = Form(...), entidad_id: int = Form(...), tipo: str = Form("OTRO"), descripcion: str | None = Form(None),
                archivo: UploadFile = File(...), db: Session = Depends(get_db),
                ctx: Contexto = Depends(requiere("adjuntos:administrar"))):
    if entidad not in ENTIDADES:
        raise ErrorNegocio("ENTIDAD", f"Entidad no valida. Opciones: {', '.join(ENTIDADES)}")
    if tipo not in TIPOS:
        raise ErrorNegocio("TIPO", f"Tipo no valido. Opciones: {', '.join(TIPOS)}")
    nombre = Path(archivo.filename or "archivo").name  # descarta cualquier ruta enviada por el cliente
    ext = Path(nombre).suffix.lower()
    if ext not in EXTENSIONES:
        raise ErrorNegocio("EXTENSION", f"Tipo de archivo no permitido. Admitidos: {', '.join(sorted(EXTENSIONES))}")
    contenido = await archivo.read(MAXIMO + 1)
    if len(contenido) > MAXIMO:
        raise ErrorNegocio("TAMANO", "El archivo supera los 15 MB.", 413)
    if not contenido:
        raise ErrorNegocio("VACIO", "El archivo esta vacio.")
    if ext == ".pdf" and not contenido.startswith(b"%PDF"):
        raise ErrorNegocio("CONTENIDO", "El archivo no es un PDF valido.")
    # El nombre en disco lo genera el servidor: el nombre original solo se guarda como dato.
    relativo = Path(entidad) / f"{uuid.uuid4().hex}{ext}"
    destino = ajustes().archivos / relativo
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    a = Adjunto(empresa_id=ctx.empresa_id, entidad=entidad, entidad_id=entidad_id, tipo=tipo, nombre_archivo=nombre[:255],
                ruta=relativo.as_posix(), mime=EXTENSIONES[ext], tamano=len(contenido), sha256=hashlib.sha256(contenido).hexdigest(),
                usuario_id=ctx.usuario.id, descripcion=descripcion)
    db.add(a)
    db.flush()
    auditar(db, ctx, "adjunto", a.id, "SUBIR", nuevo={"entidad": entidad, "entidad_id": entidad_id, "nombre": nombre})
    return a_dict(a, excluir=("ruta",))


def _obtener(db: Session, ctx: Contexto, id_: int) -> Adjunto:
    a = db.get(Adjunto, id_)
    if not a or a.empresa_id != ctx.empresa_id:
        raise no_encontrado("Adjunto")
    return a


@router.get("/adjuntos/{id_}/descargar")
def descargar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(contexto)):
    a = _obtener(db, ctx, id_)
    raiz = ajustes().archivos.resolve()
    ruta = (raiz / a.ruta).resolve()
    if raiz not in ruta.parents or not ruta.exists():
        raise no_encontrado("Archivo")
    return FileResponse(ruta, media_type=a.mime, filename=a.nombre_archivo)


@router.delete("/adjuntos/{id_}")
def eliminar(id_: int, db: Session = Depends(get_db), ctx: Contexto = Depends(requiere("adjuntos:administrar"))):
    a = _obtener(db, ctx, id_)
    ruta = (ajustes().archivos / a.ruta).resolve()
    auditar(db, ctx, "adjunto", a.id, "ELIMINAR", anterior={"nombre": a.nombre_archivo, "entidad": a.entidad,
                                                           "entidad_id": a.entidad_id, "sha256": a.sha256})
    db.delete(a)
    db.flush()
    ruta.unlink(missing_ok=True)
    return {"ok": True}
