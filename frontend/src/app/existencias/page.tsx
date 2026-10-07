"use client";

import { Printer } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Boton, Cargando, Encabezado, Entrada, Estado, Interruptor, Paginacion, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { abrirArchivo } from "@/lib/api";
import { clp, diasDesde, fecha, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Existencias() {
  const router = useRouter();
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const [f, setF] = useState<Record<string, any>>({ con_stock: true });
  const [pagina, setPagina] = useState(1);
  const [marcadas, setMarcadas] = useState<Set<number>>(new Set());
  const cat = useDatos("/catalogos");
  const { datos, cargando } = useDatos("/existencias", { ...f, pagina, tam: 50 });
  const { ejecutar, ocupado } = useAccion();
  const claveF = JSON.stringify(f);
  useEffect(() => setPagina(1), [claveF]);
  const alternar = (id: number) => setMarcadas((m) => { const n = new Set(m); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const items: any[] = datos?.items ?? [];
  const todas = items.length > 0 && items.every((e) => marcadas.has(e.id));

  return (
    <>
      <Encabezado titulo="Existencias y QR" descripcion="Cada existencia es una cantidad física concreta: tiene su lote, ubicación, fecha de ingreso, costo y QR propios.">
        {puede("inventario:editar") && (
          <Boton icono={<Printer className="size-4" />} disabled={!marcadas.size} cargando={ocupado} onClick={() => ejecutar(() => abrirArchivo("/etiquetas", { existencias: [...marcadas].join(",") }))}>
            Imprimir QR ({marcadas.size})
          </Boton>
        )}
      </Encabezado>
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-5">
          <Entrada placeholder="Código INV, producto o lote…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2" />
          <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} />
          <Interruptor valor={!!f.con_stock} onCambio={(v) => setF({ ...f, con_stock: v })} etiqueta="Solo con stock" />
          <Interruptor valor={!!f.sin_ubicacion} onCambio={(v) => setF({ ...f, sin_ubicacion: v || undefined })} etiqueta="Sin ubicación" />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={items}
            onFila={(e) => router.push(`/existencia/?id=${e.id}`)}
            columnas={[
              { clave: "sel", titulo: "", render: (e) => <input type="checkbox" aria-label={`Seleccionar ${e.codigo_publico}`} className="size-4 accent-emerald-600" checked={marcadas.has(e.id)} onClick={(ev) => ev.stopPropagation()} onChange={() => alternar(e.id)} /> },
              { clave: "codigo_publico", titulo: "Existencia", render: (e) => <span className="cifra font-medium">{e.codigo_publico}</span> },
              { clave: "producto", titulo: "Producto", render: (e) => <><span className="font-medium text-slate-900">{e.producto}</span><span className="block text-xs text-slate-500">Lote {e.lote ?? "—"}</span></> },
              { clave: "ubicacion", titulo: "Ubicación", ocultarMovil: true, render: (e) => e.ubicacion ?? <span className="text-amber-700">{e.bodega} · sin ubicar</span> },
              { clave: "fecha_ingreso", titulo: "Ingreso", ocultarMovil: true, render: (e) => <>{fecha(e.fecha_ingreso)}<span className="block text-xs text-slate-500">{diasDesde(e.fecha_ingreso)} días</span></> },
              { clave: "fecha_vencimiento", titulo: "Vence", ocultarMovil: true, render: (e) => fecha(e.fecha_vencimiento) },
              { clave: "cantidad_fisica", titulo: "Cantidad", alinear: "derecha", render: (e) => <><b>{num(e.cantidad_fisica)}</b> <span className="text-xs text-slate-500">/ {num(e.cantidad_inicial)} {e.unidad}</span></> },
              ...(costos ? [{ clave: "costo_unitario", titulo: "Costo unit.", alinear: "derecha" as const, ocultarMovil: true, render: (e: any) => clp(e.costo_unitario, 2) }, { clave: "valor_disponible", titulo: "Valor", alinear: "derecha" as const, ocultarMovil: true, render: (e: any) => clp(e.valor_disponible) }] : []),
              { clave: "estado", titulo: "Estado", render: (e) => <Estado valor={e.lote_estado && e.lote_estado !== "DISPONIBLE" && e.estado === "DISPONIBLE" ? e.lote_estado : e.estado} /> },
            ]}
          />
        )}
        <div className="flex items-center justify-between border-t border-slate-100">
          <label className="flex items-center gap-2 px-4 text-xs text-slate-600">
            <input type="checkbox" className="size-4 accent-emerald-600" checked={todas} onChange={() => setMarcadas((m) => { const n = new Set(m); items.forEach((e) => (todas ? n.delete(e.id) : n.add(e.id))); return n; })} />
            Seleccionar página
          </label>
          {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
        </div>
      </Tarjeta>
    </>
  );
}
