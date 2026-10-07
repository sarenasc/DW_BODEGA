"use client";

import { useState } from "react";
import { activoCol, type CampoCrud, Crud } from "@/components/Crud";
import { Encabezado, Insignia, Pestanas, Selector } from "@/components/ui";
import { etiqueta } from "@/lib/formato";
import { camposPolitica } from "@/lib/politica";
import { useDatos } from "@/lib/sesion";

const resumen = (f: any) => (
  <span className="flex flex-wrap gap-1">
    {f.usa_lote !== null && <Insignia tono={f.usa_lote ? "verde" : "gris"}>{f.usa_lote ? "Con lote" : "Sin lote"}</Insignia>}
    {f.usa_vencimiento && <Insignia tono="ambar">Vencimiento</Insignia>}
    {f.granularidad && <Insignia tono="azul">{etiqueta(f.granularidad)}</Insignia>}
    {f.estrategia_salida && <Insignia tono="violeta">{f.estrategia_salida.replace("_", "+")}</Insignia>}
    {f.usa_lote === null && !f.granularidad && !f.estrategia_salida && <span className="text-xs text-slate-400">Hereda todo</span>}
  </span>
);

export default function Familias() {
  const [tab, setTab] = useState("familias");
  const [familia, setFamilia] = useState("");
  const cat = useDatos("/catalogos");
  const plantillas = useDatos("/plantillas-lotes");
  const politica = camposPolitica(plantillas.datos ?? []);
  const familias = (cat.datos?.familias ?? []).map((f: any) => ({ valor: f.id as number, texto: f.nombre as string }));
  const base: CampoCrud[] = [
    { clave: "codigo", etiqueta: "Código", requerido: true, ayuda: "Puede formar parte del código de lote." },
    { clave: "nombre", etiqueta: "Nombre", requerido: true },
    { clave: "descripcion", etiqueta: "Descripción", ancho: 2 },
  ];
  const activo: CampoCrud = { clave: "activo", etiqueta: "Activa", tipo: "booleano", porDefecto: true };
  return (
    <>
      <Encabezado titulo="Familias y subfamilias" descripcion="Familia → Subfamilia → Producto. La configuración se hereda y puede sobreescribirse en cada nivel." />
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "familias", texto: "Familias" }, { valor: "subfamilias", texto: "Subfamilias" }]} />
      {tab === "familias" ? (
        <Crud
          key="f"
          sinEncabezado
          titulo="Familias"
          singular="familia"
          ruta="/familias"
          permiso="catalogo:administrar"
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "politica", titulo: "Configuración propia", render: resumen, ocultarMovil: true }, activoCol]}
          campos={[...base, ...politica, activo]}
        />
      ) : (
        <Crud
          key="s"
          sinEncabezado
          titulo="Subfamilias"
          singular="subfamilia"
          ruta="/subfamilias"
          permiso="catalogo:administrar"
          filtros={{ familia_id: familia }}
          valoresIniciales={{ familia_id: familia }}
          barra={<Selector aria-label="Familia" className="!w-52" vacio="Todas las familias" value={familia} onChange={(e) => setFamilia(e.target.value)} opciones={familias} />}
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "familia", titulo: "Familia" }, { clave: "politica", titulo: "Configuración propia", render: resumen, ocultarMovil: true }, activoCol]}
          campos={[{ clave: "familia_id", etiqueta: "Familia", tipo: "select", opciones: familias, requerido: true, ancho: 2 }, ...base, ...politica, activo]}
        />
      )}
    </>
  );
}
