"use client";

import { useState } from "react";
import { activoCol, Crud } from "@/components/Crud";
import { Encabezado, Pestanas } from "@/components/ui";
import { num } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

export default function Unidades() {
  const [tab, setTab] = useState("unidades");
  const cat = useDatos("/catalogos");
  const unidades = (cat.datos?.unidades ?? []).map((u: any) => ({ valor: u.id as number, texto: `${u.codigo} — ${u.nombre}` }));
  const cod = (id: number) => cat.datos?.unidades.find((u: any) => u.id === id)?.codigo ?? id;
  return (
    <>
      <Encabezado titulo="Unidades de medida" descripcion="Catálogo configurable y conversiones universales. Las conversiones propias de un producto (p. ej. 1 bidón = 20 L) se definen en el producto." />
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "unidades", texto: "Unidades" }, { valor: "conversiones", texto: "Conversiones universales" }]} />
      {tab === "unidades" ? (
        <Crud
          key="u"
          sinEncabezado
          titulo="Unidades"
          singular="unidad"
          ruta="/unidades"
          permiso="catalogo:administrar"
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "dimension", titulo: "Dimensión" }, { clave: "decimales", titulo: "Decimales", alinear: "derecha" }, activoCol]}
          campos={[
            { clave: "codigo", etiqueta: "Código", requerido: true },
            { clave: "nombre", etiqueta: "Nombre", requerido: true },
            { clave: "dimension", etiqueta: "Dimensión", tipo: "select", requerido: true, porDefecto: "CONTEO", opciones: ["MASA", "VOLUMEN", "CONTEO", "LONGITUD", "ENVASE"].map((d) => ({ valor: d, texto: d })) },
            { clave: "decimales", etiqueta: "Decimales", tipo: "numero", porDefecto: 2 },
            { clave: "activo", etiqueta: "Activa", tipo: "booleano", porDefecto: true },
          ]}
        />
      ) : (
        <Crud
          key="c"
          sinEncabezado
          titulo="Conversiones"
          singular="conversión"
          ruta="/conversiones"
          permiso="catalogo:administrar"
          filtros={{ producto_id: "null" }}
          columnas={[{ clave: "regla", titulo: "Conversión", render: (c) => <span className="cifra">1 {cod(c.unidad_origen_id)} = {num(c.factor, 6)} {cod(c.unidad_destino_id)}</span> }]}
          campos={[
            { clave: "unidad_origen_id", etiqueta: "1 unidad de…", tipo: "select", opciones: unidades, requerido: true },
            { clave: "unidad_destino_id", etiqueta: "…equivale a (unidad)", tipo: "select", opciones: unidades, requerido: true },
            { clave: "factor", etiqueta: "Factor", tipo: "numero", requerido: true, ayuda: "Ejemplo: 1 kg = 1000 g → factor 1000." },
          ]}
        />
      )}
    </>
  );
}
