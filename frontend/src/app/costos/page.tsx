"use client";

import { useState } from "react";
import { BarrasLista } from "@/components/Graficos";
import { Aviso, Cargando, Encabezado, Entrada, Indicador, Insignia, Selector, Tabla, Tarjeta } from "@/components/ui";
import { clp, num } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

const DIMENSIONES = [
  ["proceso", "Proceso"], ["especie", "Especie"], ["variedad", "Variedad"], ["productor", "Productor"], ["exportadora", "Exportadora"], ["lote_productivo", "Lote productivo"],
  ["temporada", "Temporada"], ["semana", "Semana"], ["mes", "Mes"], ["producto", "Producto / fitosanitario"], ["familia", "Familia"], ["subfamilia", "Subfamilia"], ["bodega", "Bodega"],
];

export default function Costos() {
  const [dimension, setDimension] = useState("especie");
  const [f, setF] = useState<Record<string, any>>({});
  const cat = useDatos("/catalogos");
  const val = useDatos("/procesos/valores");
  const { datos, cargando, error } = useDatos<any[]>("/costos", { dimension, ...f });
  const total = (datos ?? []).reduce((s, x) => s + x.costo, 0);
  // Los kilos de una dimension de producto se repiten entre filas: el total por kilo solo es valido en dimensiones de proceso.
  const porProceso = !["producto", "familia", "subfamilia", "bodega"].includes(dimension);
  const kilos = porProceso ? (datos ?? []).reduce((s, x) => s + x.kilos, 0) : null;
  const nombre = DIMENSIONES.find(([d]) => d === dimension)?.[1] ?? dimension;

  return (
    <>
      <Encabezado titulo="Costos" descripcion="Costeo multidimensional: cada consumo conserva el costo real de la existencia utilizada." />
      <Tarjeta className="mb-3">
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
          <Selector aria-label="Analizar por" value={dimension} onChange={(e) => setDimension(e.target.value)} opciones={DIMENSIONES.map(([valor, texto]) => ({ valor, texto: `Por ${texto.toLowerCase()}` }))} className="col-span-2 font-medium md:col-span-1" />
          <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
          <Entrada type="date" aria-label="Hasta" value={f.hasta ?? ""} onChange={(e) => setF({ ...f, hasta: e.target.value })} />
          <Selector vacio="Todas las temporadas" value={f.temporada_id ?? ""} onChange={(e) => setF({ ...f, temporada_id: e.target.value })} opciones={(cat.datos?.temporadas ?? []).map((t: any) => ({ valor: t.id, texto: t.codigo }))} />
          <Selector vacio="Todas las especies" value={f.especie ?? ""} onChange={(e) => setF({ ...f, especie: e.target.value })} opciones={(val.datos?.especies ?? []).map((x: string) => ({ valor: x, texto: x }))} />
          <Selector vacio="Todos los productores" value={f.productor ?? ""} onChange={(e) => setF({ ...f, productor: e.target.value })} opciones={(val.datos?.productores ?? []).map((x: string) => ({ valor: x, texto: x }))} />
          <Selector vacio="Todas las familias" value={f.familia_id ?? ""} onChange={(e) => setF({ ...f, familia_id: e.target.value })} opciones={(cat.datos?.familias ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }))} />
        </div>
      </Tarjeta>
      {error && <Aviso tipo="error">{error}</Aviso>}
      {!datos && cargando ? (
        <Cargando />
      ) : (
        <>
          <div className="mb-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Indicador titulo="Costo total" valor={clp(total)} />
            <Indicador titulo="Kilos base" valor={kilos != null ? `${num(kilos, 0)} kg` : "—"} detalle={kilos == null ? "No aplica a esta dimensión" : undefined} />
            <Indicador titulo="Costo por kilo" valor={kilos ? clp(total / kilos, 2) : "—"} />
            <Indicador titulo={`Grupos (${nombre.toLowerCase()})`} valor={datos?.length ?? 0} />
          </div>
          <div className="grid gap-3 lg:grid-cols-[1fr_1.4fr]">
            <Tarjeta titulo={`Costo por ${nombre.toLowerCase()}`}>
              <BarrasLista maximo={12} datos={(datos ?? []).map((x) => ({ nombre: x.clave, valor: x.costo, detalle: x.costo_por_kilo != null ? `${clp(x.costo_por_kilo, 2)}/kg` : undefined }))} />
            </Tarjeta>
            <Tarjeta titulo="Detalle" sinRelleno>
              <Tabla
                claveFila="clave"
                vacio="Sin consumos asociados a procesos para los filtros indicados."
                filas={datos ?? []}
                columnas={[
                  { clave: "clave", titulo: nombre, render: (x) => <span className="font-medium text-slate-900">{x.clave}</span> },
                  { clave: "costo", titulo: "Costo", alinear: "derecha", render: (x) => clp(x.costo) },
                  { clave: "kilos", titulo: "Kilos", alinear: "derecha", render: (x) => num(x.kilos, 0) },
                  { clave: "costo_por_kilo", titulo: "Costo/kg", alinear: "derecha", render: (x) => <b>{clp(x.costo_por_kilo, 2)}</b> },
                  { clave: "procesos", titulo: "Procesos", alinear: "derecha", ocultarMovil: true },
                  { clave: "estado_kilos", titulo: "Kilos", render: (x) => <Insignia tono={x.estado_kilos === "DEFINITIVO" ? "verde" : "ambar"}>{x.estado_kilos === "DEFINITIVO" ? "Definitivos" : `Provisorios (${x.procesos_provisorios})`}</Insignia> },
                ]}
              />
            </Tarjeta>
          </div>
        </>
      )}
    </>
  );
}
