"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Cargando, Encabezado, EnlaceBoton, Entrada, Estado, Insignia, Paginacion, Selector, Tabla, Tarjeta } from "@/components/ui";
import { clp, etiqueta, fechaHora } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

const CLASES = [["INGRESO", "inventario:crear"], ["SALIDA", "movimientos:crear"], ["TRASLADO", "traslados:crear"], ["AJUSTE", "inventario:ajustar"]];

export default function Documentos() {
  const router = useRouter();
  const { puede } = useSesion();
  const [f, setF] = useState<Record<string, any>>({});
  const [pagina, setPagina] = useState(1);
  const cat = useDatos("/catalogos");
  const { datos, cargando } = useDatos("/documentos", { ...f, pagina, tam: 50 });
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave]);
  return (
    <>
      <Encabezado titulo="Documentos de inventario" descripcion="Borrador → Confirmado → Anulado. Un documento confirmado genera movimientos inmutables.">
        {CLASES.filter(([, p]) => puede(p)).map(([c]) => (
          <EnlaceBoton key={c} href={`/documentos/nuevo/?clase=${c}`} variante={c === "INGRESO" ? "primario" : "secundario"} icono={<Plus className="size-4" />}>
            {etiqueta(c)}
          </EnlaceBoton>
        ))}
      </Encabezado>
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-6">
          <Entrada placeholder="Número o documento…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2" />
          <Selector vacio="Todas las clases" value={f.clase ?? ""} onChange={(e) => setF({ ...f, clase: e.target.value })} opciones={CLASES.map(([c]) => ({ valor: c, texto: etiqueta(c) }))} />
          <Selector vacio="Todos los estados" value={f.estado ?? ""} onChange={(e) => setF({ ...f, estado: e.target.value })} opciones={["BORRADOR", "CONFIRMADO", "ANULADO"].map((c) => ({ valor: c, texto: etiqueta(c) }))} />
          <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} />
          <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            onFila={(d) => router.push(`/documentos/detalle/?id=${d.id}`)}
            columnas={[
              { clave: "numero", titulo: "Número", render: (d) => <span className="cifra font-medium">{d.numero}</span> },
              { clave: "clase", titulo: "Clase", render: (d) => <Insignia tono={d.clase === "INGRESO" ? "verde" : d.clase === "SALIDA" ? "azul" : d.clase === "TRASLADO" ? "violeta" : "ambar"}>{d.clase}</Insignia> },
              { clave: "fecha", titulo: "Fecha", render: (d) => fechaHora(d.fecha) },
              { clave: "motivo", titulo: "Motivo", ocultarMovil: true },
              { clave: "numero_documento", titulo: "Documento", ocultarMovil: true, render: (d) => (d.numero_documento ? `${etiqueta(d.tipo_documento)} ${d.numero_documento}` : "—") },
              { clave: "proveedor", titulo: "Proveedor", ocultarMovil: true },
              { clave: "bodega", titulo: "Bodega", ocultarMovil: true, render: (d) => (d.bodega_destino && d.bodega_destino !== d.bodega ? `${d.bodega} → ${d.bodega_destino}` : d.bodega) },
              { clave: "lineas", titulo: "Líneas", alinear: "derecha", ocultarMovil: true },
              ...(puede("costos:ver") ? [{ clave: "costo_total", titulo: "Total", alinear: "derecha" as const, render: (d: any) => clp(d.costo_total) }] : []),
              { clave: "estado", titulo: "Estado", render: (d) => <Estado valor={d.estado} /> },
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>
    </>
  );
}
