"use client";

import { Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type Params } from "@/lib/api";
import { num } from "@/lib/formato";
import { cx } from "./ui";

type Props<T> = {
  ruta: string;
  params?: Params;
  valor: T | null;
  onCambio: (item: T | null) => void;
  titulo: (item: T) => string;
  detalle?: (item: T) => string;
  placeholder?: string;
  autoFocus?: boolean;
};

/** Selector con busqueda en el servidor (productos, existencias, procesos...). */
export function BuscarSelect<T extends { id: number }>({ ruta, params, valor, onCambio, titulo, detalle, placeholder = "Buscar…", autoFocus }: Props<T>) {
  const [q, setQ] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [items, setItems] = useState<T[]>([]);
  const caja = useRef<HTMLDivElement>(null);
  const clave = JSON.stringify(params ?? {});

  useEffect(() => {
    if (!abierto) return;
    const t = setTimeout(() => {
      api
        .get(ruta, { q, tam: 20, ...JSON.parse(clave) })
        .then((r) => setItems(Array.isArray(r) ? r : r.items))
        .catch(() => setItems([]));
    }, 200);
    return () => clearTimeout(t);
  }, [q, abierto, ruta, clave]);

  useEffect(() => {
    const fuera = (e: MouseEvent) => !caja.current?.contains(e.target as Node) && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, []);

  if (valor)
    return (
      <div className="campo flex !h-auto min-h-10 items-center justify-between gap-2 py-1.5">
        <span className="min-w-0">
          <span className="block truncate font-medium">{titulo(valor)}</span>
          {detalle && <span className="block truncate text-xs text-slate-500">{detalle(valor)}</span>}
        </span>
        <button type="button" aria-label="Quitar selección" onClick={() => onCambio(null)} className="rounded p-1 text-slate-500 hover:bg-slate-100">
          <X className="size-4" />
        </button>
      </div>
    );
  return (
    <div ref={caja} className="relative">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
      <input className="campo pl-9" value={q} placeholder={placeholder} autoFocus={autoFocus} onFocus={() => setAbierto(true)} onChange={(e) => { setQ(e.target.value); setAbierto(true); }} />
      {abierto && (
        <ul className="aparecer absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-xl">
          {items.length === 0 && <li className="px-3 py-2 text-sm text-slate-500">Sin resultados.</li>}
          {items.map((i) => (
            <li key={i.id}>
              <button type="button" onClick={() => { onCambio(i); setAbierto(false); setQ(""); }} className={cx("block w-full px-3 py-2 text-left hover:bg-slate-50")}>
                <span className="block truncate text-sm font-medium text-slate-900">{titulo(i)}</span>
                {detalle && <span className="block truncate text-xs text-slate-500">{detalle(i)}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SelectorProducto({ valor, onCambio, autoFocus }: { valor: any; onCambio: (p: any) => void; autoFocus?: boolean }) {
  return <BuscarSelect ruta="/productos" params={{ activo: true }} valor={valor} onCambio={onCambio} autoFocus={autoFocus} placeholder="Buscar producto por nombre o código…" titulo={(p: any) => p.nombre} detalle={(p: any) => `${p.codigo} · ${p.familia} › ${p.subfamilia} · ${p.unidad_base}`} />;
}

export function SelectorExistencia({ valor, onCambio, bodegaId, productoId }: { valor: any; onCambio: (e: any) => void; bodegaId?: number | string; productoId?: number | string }) {
  return (
    <BuscarSelect
      ruta="/existencias"
      params={{ bodega_id: bodegaId, producto_id: productoId, con_stock: true }}
      valor={valor}
      onCambio={onCambio}
      placeholder="Buscar existencia por código INV, producto o lote…"
      titulo={(e: any) => `${e.codigo_publico} · ${e.producto}`}
      detalle={(e: any) => `Lote ${e.lote ?? "—"} · ${num(e.cantidad_fisica)} ${e.unidad} · ${e.ubicacion ?? e.bodega} · ingreso ${new Date(e.fecha_ingreso).toLocaleDateString("es-CL")}`}
    />
  );
}

export function SelectorProceso({ valor, onCambio, estado = "ABIERTO" }: { valor: any; onCambio: (p: any) => void; estado?: string }) {
  return <BuscarSelect ruta="/procesos" params={{ estado }} valor={valor} onCambio={onCambio} placeholder="Buscar proceso…" titulo={(p: any) => p.codigo} detalle={(p: any) => [p.especie, p.variedad, p.productor].filter(Boolean).join(" · ")} />;
}
