"use client";

import { Undo2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Boton, Cargando, Encabezado, Entrada, Insignia, Paginacion, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, fechaHora, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

const NO_ANULABLES = ["INGRESO", "ANULACION", "TRASLADO_SALIDA", "TRASLADO_ENTRADA", "FRACCIONAMIENTO_SALIDA", "FRACCIONAMIENTO_ENTRADA"];

export default function Movimientos() {
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const [f, setF] = useState<Record<string, any>>({});
  const [pagina, setPagina] = useState(1);
  const cat = useDatos("/catalogos");
  const tipos = useDatos("/tipos-movimiento", { tam: 100 });
  const { datos, cargando, recargar } = useDatos("/movimientos", { ...f, pagina, tam: 50 });
  const { ejecutar } = useAccion();
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave]);

  const anular = (m: any) => {
    const motivo = prompt(`Anular ${m.tipo_nombre.toLowerCase()} de ${num(Math.abs(m.cantidad))} ${m.unidad} (${m.producto}).\nEl movimiento no se elimina: se genera su inverso.\n\nMotivo:`);
    if (motivo?.trim()) ejecutar(async () => { await api.post(`/movimientos/${m.id}/anular`, { motivo }); recargar(); }, "Movimiento anulado");
  };

  return (
    <>
      <Encabezado titulo="Movimientos de inventario" descripcion="Libro inmutable: los movimientos no se editan ni se borran; se corrigen con una anulación (movimiento inverso) o un ajuste." />
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-6">
          <Entrada placeholder="Producto o existencia…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2" />
          <Selector vacio="Todos los tipos" value={f.tipo ?? ""} onChange={(e) => setF({ ...f, tipo: e.target.value })} opciones={(tipos.datos?.items ?? []).map((t: any) => ({ valor: t.codigo, texto: t.nombre }))} />
          <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} />
          <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
          <Entrada type="date" aria-label="Hasta" value={f.hasta ? f.hasta.slice(0, 10) : ""} onChange={(e) => setF({ ...f, hasta: e.target.value ? `${e.target.value}T23:59:59` : "" })} />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            columnas={[
              { clave: "fecha", titulo: "Fecha", render: (m) => fechaHora(m.fecha) },
              { clave: "tipo_nombre", titulo: "Tipo", render: (m) => <><Insignia tono={m.tipo === "ANULACION" ? "rojo" : m.cantidad < 0 ? "azul" : "verde"}>{m.tipo_nombre}</Insignia>{m.anulado && <span className="ml-1"><Insignia tono="rojo">Anulado</Insignia></span>}</> },
              { clave: "producto", titulo: "Producto", render: (m) => <><span className="font-medium text-slate-900">{m.producto}</span><Link href={`/existencia/?id=${m.existencia_id}`} className="block text-xs text-marca-700 hover:underline">{m.codigo_publico} · lote {m.lote ?? "—"}</Link></> },
              { clave: "cantidad", titulo: "Cantidad", alinear: "derecha", render: (m) => <span className={m.cantidad < 0 ? "text-rose-700" : "text-emerald-700"}>{m.cantidad > 0 ? "+" : ""}{num(m.cantidad)} {m.unidad}</span> },
              ...(costos ? [{ clave: "costo_unitario", titulo: "Costo unit.", alinear: "derecha" as const, ocultarMovil: true, render: (m: any) => clp(m.costo_unitario, 2) }, { clave: "costo_total", titulo: "Costo total", alinear: "derecha" as const, ocultarMovil: true, render: (m: any) => clp(m.costo_total) }] : []),
              { clave: "bodega", titulo: "Bodega", ocultarMovil: true },
              { clave: "proceso", titulo: "Proceso", ocultarMovil: true, render: (m) => (m.proceso_id ? <Link className="text-marca-700 hover:underline" href={`/procesos/detalle/?id=${m.proceso_id}`}>{m.proceso}</Link> : "—") },
              { clave: "documento", titulo: "Documento", ocultarMovil: true, render: (m) => (m.documento_id ? <Link className="text-marca-700 hover:underline" href={`/documentos/detalle/?id=${m.documento_id}`}>{m.documento}</Link> : "—") },
              { clave: "usuario", titulo: "Usuario", ocultarMovil: true },
              { clave: "motivo_texto", titulo: "Motivo", ocultarMovil: true, render: (m) => <span className="block max-w-48 truncate" title={m.motivo_texto ?? m.observacion ?? ""}>{m.motivo_texto ?? m.observacion ?? "—"}</span> },
              ...(puede("movimientos:anular") ? [{ clave: "x", titulo: "", render: (m: any) => !m.anulado && !NO_ANULABLES.includes(m.tipo) && <Boton tam="sm" variante="fantasma" aria-label="Anular" title="Anular" onClick={() => anular(m)}><Undo2 className="size-4 text-rose-600" /></Boton> }] : []),
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>
    </>
  );
}
