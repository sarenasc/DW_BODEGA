"use client";

import { Download, Paperclip, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { abrirArchivo, api } from "@/lib/api";
import { etiqueta, fecha, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";
import { Boton, Selector, Tarjeta, useAccion } from "./ui";

const TIPOS = ["FACTURA", "GUIA", "FOTO", "CERTIFICADO", "FICHA_TECNICA", "HOJA_SEGURIDAD", "OTRO"];

/** Archivos adjuntos de cualquier entidad (documento, producto, lote, proceso...). */
export function Adjuntos({ entidad, id, titulo = "Archivos adjuntos", className }: { entidad: string; id: number; titulo?: string; className?: string }) {
  const { puede } = useSesion();
  const { datos, recargar } = useDatos("/adjuntos", { entidad, entidad_id: id });
  const [tipo, setTipo] = useState(entidad === "producto" ? "FICHA_TECNICA" : entidad === "documento" ? "FACTURA" : "OTRO");
  const archivo = useRef<HTMLInputElement>(null);
  const { ejecutar, ocupado } = useAccion();
  const editable = puede("adjuntos:administrar");

  const subir = (f: File | undefined) =>
    f &&
    ejecutar(async () => {
      const datosForm = new FormData();
      datosForm.set("entidad", entidad);
      datosForm.set("entidad_id", String(id));
      datosForm.set("tipo", tipo);
      datosForm.set("archivo", f);
      await api.subir("/adjuntos", datosForm);
      if (archivo.current) archivo.current.value = "";
      recargar();
    }, "Archivo adjuntado");

  return (
    <Tarjeta titulo={titulo} className={className}>
      <ul className="space-y-1.5">
        {(datos ?? []).length === 0 && <li className="text-sm text-slate-500">Sin archivos.</li>}
        {(datos ?? []).map((a: any) => (
          <li key={a.id} className="flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <Paperclip className="size-4 shrink-0 text-slate-400" />
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium text-slate-800">{a.nombre_archivo}</span>
              <span className="block text-xs text-slate-500">
                {etiqueta(a.tipo)} · {num(a.tamano / 1024, 0)} KB · {fecha(a.creado_en)} · {a.usuario}
              </span>
            </span>
            <button aria-label="Descargar" onClick={() => ejecutar(() => abrirArchivo(`/adjuntos/${a.id}/descargar`, undefined, a.mime === "application/pdf" ? undefined : a.nombre_archivo))} className="rounded p-1.5 text-slate-600 hover:bg-slate-200">
              <Download className="size-4" />
            </button>
            {editable && (
              <button aria-label="Eliminar" onClick={() => confirm(`¿Eliminar ${a.nombre_archivo}?`) && ejecutar(async () => { await api.del(`/adjuntos/${a.id}`); recargar(); })} className="rounded p-1.5 text-rose-600 hover:bg-rose-50">
                <Trash2 className="size-4" />
              </button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3">
          <Selector aria-label="Tipo de archivo" value={tipo} onChange={(e) => setTipo(e.target.value)} opciones={TIPOS.map((t) => ({ valor: t, texto: etiqueta(t) }))} />
          <input ref={archivo} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.docx,.csv,.txt" onChange={(e) => subir(e.target.files?.[0])} />
          <Boton variante="secundario" cargando={ocupado} icono={<Upload className="size-4" />} onClick={() => archivo.current?.click()}>
            Adjuntar
          </Boton>
        </div>
      )}
    </Tarjeta>
  );
}
