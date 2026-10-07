"use client";

// Trazabilidad visual: hacia adelante (lote -> procesos) y hacia atras (proceso -> documentos).

import { ArrowRight, Boxes, ChevronRight, Factory, FileText, GitBranch, Layers, Repeat } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { BuscarSelect, SelectorExistencia, SelectorProceso, SelectorProducto } from "@/components/Selectores";
import { Aviso, Cargando, cx, Encabezado, Estado, Insignia, Pestanas, Tarjeta } from "@/components/ui";
import { clp, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

const META: Record<string, { titulo: string; icono: React.ComponentType<{ className?: string }>; color: string }> = {
  documento: { titulo: "Documentos de ingreso", icono: FileText, color: "border-slate-400" },
  lote: { titulo: "Lotes", icono: Layers, color: "border-violet-400" },
  existencia: { titulo: "Existencias (QR)", icono: Boxes, color: "border-sky-400" },
  movimiento: { titulo: "Movimientos y consumos", icono: Repeat, color: "border-amber-400" },
  proceso: { titulo: "Procesos", icono: Factory, color: "border-emerald-500" },
};

export default function Trazabilidad() {
  const router = useRouter();
  const { puede } = useSesion();
  const lote = useParametro("lote");
  const proceso = useParametro("proceso");
  const existencia = useParametro("existencia");
  const producto = useParametro("producto");
  const ruta = lote ? `/trazabilidad/lote/${lote}` : proceso ? `/trazabilidad/proceso/${proceso}` : existencia ? `/trazabilidad/existencia/${existencia}` : null;
  const { datos, cargando, error } = useDatos(ruta);
  const lotesProducto = useDatos<any[]>(producto ? `/trazabilidad/producto/${producto}` : null);
  const [activo, setActivo] = useState<string | null>(null);
  const [vista, setVista] = useState("cadena");
  const [buscar, setBuscar] = useState("lote");

  // Nodos conectados (en ambos sentidos) con el nodo bajo el cursor: la cadena completa de ese elemento.
  const conectados = useMemo(() => {
    if (!datos || !activo) return null;
    const ady = new Map<string, string[]>();
    for (const { origen, destino } of datos.enlaces) {
      ady.set(origen, [...(ady.get(origen) ?? []), `>${destino}`]);
      ady.set(destino, [...(ady.get(destino) ?? []), `<${origen}`]);
    }
    const vistos = new Set([activo]);
    const recorrer = (inicio: string, sentido: string) => {
      const pila = [inicio];
      while (pila.length) for (const v of ady.get(pila.pop()!) ?? []) if (v[0] === sentido && !vistos.has(v.slice(1))) { vistos.add(v.slice(1)); pila.push(v.slice(1)); }
    };
    recorrer(activo, ">");
    recorrer(activo, "<");
    return vistos;
  }, [datos, activo]);

  const haciaAtras = !!proceso;
  const columnas = datos ? (haciaAtras ? [...datos.columnas].reverse() : datos.columnas) : [];

  return (
    <>
      <Encabezado titulo="Trazabilidad" descripcion={haciaAtras ? "Hacia atrás: proceso → consumos → existencias → lotes → ingresos → documentos." : "Hacia adelante: documento → lote → existencias → movimientos → consumos → procesos."} />
      <Tarjeta className="mb-3">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
            {[["lote", "Lote"], ["proceso", "Proceso"], ["existencia", "Existencia / QR"], ["producto", "Producto"]].map(([v, t]) => (
              <button key={v} onClick={() => setBuscar(v)} className={cx("rounded-md px-3 py-1.5 text-sm font-medium", buscar === v ? "bg-white text-slate-900 shadow-sm" : "text-slate-600")}>{t}</button>
            ))}
          </div>
          <div className="min-w-64 flex-1">
            {buscar === "lote" && <BuscarSelect ruta="/lotes" valor={null} onCambio={(l: any) => l && router.push(`/trazabilidad/?lote=${l.id}`)} placeholder="Buscar lote interno…" titulo={(l: any) => l.codigo} detalle={(l: any) => `${l.producto} · ${l.estado} · ${num(l.cantidad_disponible)} ${l.unidad}`} />}
            {buscar === "proceso" && <SelectorProceso valor={null} estado="" onCambio={(p) => p && router.push(`/trazabilidad/?proceso=${p.id}`)} />}
            {buscar === "existencia" && puede("inventario:ver") && <SelectorExistencia valor={null} onCambio={(e) => e && router.push(`/trazabilidad/?existencia=${e.id}`)} />}
            {buscar === "producto" && <SelectorProducto valor={null} onCambio={(p) => p && router.push(`/trazabilidad/?producto=${p.id}`)} />}
          </div>
        </div>
      </Tarjeta>

      {producto && lotesProducto.datos && (
        <Tarjeta titulo="Lotes del producto: elija uno para trazar">
          <div className="flex flex-wrap gap-2">
            {lotesProducto.datos.length === 0 && <p className="text-sm text-slate-500">Este producto no tiene lotes.</p>}
            {lotesProducto.datos.map((l) => (
              <Link key={l.id} href={`/trazabilidad/?lote=${l.id}`} className="rounded-lg border border-slate-200 px-3 py-2 text-sm hover:border-marca-500">
                <b className="cifra">{l.codigo}</b> <Estado valor={l.estado} />
                <span className="block text-xs text-slate-500">Ingreso {fecha(l.fecha_ingreso)}{l.fecha_vencimiento && ` · vence ${fecha(l.fecha_vencimiento)}`}</span>
              </Link>
            ))}
          </div>
        </Tarjeta>
      )}
      {error && <Aviso tipo="error">{error}</Aviso>}
      {cargando && <Cargando />}
      {!ruta && !producto && <Aviso><GitBranch className="mr-1 inline size-4" />Busque un lote, un proceso o una existencia para ver su cadena completa. También puede llegar aquí desde la ficha de cualquiera de ellos.</Aviso>}

      {datos && (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            {columnas.map((c: any, i: number) => (
              <span key={c.tipo} className="inline-flex items-center gap-2">
                {i > 0 && <ArrowRight className="size-4 text-slate-400" />}
                <Insignia tono="gris">{datos.resumen[c.tipo]} {META[c.tipo].titulo.toLowerCase()}</Insignia>
              </span>
            ))}
          </div>
          <Pestanas valor={vista} onCambio={setVista} opciones={[{ valor: "cadena", texto: "Cadena" }, { valor: "tiempo", texto: "Línea de tiempo", contador: datos.linea_tiempo.length }, ...(datos.productos ? [{ valor: "productos", texto: "Productos consumidos", contador: datos.productos.length }] : [])]} />

          {vista === "cadena" && (
            <div className="overflow-x-auto pb-2">
              <div className="flex min-w-max items-start gap-2" onMouseLeave={() => setActivo(null)}>
                {columnas.map((c: any, i: number) => {
                  const m = META[c.tipo];
                  return (
                    <div key={c.tipo} className="flex items-start gap-2">
                      {i > 0 && <ChevronRight className="mt-9 size-6 shrink-0 text-slate-300" />}
                      <section className="w-64 shrink-0">
                        <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wide text-slate-500 uppercase"><m.icono className="size-4" /> {m.titulo}</h2>
                        <ul className="space-y-2">
                          {c.nodos.map((n: any) => {
                            const tenue = conectados && !conectados.has(n.clave);
                            const cuerpo = (
                              <>
                                <span className="flex items-start justify-between gap-2">
                                  <b className="cifra text-sm break-all text-slate-900">{n.titulo}</b>
                                  {n.estado && c.tipo !== "movimiento" && <Estado valor={n.estado} />}
                                </span>
                                <span className="mt-0.5 block text-xs text-slate-600">{n.detalle}</span>
                                {n.costo_total != null && c.tipo === "movimiento" && <span className="cifra mt-0.5 block text-xs font-medium text-slate-700">{clp(Math.abs(n.costo_total))}</span>}
                                {n.anula_a && <span className="mt-1 block"><Insignia tono="rojo">Anula un movimiento</Insignia></span>}
                              </>
                            );
                            const clase = cx("block rounded-lg border-l-4 bg-white p-2.5 shadow-sm ring-1 ring-slate-200 transition", m.color, n.clave === datos.raiz && "ring-2 ring-marca-500", tenue && "opacity-25", n.enlace && "hover:ring-marca-500");
                            return (
                              <li key={n.clave} onMouseEnter={() => setActivo(n.clave)} onFocus={() => setActivo(n.clave)}>
                                {n.enlace ? <Link href={n.enlace} className={clase} title="Abrir">{cuerpo}</Link> : <div className={clase} tabIndex={0}>{cuerpo}</div>}
                              </li>
                            );
                          })}
                        </ul>
                      </section>
                    </div>
                  );
                })}
              </div>
              <p className="mt-3 text-xs text-slate-500">Pase el cursor sobre un elemento para resaltar su cadena completa. Haga clic para abrirlo.</p>
            </div>
          )}

          {vista === "tiempo" && (
            <Tarjeta>
              <ol className="relative ml-2 space-y-4 border-l-2 border-slate-200 pl-5">
                {datos.linea_tiempo.length === 0 && <li className="text-sm text-slate-500">Sin eventos.</li>}
                {datos.linea_tiempo.map((ev: any, i: number) => (
                  <li key={i} className="relative">
                    <span className={cx("absolute top-1 -left-[27px] size-3 rounded-full ring-4 ring-white", ev.tipo === "INGRESO" ? "bg-emerald-500" : ev.tipo === "ANULACION" ? "bg-rose-500" : ev.tipo.startsWith("TRASLADO") || ev.tipo.startsWith("FRACC") ? "bg-violet-500" : "bg-amber-500")} />
                    <p className="text-xs text-slate-500">{fechaHora(ev.fecha)} · {ev.usuario ?? "Sistema"}</p>
                    <p className="text-sm font-medium text-slate-900">{ev.titulo}</p>
                    <p className="text-sm text-slate-600">{ev.detalle}{ev.costo_total != null && ` · ${clp(Math.abs(ev.costo_total))}`}</p>
                    {ev.motivo && <p className="text-xs text-slate-500">Motivo: {ev.motivo}</p>}
                  </li>
                ))}
              </ol>
            </Tarjeta>
          )}

          {vista === "productos" && datos.productos && (
            <Tarjeta sinRelleno>
              <table className="tabla w-full">
                <thead><tr><th>Producto</th><th className="!text-right">Cantidad</th><th className="!text-right">Costo</th><th>Lotes utilizados</th></tr></thead>
                <tbody>
                  {datos.productos.map((p: any) => (
                    <tr key={p.producto_id}>
                      <td className="font-medium">{p.producto}</td>
                      <td className="cifra text-right">{num(p.cantidad)} {p.unidad}</td>
                      <td className="cifra text-right">{clp(p.costo)}</td>
                      <td>{p.lotes.join(", ") || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Tarjeta>
          )}
        </>
      )}
    </>
  );
}
