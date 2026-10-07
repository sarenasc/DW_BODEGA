"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { activoCol, type CampoCrud, Crud } from "@/components/Crud";
import { Selector } from "@/components/ui";
import { clp, num } from "@/lib/formato";
import { camposPolitica } from "@/lib/politica";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Productos() {
  const router = useRouter();
  const { puede } = useSesion();
  const cat = useDatos("/catalogos");
  const plantillas = useDatos("/plantillas-lotes");
  const [sub, setSub] = useState("");
  const c = cat.datos;
  const unidades = (c?.unidades ?? []).map((u: any) => ({ valor: u.id as number, texto: `${u.codigo} — ${u.nombre}` }));
  const subfamilias = (c?.subfamilias ?? []).map((s: any) => ({ valor: s.id as number, texto: `${c.familias.find((f: any) => f.id === s.familia_id)?.nombre ?? ""} › ${s.nombre}` }));
  const g = "Datos generales";
  const u = "Unidades y stock";
  const campos: CampoCrud[] = [
    { clave: "codigo", etiqueta: "Código interno", requerido: true, seccion: g },
    { clave: "codigo_externo", etiqueta: "Código externo", seccion: g },
    { clave: "nombre", etiqueta: "Nombre", requerido: true, ancho: 2, seccion: g },
    { clave: "subfamilia_id", etiqueta: "Familia › Subfamilia", tipo: "select", opciones: subfamilias, requerido: true, ancho: 2, seccion: g },
    { clave: "descripcion", etiqueta: "Descripción", tipo: "area", ancho: 2, seccion: g },
    { clave: "categoria", etiqueta: "Categoría", seccion: g },
    { clave: "marca", etiqueta: "Marca", seccion: g },
    { clave: "proveedor_id", etiqueta: "Proveedor habitual", tipo: "select", opciones: (c?.proveedores ?? []).map((p: any) => ({ valor: p.id as number, texto: p.nombre })), seccion: g },
    { clave: "codigo_barras", etiqueta: "Código de barras", seccion: g },
    { clave: "unidad_base_id", etiqueta: "Unidad principal (inventario)", tipo: "select", opciones: unidades, requerido: true, seccion: u, ayuda: "No puede cambiarse cuando ya hay existencias." },
    { clave: "unidad_consumo_id", etiqueta: "Unidad de consumo", tipo: "select", opciones: unidades, seccion: u },
    { clave: "costo_referencial", etiqueta: "Costo referencial (por unidad principal)", tipo: "numero", seccion: u },
    { clave: "moneda", etiqueta: "Moneda", porDefecto: "CLP", seccion: u },
    { clave: "stock_minimo", etiqueta: "Stock mínimo", tipo: "numero", seccion: u },
    { clave: "stock_critico", etiqueta: "Stock crítico", tipo: "numero", seccion: u },
    { clave: "punto_reposicion", etiqueta: "Punto de reposición", tipo: "numero", seccion: u },
    { clave: "stock_maximo", etiqueta: "Stock máximo", tipo: "numero", seccion: u },
    ...camposPolitica(plantillas.datos ?? []),
    { clave: "activo", etiqueta: "Activo", tipo: "booleano", porDefecto: true },
  ];
  return (
    <Crud
      titulo="Productos"
      descripcion="Maestro de productos. La unidad de compra y sus conversiones se configuran en la ficha del producto."
      singular="producto"
      ruta="/productos"
      permiso="catalogo:administrar"
      filtros={{ subfamilia_id: sub }}
      onFila={(f) => router.push(`/productos/detalle/?id=${f.id}`)}
      barra={<Selector aria-label="Subfamilia" className="!w-64" vacio="Todas las subfamilias" value={sub} onChange={(e) => setSub(e.target.value)} opciones={subfamilias} />}
      columnas={[
        { clave: "codigo", titulo: "Código" },
        { clave: "nombre", titulo: "Nombre", render: (p) => <span className="font-medium text-slate-900">{p.nombre}</span> },
        { clave: "familia", titulo: "Familia", ocultarMovil: true },
        { clave: "subfamilia", titulo: "Subfamilia", ocultarMovil: true },
        { clave: "unidad_base", titulo: "Unidad" },
        { clave: "stock_minimo", titulo: "Mínimo", alinear: "derecha", ocultarMovil: true, render: (p) => num(p.stock_minimo) },
        ...(puede("costos:ver") ? [{ clave: "costo_referencial", titulo: "Costo ref.", alinear: "derecha" as const, ocultarMovil: true, render: (p: any) => clp(p.costo_referencial, 2) }] : []),
        activoCol,
      ]}
      campos={campos}
    />
  );
}
