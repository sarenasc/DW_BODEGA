"use client";

import { Ban, Check, Pencil, Printer } from "lucide-react";
import Link from "next/link";
import { Adjuntos } from "@/components/Adjuntos";
import { Aviso, Boton, Cargando, Dato, Encabezado, EnlaceBoton, Estado, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { abrirArchivo, api } from "@/lib/api";
import { clp, etiqueta, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function DetalleDocumento() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const { datos: d, error, setDatos } = useDatos(id ? `/documentos/${id}` : null);
  const { ejecutar, ocupado } = useAccion();
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!d) return <Cargando />;
  const ingreso = d.clase === "INGRESO";

  const anular = () => {
    const motivo = prompt(d.estado === "CONFIRMADO" ? "Anular un documento confirmado revierte sus movimientos con movimientos inversos.\nMotivo de la anulación:" : "Motivo de la anulación:");
    if (motivo?.trim()) ejecutar(async () => setDatos(await api.post(`/documentos/${d.id}/anular`, { motivo })), "Documento anulado");
  };

  return (
    <>
      <Encabezado titulo={`${etiqueta(d.clase)} ${d.numero}`} descripcion={`${d.bodega}${d.bodega_destino && d.bodega_destino !== d.bodega ? ` → ${d.bodega_destino}` : ""} · ${fechaHora(d.fecha)}`} volver="/documentos/">
        <Estado valor={d.estado} />
        {d.estado === "BORRADOR" && puede("inventario:editar") && <EnlaceBoton href={`/documentos/nuevo/?clase=${d.clase}&id=${d.id}`} icono={<Pencil className="size-4" />}>Editar</EnlaceBoton>}
        {d.estado === "BORRADOR" && <Boton icono={<Check className="size-4" />} cargando={ocupado} onClick={() => ejecutar(async () => setDatos(await api.post(`/documentos/${d.id}/confirmar`)), "Documento confirmado")}>Confirmar</Boton>}
        {ingreso && d.estado === "CONFIRMADO" && d.existencias.length > 0 && puede("inventario:editar") && (
          <Boton icono={<Printer className="size-4" />} onClick={() => ejecutar(() => abrirArchivo("/etiquetas", { existencias: d.existencias.map((e: any) => e.id).join(",") }))}>
            Imprimir QR ({d.existencias.length})
          </Boton>
        )}
        {d.estado !== "ANULADO" && (d.estado === "BORRADOR" || puede("movimientos:anular")) && d.clase !== "TRASLADO" && <Boton variante="peligro" icono={<Ban className="size-4" />} onClick={anular}>Anular</Boton>}
      </Encabezado>

      {d.estado === "ANULADO" && <Aviso tipo="error" className="mb-3" titulo="Documento anulado">{d.motivo_anulacion} · {fechaHora(d.anulado_en)}</Aviso>}
      {d.estado === "BORRADOR" && <Aviso tipo="alerta" className="mb-3">Borrador: aún no afecta el stock. Puede editarse hasta que se confirme.</Aviso>}

      <div className="grid gap-3 lg:grid-cols-3">
        <Tarjeta titulo="Datos del documento" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Dato etiqueta="Motivo">{d.motivo}</Dato>
            <Dato etiqueta="Documento">{d.numero_documento ? `${etiqueta(d.tipo_documento)} ${d.numero_documento}` : "—"}</Dato>
            <Dato etiqueta="Fecha documento">{fecha(d.fecha_documento)}</Dato>
            <Dato etiqueta="Proveedor">{d.proveedor}</Dato>
            <Dato etiqueta="Registrado por">{d.usuario}</Dato>
            <Dato etiqueta="Confirmado">{fechaHora(d.confirmado_en)}</Dato>
            <Dato etiqueta="Proceso">{d.proceso_id ? <Link className="text-marca-700 hover:underline" href={`/procesos/detalle/?id=${d.proceso_id}`}>{d.proceso}</Link> : "—"}</Dato>
            {costos && <Dato etiqueta="Valor total">{clp(d.costo_total)} {d.moneda}</Dato>}
          </dl>
          {d.observaciones && <p className="mt-3 border-t border-slate-100 pt-3 text-sm text-slate-600">{d.observaciones}</p>}
        </Tarjeta>
        <Adjuntos entidad="documento" id={d.id} titulo="Factura, guía u otros" />

        <Tarjeta titulo="Líneas" className="lg:col-span-3" sinRelleno>
          <Tabla
            filas={d.detalles}
            columnas={[
              { clave: "producto", titulo: "Producto", render: (x) => <><span className="font-medium text-slate-900">{x.producto}</span><span className="block text-xs text-slate-500">{x.producto_codigo}{x.existencia ? ` · ${x.existencia}` : ""}</span></> },
              { clave: "cantidad", titulo: "Cantidad", alinear: "derecha", render: (x) => `${num(x.cantidad)} ${x.unidad}` },
              { clave: "cantidad_base", titulo: "En unidad base", alinear: "derecha", ocultarMovil: true, render: (x) => (x.cantidad_base != null ? `${num(x.cantidad_base)} ${x.unidad_base}` : "—") },
              ...(costos ? [
                { clave: "precio_unitario", titulo: "Valor unitario", alinear: "derecha" as const, ocultarMovil: true, render: (x: any) => clp(x.precio_unitario, 2) },
                { clave: "costo_unitario_base", titulo: "Costo / unidad base", alinear: "derecha" as const, ocultarMovil: true, render: (x: any) => clp(x.costo_unitario_base, 2) },
                { clave: "costo_total", titulo: "Total", alinear: "derecha" as const, render: (x: any) => clp(x.costo_total) },
              ] : []),
              { clave: "lote", titulo: "Lote", render: (x) => (x.lote_id ? <Link className="text-marca-700 hover:underline" href={`/lotes/detalle/?id=${x.lote_id}`}>{x.lote}</Link> : x.lote_manual ?? "—") },
              { clave: "fecha_vencimiento", titulo: "Vence", ocultarMovil: true, render: (x) => fecha(x.fecha_vencimiento) },
              { clave: "ubicacion", titulo: "Ubicación", ocultarMovil: true, render: (x) => x.ubicacion_destino ?? x.ubicacion ?? "—" },
            ]}
          />
        </Tarjeta>

        {ingreso && d.existencias.length > 0 && (
          <Tarjeta titulo={`Existencias generadas (${d.existencias.length})`} className="lg:col-span-3" sinRelleno>
            <Tabla
              filas={d.existencias}
              columnas={[
                { clave: "codigo_publico", titulo: "Existencia", render: (e) => <Link className="cifra font-medium text-marca-700 hover:underline" href={`/existencia/?id=${e.id}`}>{e.codigo_publico}</Link> },
                { clave: "producto", titulo: "Producto" },
                { clave: "lote", titulo: "Lote" },
                { clave: "ubicacion", titulo: "Ubicación", render: (e) => e.ubicacion ?? "Sin ubicar" },
                { clave: "cantidad_fisica", titulo: "Disponible", alinear: "derecha", render: (e) => `${num(e.cantidad_fisica)} / ${num(e.cantidad_inicial)} ${e.unidad}` },
                ...(costos ? [{ clave: "costo_unitario", titulo: "Costo unit.", alinear: "derecha" as const, render: (e: any) => clp(e.costo_unitario, 2) }] : []),
                { clave: "estado", titulo: "Estado", render: (e) => <Estado valor={e.estado} /> },
              ]}
            />
          </Tarjeta>
        )}
      </div>
    </>
  );
}
