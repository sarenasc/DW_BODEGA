"use client";

import { Box, ListTree } from "lucide-react";
import { activoCol, Crud } from "@/components/Crud";
import { EnlaceBoton } from "@/components/ui";
import { num } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

export default function Bodegas() {
  const cat = useDatos("/catalogos");
  const tipos = (cat.datos?.tipos_bodega ?? []).map((t: any) => ({ valor: t.id as number, texto: t.nombre as string }));
  return (
    <Crud
      titulo="Bodegas"
      descripcion="Cada bodega tiene su propia estructura de ubicaciones y su plano. La jerarquía es opcional y configurable."
      singular="bodega"
      ruta="/bodegas"
      permiso="bodegas:administrar"
      columnas={[
        { clave: "codigo", titulo: "Código" },
        { clave: "nombre", titulo: "Nombre", render: (b) => <span className="font-medium text-slate-900">{b.nombre}</span> },
        { clave: "dimensiones", titulo: "Largo × ancho × alto (m)", ocultarMovil: true, render: (b) => (b.largo ? `${num(b.largo)} × ${num(b.ancho)} × ${num(b.alto)}` : "—") },
        activoCol,
        {
          clave: "ir",
          titulo: "",
          alinear: "derecha",
          render: (b) => (
            <span className="flex justify-end gap-1.5">
              <EnlaceBoton tam="sm" href={`/bodegas/plano/?id=${b.id}`} icono={<Box className="size-3.5" />}>
                Plano 2D / 3D
              </EnlaceBoton>
              <EnlaceBoton tam="sm" href={`/bodegas/ubicaciones/?id=${b.id}`} icono={<ListTree className="size-3.5" />}>
                Ubicaciones
              </EnlaceBoton>
            </span>
          ),
        },
      ]}
      campos={[
        { clave: "codigo", etiqueta: "Código", requerido: true, ayuda: "Prefijo de las ubicaciones: FIT-A-R02-N03-P04." },
        { clave: "nombre", etiqueta: "Nombre", requerido: true },
        { clave: "tipo_bodega_id", etiqueta: "Tipo de bodega", tipo: "select", opciones: tipos },
        { clave: "direccion", etiqueta: "Dirección / sector" },
        { clave: "largo", etiqueta: "Largo (m)", tipo: "numero" },
        { clave: "ancho", etiqueta: "Ancho (m)", tipo: "numero" },
        { clave: "alto", etiqueta: "Alto (m)", tipo: "numero" },
        { clave: "activo", etiqueta: "Activa", tipo: "booleano", porDefecto: true },
      ]}
    />
  );
}
