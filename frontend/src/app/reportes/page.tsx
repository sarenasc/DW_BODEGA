"use client";

import { FileDown, FileSpreadsheet, FileText, Printer } from "lucide-react";
import { useEffect, useState } from "react";
import { Aviso, Boton, Cargando, Encabezado, Entrada, Selector, Tarjeta, useAccion } from "@/components/ui";
import { abrirArchivo } from "@/lib/api";
import { clp, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

function celda(v: any, tipo: string) {
  if (v === null || v === undefined || v === "") return <span className="text-slate-300">—</span>;
  if (tipo === "moneda") return clp(v);
  if (tipo === "moneda4") return clp(v, 2);
  if (tipo === "numero") return num(v, 3);
  if (tipo === "fecha") return fecha(v);
  if (tipo === "fechahora") return fechaHora(v);
  return String(v);
}

export default function Reportes() {
  const { puede } = useSesion();
  const inicial = useParametro("r");
  const lista = useDatos<any[]>("/reportes");
  const cat = useDatos("/catalogos");
  const val = useDatos(puede("procesos:ver") ? "/procesos/valores" : null);
  const [codigo, setCodigo] = useState("stock_actual");
  const [f, setF] = useState<Record<string, any>>({});
  useEffect(() => { if (inicial) setCodigo(inicial); }, [inicial]);
  const { datos, cargando, error } = useDatos(`/reportes/${codigo}`, f);
  const { ejecutar, ocupado } = useAccion();
  const exportar = (formato: string) => ejecutar(() => abrirArchivo(`/reportes/${codigo}`, { ...f, formato }, formato === "pdf" ? undefined : `${codigo}.${formato}`));
  const numericas = (datos?.columnas ?? []).filter((c: any) => ["moneda", "numero"].includes(c.tipo) && !["dias", "dias_para_vencer", "stock_minimo", "costo_unitario", "porcentaje"].includes(c.clave));
  const op = (l: any[] | undefined) => (l ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }));

  return (
    <>
      <Encabezado titulo="Reportes" descripcion="Todos los reportes se exportan a Excel, CSV y PDF con los filtros aplicados.">
        {puede("reportes:exportar") && (
          <>
            <Boton variante="secundario" cargando={ocupado} icono={<FileSpreadsheet className="size-4" />} onClick={() => exportar("xlsx")}>Excel</Boton>
            <Boton variante="secundario" icono={<FileDown className="size-4" />} onClick={() => exportar("csv")}>CSV</Boton>
            <Boton variante="secundario" icono={<FileText className="size-4" />} onClick={() => exportar("pdf")}>PDF</Boton>
          </>
        )}
        <Boton variante="fantasma" icono={<Printer className="size-4" />} onClick={() => window.print()}>Imprimir</Boton>
      </Encabezado>
      <Tarjeta className="no-imprimir mb-3">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-8">
          <Selector aria-label="Reporte" className="col-span-2 font-medium" value={codigo} onChange={(e) => setCodigo(e.target.value)} opciones={(lista.datos ?? []).map((r) => ({ valor: r.codigo, texto: r.titulo }))} />
          <Entrada type="date" aria-label="Desde" title="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
          <Entrada type="date" aria-label="Hasta" title="Hasta" value={f.hasta ?? ""} onChange={(e) => setF({ ...f, hasta: e.target.value })} />
          <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={op(cat.datos?.bodegas)} />
          <Selector vacio="Todas las familias" value={f.familia_id ?? ""} onChange={(e) => setF({ ...f, familia_id: e.target.value })} opciones={op(cat.datos?.familias)} />
          <Selector vacio="Todas las especies" value={f.especie ?? ""} onChange={(e) => setF({ ...f, especie: e.target.value })} opciones={(val.datos?.especies ?? []).map((x: string) => ({ valor: x, texto: x }))} />
          <Selector vacio="Todas las temporadas" value={f.temporada_id ?? ""} onChange={(e) => setF({ ...f, temporada_id: e.target.value })} opciones={(cat.datos?.temporadas ?? []).map((t: any) => ({ valor: t.id, texto: t.codigo }))} />
        </div>
      </Tarjeta>
      {error && <Aviso tipo="error">{error}</Aviso>}
      <Tarjeta titulo={datos ? `${datos.titulo} · ${datos.filas.length} fila(s)` : "…"} sinRelleno>
        {!datos || cargando ? (
          <Cargando />
        ) : datos.filas.length === 0 ? (
          <p className="p-10 text-center text-sm text-slate-500">Sin datos para los filtros indicados.</p>
        ) : (
          <div className="max-h-[68vh] overflow-auto">
            <table className="tabla w-full border-collapse">
              <thead className="sticky top-0 z-10">
                <tr>{datos.columnas.map((c: any) => <th key={c.clave} className={["moneda", "moneda4", "numero"].includes(c.tipo) ? "!text-right" : ""}>{c.titulo}</th>)}</tr>
              </thead>
              <tbody>
                {datos.filas.slice(0, 1000).map((fila: any, i: number) => (
                  <tr key={i}>
                    {datos.columnas.map((c: any) => <td key={c.clave} className={["moneda", "moneda4", "numero"].includes(c.tipo) ? "cifra text-right whitespace-nowrap" : "max-w-72 truncate"} title={typeof fila[c.clave] === "string" ? fila[c.clave] : undefined}>{celda(fila[c.clave], c.tipo)}</td>)}
                  </tr>
                ))}
              </tbody>
              {numericas.length > 0 && (
                <tfoot>
                  <tr className="bg-slate-50 font-semibold">
                    {datos.columnas.map((c: any, i: number) => {
                      const suma = numericas.some((n: any) => n.clave === c.clave) ? datos.filas.reduce((s: number, x: any) => s + (Number(x[c.clave]) || 0), 0) : null;
                      return <td key={c.clave} className={suma !== null ? "cifra text-right" : ""}>{suma !== null ? celda(suma, c.tipo) : i === 0 ? "Total" : ""}</td>;
                    })}
                  </tr>
                </tfoot>
              )}
            </table>
          </div>
        )}
        {datos && datos.filas.length > 1000 && <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-500">Se muestran las primeras 1.000 filas. Exporte para obtener el reporte completo.</p>}
      </Tarjeta>
    </>
  );
}
