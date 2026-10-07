"use client";

import { activoCol, Crud } from "@/components/Crud";

export default function Proveedores() {
  return (
    <Crud
      titulo="Proveedores"
      singular="proveedor"
      ruta="/proveedores"
      permiso="catalogo:administrar"
      columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "rut", titulo: "RUT", ocultarMovil: true }, { clave: "contacto", titulo: "Contacto", ocultarMovil: true }, activoCol]}
      campos={[
        { clave: "codigo", etiqueta: "Código", requerido: true },
        { clave: "rut", etiqueta: "RUT" },
        { clave: "nombre", etiqueta: "Nombre", requerido: true, ancho: 2 },
        { clave: "contacto", etiqueta: "Contacto", ancho: 2 },
        { clave: "activo", etiqueta: "Activo", tipo: "booleano", porDefecto: true },
      ]}
    />
  );
}
