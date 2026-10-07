"use client";

import { GitBranch, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Adjuntos } from "@/components/Adjuntos";
import { Aviso, Boton, Campo, Cargando, Dato, Encabezado, EnlaceBoton, Entrada, Estado, Modal, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, etiqueta, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function DetalleLote() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const { datos: l, error, recargar } = useDatos(id ? `/lotes/${id}` : null);
  const ex = useDatos(id && puede("inventario:ver") ? "/existencias" : null, { lote_id: id, con_stock: false, tam: 200 });
  const [cambio, setCambio] = useState<{ estado: string; motivo: string } | null>(null);
  const { ejecutar, ocupado } = useAccion();
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!l) return <Cargando />;

  return (
    <>
      <Encabezado titulo={l.codigo} descripcion={`${l.producto} · ${l.producto_codigo}`} volver="/lotes/">
        <Estado valor={l.estado} />
        {puede("lotes:bloquear") && l.estado !== "ANULADO" && <Boton variante="secundario" icono={<ShieldAlert className="size-4" />} onClick={() => setCambio({ estado: l.estado === "DISPONIBLE" ? "BLOQUEADO" : "DISPONIBLE", motivo: "" })}>Cambiar estado</Boton>}
        {puede("trazabilidad:ver") && <EnlaceBoton variante="primario" href={`/trazabilidad/?lote=${l.id}`} icono={<GitBranch className="size-4" />}>Trazabilidad</EnlaceBoton>}
      </Encabezado>
      {["BLOQUEADO", "CUARENTENA", "VENCIDO"].includes(l.estado) && <Aviso tipo="alerta" className="mb-3">Lote en estado {l.estado}: no puede consumirse salvo con permiso especial.</Aviso>}
      <div className="grid gap-3 lg:grid-cols-3">
        <Tarjeta titulo="Datos del lote" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Dato etiqueta="Fecha creación">{fechaHora(l.fecha_creacion)}</Dato>
            <Dato etiqueta="Fecha ingreso">{fecha(l.fecha_ingreso)}</Dato>
            <Dato etiqueta="Fabricación">{fecha(l.fecha_fabricacion)}</Dato>
            <Dato etiqueta="Vencimiento">{fecha(l.fecha_vencimiento)}</Dato>
            <Dato etiqueta="Cantidad inicial">{num(l.cantidad_inicial)} {l.unidad}</Dato>
            <Dato etiqueta="Cantidad disponible">{num(l.cantidad_disponible)} {l.unidad}</Dato>
            {costos && <Dato etiqueta="Valor inicial">{clp(l.valor_inicial)}</Dato>}
            {costos && <Dato etiqueta="Valor disponible">{clp(l.valor_disponible)}</Dato>}
            <Dato etiqueta="Referencia externa">{l.referencia_externa}</Dato>
            <Dato etiqueta="Documento origen">{l.documento_origen_id ? <Link className="text-marca-700 hover:underline" href={`/documentos/detalle/?id=${l.documento_origen_id}`}>Ver ingreso</Link> : "—"}</Dato>
            <Dato etiqueta="Lote padre">{l.lote_padre_id ? <Link className="text-marca-700 hover:underline" href={`/lotes/detalle/?id=${l.lote_padre_id}`}>Ver lote de origen</Link> : "—"}</Dato>
            <Dato etiqueta="Plantilla (versión)">{l.version_plantilla_id ? `Versión #${l.version_plantilla_id}` : "Lote manual"}</Dato>
          </dl>
          {l.sublotes.length > 0 && (
            <p className="mt-4 flex flex-wrap items-center gap-1.5 border-t border-slate-100 pt-3 text-sm text-slate-600">
              Sublotes:
              {l.sublotes.map((s: any) => (
                <Link key={s.id} href={`/lotes/detalle/?id=${s.id}`} className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-800 hover:bg-slate-200">{s.codigo}</Link>
              ))}
            </p>
          )}
        </Tarjeta>
        <Tarjeta titulo="Historial de estados">
          <ol className="space-y-2">
            {l.historial.map((h: any) => (
              <li key={h.id} className="border-l-2 border-slate-200 pl-3 text-sm">
                <Estado valor={h.estado_nuevo} /> <span className="text-xs text-slate-500">{fechaHora(h.fecha)}</span>
                {h.motivo && <p className="text-slate-600">{h.motivo}</p>}
              </li>
            ))}
          </ol>
        </Tarjeta>
        {ex.datos && (
          <Tarjeta titulo={`Existencias del lote (${ex.datos.total})`} className="lg:col-span-2" sinRelleno>
            <Tabla
              filas={ex.datos.items}
              columnas={[
                { clave: "codigo_publico", titulo: "Existencia", render: (e) => <Link className="cifra font-medium text-marca-700 hover:underline" href={`/existencia/?id=${e.id}`}>{e.codigo_publico}</Link> },
                { clave: "ubicacion", titulo: "Ubicación", render: (e) => e.ubicacion ?? e.bodega },
                { clave: "fecha_ingreso", titulo: "Ingreso", render: (e) => fecha(e.fecha_ingreso) },
                { clave: "cantidad_fisica", titulo: "Cantidad", alinear: "derecha", render: (e) => `${num(e.cantidad_fisica)} / ${num(e.cantidad_inicial)} ${e.unidad}` },
                ...(costos ? [{ clave: "costo_unitario", titulo: "Costo unit.", alinear: "derecha" as const, render: (e: any) => clp(e.costo_unitario, 2) }] : []),
                { clave: "estado", titulo: "Estado", render: (e) => <Estado valor={e.estado} /> },
              ]}
            />
          </Tarjeta>
        )}
        <Adjuntos entidad="lote" id={l.id} titulo="Certificados y documentos" />
      </div>

      <Modal abierto={!!cambio} titulo="Cambiar estado del lote" onCerrar={() => setCambio(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} disabled={!cambio?.motivo.trim()} onClick={() => ejecutar(async () => { await api.post(`/lotes/${l.id}/estado`, cambio); setCambio(null); recargar(); }, "Estado actualizado")}>Aplicar</Boton>}>
        {cambio && (
          <div className="grid gap-3">
            <Campo etiqueta="Nuevo estado" ayuda="Agotado y Anulado los asigna el sistema.">
              <Selector value={cambio.estado} onChange={(e) => setCambio({ ...cambio, estado: e.target.value })} opciones={["DISPONIBLE", "BLOQUEADO", "CUARENTENA", "VENCIDO"].map((s) => ({ valor: s, texto: etiqueta(s) }))} />
            </Campo>
            <Campo etiqueta="Motivo" requerido><Entrada value={cambio.motivo} onChange={(e) => setCambio({ ...cambio, motivo: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
    </>
  );
}
