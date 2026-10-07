"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Cargando, Encabezado, Entrada, Estado, Insignia, Interruptor, Pestanas, Selector, Tabla, Tarjeta } from "@/components/ui";
import { clp, fecha, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function Stock() {
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const bajoInicial = useParametro("bajo");
  const [agrupar, setAgrupar] = useState("producto");
  const [f, setF] = useState<Record<string, any>>({});
  const [bajo, setBajo] = useState(false);
  useEffect(() => setBajo(bajoInicial === "1"), [bajoInicial]);
  const cat = useDatos("/catalogos");
  const { datos, cargando, error } = useDatos("/stock", { agrupar, ...f, solo_bajo_minimo: bajo && agrupar === "producto" ? true : undefined });
  const op = (l: any[] | undefined) => (l ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }));
  const total = (datos ?? []).reduce((s: number, x: any) => s + (x.valor_inventario ?? 0), 0);

  return (
    <>
      <Encabezado titulo="Stock" descripcion="Stock físico − reservado = disponible. Comprometido incluye reservas activas y salidas en borrador." />
      <Pestanas valor={agrupar} onCambio={setAgrupar} opciones={[{ valor: "producto", texto: "Por producto" }, { valor: "bodega", texto: "Por bodega" }, { valor: "lote", texto: "Por lote" }, { valor: "ubicacion", texto: "Por ubicación" }]} />
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-5">
          <Entrada placeholder="Buscar producto…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2 md:col-span-1" />
          <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={op(cat.datos?.bodegas)} />
          <Selector vacio="Todas las familias" value={f.familia_id ?? ""} onChange={(e) => setF({ ...f, familia_id: e.target.value, subfamilia_id: "" })} opciones={op(cat.datos?.familias)} />
          <Selector vacio="Todas las subfamilias" value={f.subfamilia_id ?? ""} onChange={(e) => setF({ ...f, subfamilia_id: e.target.value })} opciones={op(cat.datos?.subfamilias?.filter((s: any) => !f.familia_id || String(s.familia_id) === String(f.familia_id)))} />
          {agrupar === "producto" && <Interruptor valor={bajo} onCambio={setBajo} etiqueta="Solo bajo mínimo" />}
        </div>
        {error && <Aviso tipo="error" className="m-3">{error}</Aviso>}
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            claveFila="_k"
            vacio="Sin stock para los filtros indicados."
            filas={(datos ?? []).map((x: any, i: number) => ({ ...x, _k: i }))}
            columnas={[
              { clave: "producto", titulo: "Producto", render: (x) => (
                <Link href={`/productos/detalle/?id=${x.producto_id}`} className="block hover:underline">
                  <span className="font-medium text-slate-900">{x.producto}</span>
                  <span className="block text-xs text-slate-500">{x.producto_codigo} · {x.subfamilia}</span>
                </Link>
              ) },
              ...(agrupar !== "producto" ? [{ clave: "bodega", titulo: "Bodega" }] : []),
              ...(agrupar === "lote" || agrupar === "ubicacion"
                ? [
                    { clave: "lote", titulo: "Lote", render: (x: any) => (x.lote_id ? <Link className="hover:underline" href={`/lotes/detalle/?id=${x.lote_id}`}>{x.lote}</Link> : "Sin lote") },
                    { clave: "lote_estado", titulo: "Estado", ocultarMovil: true, render: (x: any) => <Estado valor={x.lote_estado} /> },
                    { clave: "fecha_vencimiento", titulo: "Vence", ocultarMovil: true, render: (x: any) => fecha(x.fecha_vencimiento) },
                  ]
                : []),
              ...(agrupar === "ubicacion" ? [{ clave: "ubicacion", titulo: "Ubicación", render: (x: any) => x.ubicacion ?? "Sin ubicación" }] : []),
              { clave: "stock_fisico", titulo: "Físico", alinear: "derecha", render: (x) => num(x.stock_fisico) },
              { clave: "stock_reservado", titulo: "Reservado", alinear: "derecha", render: (x) => (x.stock_reservado ? <span className="text-amber-700">{num(x.stock_reservado)}</span> : "0") },
              { clave: "stock_disponible", titulo: "Disponible", alinear: "derecha", render: (x) => <b>{num(x.stock_disponible)}</b> },
              { clave: "stock_comprometido", titulo: "Comprometido", alinear: "derecha", ocultarMovil: true, render: (x) => num(x.stock_comprometido) },
              { clave: "unidad", titulo: "Unidad" },
              ...(agrupar === "producto" ? [{ clave: "stock_minimo", titulo: "Mínimo", alinear: "derecha" as const, ocultarMovil: true, render: (x: any) => (x.bajo_minimo ? <Insignia tono="rojo">{num(x.stock_minimo)} · bajo</Insignia> : num(x.stock_minimo)) }] : []),
              { clave: "ingreso_mas_antiguo", titulo: "Ingreso más antiguo", ocultarMovil: true, render: (x) => fecha(x.ingreso_mas_antiguo) },
              ...(costos ? [{ clave: "valor_inventario", titulo: "Valor", alinear: "derecha" as const, render: (x: any) => clp(x.valor_inventario) }] : []),
            ]}
          />
        )}
        {datos && (
          <p className="flex justify-between border-t border-slate-100 px-4 py-2 text-xs text-slate-500">
            <span>{datos.length} fila(s)</span>
            {costos && <span>Valor total: <b className="cifra text-slate-900">{clp(total)}</b></span>}
          </p>
        )}
      </Tarjeta>
    </>
  );
}
