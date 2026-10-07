"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { SelectorExistencia } from "@/components/Selectores";
import { Boton, Campo, Cargando, Encabezado, Entrada, Estado, Insignia, Modal, Pestanas, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { fecha, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Prestamos() {
  const { puede } = useSesion();
  const editable = puede("prestamos:administrar");
  const [tab, setTab] = useState("pendientes");
  const { datos, recargar } = useDatos("/prestamos", { tam: 200, vencidos: tab === "vencidos" ? true : undefined, estado: tab === "devueltos" ? "DEVUELTO" : undefined });
  const [form, setForm] = useState<Record<string, any> | null>(null);
  const [devolver, setDevolver] = useState<{ p: any; cantidad: string } | null>(null);
  const { ejecutar, ocupado } = useAccion();
  const filas = (datos?.items ?? []).filter((p: any) => tab !== "pendientes" || ["ACTIVO", "PARCIAL"].includes(p.estado));

  return (
    <>
      <Encabezado titulo="Préstamos" descripcion="Producto, cantidad, persona, área, fecha de préstamo, devolución esperada y real.">
        {editable && <Boton icono={<Plus className="size-4" />} onClick={() => setForm({ cantidad: "1" })}>Nuevo préstamo</Boton>}
      </Encabezado>
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "pendientes", texto: "Pendientes" }, { valor: "vencidos", texto: "Vencidos" }, { valor: "devueltos", texto: "Devueltos" }, { valor: "todos", texto: "Todos" }]} />
      <Tarjeta sinRelleno>
        {!datos ? (
          <Cargando />
        ) : (
          <Tabla
            filas={filas}
            vacio="No hay préstamos en esta vista."
            columnas={[
              { clave: "numero", titulo: "Préstamo", render: (p) => <span className="cifra font-medium">{p.numero}</span> },
              { clave: "producto", titulo: "Producto", render: (p) => <>{p.producto}<Link href={`/existencia/?id=${p.existencia_id}`} className="block text-xs text-marca-700 hover:underline">{p.codigo_publico} · {p.bodega}</Link></> },
              { clave: "persona", titulo: "Persona", render: (p) => <>{p.persona}<span className="block text-xs text-slate-500">{p.area}</span></> },
              { clave: "cantidad", titulo: "Prestado", alinear: "derecha", render: (p) => `${num(p.cantidad)} ${p.unidad}` },
              { clave: "pendiente", titulo: "Pendiente", alinear: "derecha", render: (p) => <b>{num(p.pendiente)}</b> },
              { clave: "fecha_prestamo", titulo: "Préstamo", ocultarMovil: true, render: (p) => fecha(p.fecha_prestamo) },
              { clave: "fecha_devolucion_esperada", titulo: "Devolución esperada", render: (p) => <span className={p.vencido ? "font-semibold text-rose-700" : ""}>{fecha(p.fecha_devolucion_esperada)}</span> },
              { clave: "fecha_devolucion_real", titulo: "Devolución real", ocultarMovil: true, render: (p) => fecha(p.fecha_devolucion_real) },
              { clave: "estado", titulo: "Estado", render: (p) => (p.vencido ? <Insignia tono="rojo">VENCIDO</Insignia> : <Estado valor={p.estado} />) },
              ...(editable ? [{ clave: "x", titulo: "", render: (p: any) => ["ACTIVO", "PARCIAL"].includes(p.estado) && <Boton tam="sm" variante="secundario" onClick={() => setDevolver({ p, cantidad: String(p.pendiente) })}>Devolver</Boton> }] : []),
            ]}
          />
        )}
      </Tarjeta>

      <Modal abierto={!!form} titulo="Nuevo préstamo" onCerrar={() => setForm(null)}
        pie={<Boton cargando={ocupado} disabled={!form?.existencia || !form?.persona?.trim()} onClick={() => ejecutar(async () => { await api.post("/prestamos", { existencia_id: form!.existencia.id, cantidad: Number(String(form!.cantidad).replace(",", ".")), persona: form!.persona, area: form!.area || null, fecha_devolucion_esperada: form!.fecha || null, observacion: form!.observacion || null }); setForm(null); recargar(); }, "Préstamo registrado")}>Registrar</Boton>}>
        {form && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Existencia" requerido className="sm:col-span-2"><SelectorExistencia valor={form.existencia ?? null} onCambio={(e) => setForm({ ...form, existencia: e })} /></Campo>
            <Campo etiqueta={`Cantidad${form.existencia ? ` (${form.existencia.unidad})` : ""}`} requerido><Entrada inputMode="decimal" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} /></Campo>
            <Campo etiqueta="Devolución esperada"><Entrada type="date" value={form.fecha ?? ""} onChange={(e) => setForm({ ...form, fecha: e.target.value })} /></Campo>
            <Campo etiqueta="Persona" requerido><Entrada value={form.persona ?? ""} onChange={(e) => setForm({ ...form, persona: e.target.value })} /></Campo>
            <Campo etiqueta="Área"><Entrada value={form.area ?? ""} onChange={(e) => setForm({ ...form, area: e.target.value })} /></Campo>
            <Campo etiqueta="Observación" className="sm:col-span-2"><Entrada value={form.observacion ?? ""} onChange={(e) => setForm({ ...form, observacion: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
      <Modal abierto={!!devolver} titulo={`Devolución de ${devolver?.p.numero ?? ""}`} onCerrar={() => setDevolver(null)} ancho="max-w-sm"
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { await api.post(`/prestamos/${devolver!.p.id}/devolver`, { cantidad: Number(devolver!.cantidad.replace(",", ".")) }); setDevolver(null); recargar(); }, "Devolución registrada")}>Registrar devolución</Boton>}>
        {devolver && <Campo etiqueta={`Cantidad devuelta (${devolver.p.unidad})`} ayuda={`Pendiente: ${num(devolver.p.pendiente)}. Vuelve a la misma existencia.`}><Entrada inputMode="decimal" autoFocus value={devolver.cantidad} onChange={(e) => setDevolver({ ...devolver, cantidad: e.target.value })} /></Campo>}
      </Modal>
    </>
  );
}
