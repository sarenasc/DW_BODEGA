"use client";

import { num } from "@/lib/formato";

/** Lo que hay en una ubicacion (o en un rack completo): productos, lotes, cantidad, vencimiento, valor y capacidad libre. */
export function ContenidoUbicacion({ datos }: { datos: any }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">Existencias</p>
          <p className="cifra text-lg font-semibold">{datos.existencias.length}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">Valor</p>
          <p className="cifra text-lg font-semibold">{datos.valor != null ? `$${num(datos.valor, 0)}` : "—"}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">Capacidad libre</p>
          <p className="cifra text-lg font-semibold">{num(datos.capacidad_disponible)}</p>
        </div>
      </div>
      {datos.existencias.length === 0 && <p className="py-4 text-center text-sm text-slate-500">Ubicación vacía.</p>}
      <ul className="space-y-1.5">
        {datos.existencias.map((e: any) => (
          <li key={e.id}>
            <a href={`/existencia/?id=${e.id}`} className="block rounded-lg border border-slate-200 p-2.5 text-sm hover:border-marca-500">
              <span className="flex justify-between gap-2">
                <b className="truncate">{e.producto}</b>
                <span className="cifra shrink-0">
                  {num(e.cantidad)} {e.unidad}
                </span>
              </span>
              <span className="mt-0.5 block text-xs text-slate-500">
                {e.codigo_publico} · Lote {e.lote ?? "—"} · Ingreso {new Date(e.fecha_ingreso).toLocaleDateString("es-CL")}
                {e.fecha_vencimiento && ` · Vence ${new Date(e.fecha_vencimiento + "T12:00:00").toLocaleDateString("es-CL")}`}
                {e.ubicacion && ` · ${e.ubicacion}`}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
