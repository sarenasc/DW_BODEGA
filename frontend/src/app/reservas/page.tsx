"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { SelectorProceso, SelectorProducto } from "@/components/Selectores";
import { Aviso, Boton, Campo, Cargando, Encabezado, Entrada, Estado, Modal, Paginacion, Pestanas, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Reservas() {
  const { puede } = useSesion();
  const editable = puede("reservas:crear");
  const [estado, setEstado] = useState("ACTIVA");
  const [pagina, setPagina] = useState(1);
  const cat = useDatos("/catalogos");
  const { datos, cargando, recargar } = useDatos("/reservas", { estado: estado === "TODAS" ? undefined : estado, pagina, tam: 50 });
  const [form, setForm] = useState<Record<string, any> | null>(null);
  const [disp, setDisp] = useState<any>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  const { ejecutar, ocupado } = useAccion();
  useEffect(() => setPagina(1), [estado]);

  // Disponibilidad en vivo del producto (y bodega) elegidos.
  const pid = form?.producto?.id;
  const bid = form?.bodega_id;
  useEffect(() => {
    if (!pid) return setDisp(null);
    api.get("/reservas/disponibilidad", { producto_id: pid, bodega_id: bid }).then(setDisp).catch(() => setDisp(null));
  }, [pid, bid]);

  async function crear() {
    setFallo(null);
    try {
      await api.post("/reservas", {
        producto_id: form!.producto.id,
        cantidad: Number(String(form!.cantidad).replace(",", ".")),
        bodega_id: form!.bodega_id ? Number(form!.bodega_id) : null,
        proceso_id: form!.proceso?.id ?? null,
        area: form!.area || null,
        motivo: form!.motivo || null,
        documento_referencia: form!.documento_referencia || null,
        fecha_vencimiento: form!.fecha_vencimiento ? new Date(`${form!.fecha_vencimiento}T23:59:00`).toISOString() : null,
      });
      setForm(null);
      recargar();
    } catch (e: any) {
      setFallo(e.message);
    }
  }
  const cerrar = (r: any, accion: "liberar" | "anular") => {
    const motivo = prompt(accion === "liberar" ? "Liberar la reserva devuelve al disponible el saldo no consumido.\nMotivo (opcional):" : "Motivo de la anulación:");
    if (motivo === null) return;
    ejecutar(async () => { await api.post(`/reservas/${r.id}/${accion}`, { motivo }); recargar(); }, accion === "liberar" ? "Reserva liberada" : "Reserva anulada");
  };

  return (
    <>
      <Encabezado titulo="Reservas de stock" descripcion="Reservar compromete stock antes del consumo, sin descontarlo. Stock disponible = stock físico − stock reservado.">
        {editable && <Boton icono={<Plus className="size-4" />} onClick={() => { setFallo(null); setForm({ cantidad: "" }); }}>Nueva reserva</Boton>}
      </Encabezado>
      <Pestanas valor={estado} onCambio={setEstado} opciones={["ACTIVA", "CONSUMIDA", "LIBERADA", "VENCIDA", "ANULADA", "TODAS"].map((e) => ({ valor: e, texto: e.charAt(0) + e.slice(1).toLowerCase() + "s" }))} />
      <Tarjeta sinRelleno>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            vacio="No hay reservas en este estado."
            columnas={[
              { clave: "numero", titulo: "Reserva", render: (r) => <span className="cifra font-medium">{r.numero}</span> },
              { clave: "producto", titulo: "Producto", render: (r) => <><Link href={`/productos/detalle/?id=${r.producto_id}`} className="font-medium text-slate-900 hover:underline">{r.producto}</Link><span className="block text-xs text-slate-500">{[r.bodega, r.lote && `lote ${r.lote}`, r.existencia].filter(Boolean).join(" · ") || "Cualquier bodega"}</span></> },
              { clave: "cantidad", titulo: "Reservado", alinear: "derecha", render: (r) => `${num(r.cantidad)} ${r.unidad}` },
              { clave: "cantidad_consumida", titulo: "Consumido", alinear: "derecha", ocultarMovil: true, render: (r) => num(r.cantidad_consumida) },
              { clave: "pendiente", titulo: "Pendiente", alinear: "derecha", render: (r) => <b>{num(r.pendiente)}</b> },
              { clave: "proceso", titulo: "Proceso / área", ocultarMovil: true, render: (r) => <>{r.proceso_id ? <Link className="text-marca-700 hover:underline" href={`/procesos/detalle/?id=${r.proceso_id}`}>{r.proceso}</Link> : "—"}<span className="block text-xs text-slate-500">{r.area}</span></> },
              { clave: "motivo", titulo: "Motivo", ocultarMovil: true, render: (r) => <span className="block max-w-56 truncate" title={r.motivo ?? ""}>{r.motivo ?? "—"}{r.documento_referencia && ` · ${r.documento_referencia}`}</span> },
              { clave: "fecha", titulo: "Creada", ocultarMovil: true, render: (r) => <>{fecha(r.fecha)}<span className="block text-xs text-slate-500">{r.usuario}</span></> },
              { clave: "fecha_vencimiento", titulo: "Vence", ocultarMovil: true, render: (r) => fechaHora(r.fecha_vencimiento) },
              { clave: "estado", titulo: "Estado", render: (r) => <Estado valor={r.estado} /> },
              ...(editable ? [{ clave: "x", titulo: "", alinear: "derecha" as const, render: (r: any) => r.estado === "ACTIVA" && <span className="flex justify-end gap-1"><Boton tam="sm" variante="secundario" onClick={() => cerrar(r, "liberar")}>Liberar</Boton>{r.cantidad_consumida === 0 && <Boton tam="sm" variante="fantasma" onClick={() => cerrar(r, "anular")}>Anular</Boton>}</span> }] : []),
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>

      <Modal abierto={!!form} titulo="Nueva reserva de stock" onCerrar={() => setForm(null)} pie={<><Boton variante="secundario" onClick={() => setForm(null)}>Cancelar</Boton><Boton cargando={ocupado} disabled={!form?.producto || !(Number(String(form?.cantidad).replace(",", ".")) > 0)} onClick={crear}>Reservar</Boton></>}>
        {form && (
          <div className="grid gap-3 sm:grid-cols-2">
            {fallo && <Aviso tipo="error" className="sm:col-span-2">{fallo}</Aviso>}
            <Campo etiqueta="Producto" requerido className="sm:col-span-2"><SelectorProducto valor={form.producto ?? null} onCambio={(p) => setForm({ ...form, producto: p })} autoFocus /></Campo>
            {disp && (
              <div className="grid grid-cols-3 gap-2 text-center sm:col-span-2">
                <div className="rounded-lg bg-slate-50 p-2"><p className="text-[10px] font-semibold text-slate-500 uppercase">Stock físico</p><p className="cifra font-semibold">{num(disp.stock_fisico)} {disp.unidad}</p></div>
                <div className="rounded-lg bg-amber-50 p-2"><p className="text-[10px] font-semibold text-amber-700 uppercase">Reservado</p><p className="cifra font-semibold text-amber-800">{num(disp.stock_reservado)}</p></div>
                <div className="rounded-lg bg-marca-50 p-2"><p className="text-[10px] font-semibold text-marca-700 uppercase">Disponible</p><p className="cifra font-semibold text-marca-700">{num(disp.stock_disponible)}</p></div>
              </div>
            )}
            <Campo etiqueta={`Cantidad a reservar${form.producto ? ` (${form.producto.unidad_base})` : ""}`} requerido error={disp && Number(String(form.cantidad).replace(",", ".")) > disp.stock_disponible ? "Supera el stock disponible." : null}>
              <Entrada inputMode="decimal" value={form.cantidad} onChange={(e) => setForm({ ...form, cantidad: e.target.value })} />
            </Campo>
            <Campo etiqueta="Bodega" ayuda="Vacío = cualquier bodega."><Selector vacio="Cualquier bodega" value={form.bodega_id ?? ""} onChange={(e) => setForm({ ...form, bodega_id: e.target.value })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} /></Campo>
            <Campo etiqueta="Proceso" className="sm:col-span-2" ayuda="El consumo de este proceso irá descontando la reserva."><SelectorProceso valor={form.proceso ?? null} onCambio={(p) => setForm({ ...form, proceso: p })} estado="" /></Campo>
            <Campo etiqueta="Área"><Entrada value={form.area ?? ""} onChange={(e) => setForm({ ...form, area: e.target.value })} /></Campo>
            <Campo etiqueta="Documento de referencia"><Entrada value={form.documento_referencia ?? ""} onChange={(e) => setForm({ ...form, documento_referencia: e.target.value })} /></Campo>
            <Campo etiqueta="Motivo"><Entrada value={form.motivo ?? ""} onChange={(e) => setForm({ ...form, motivo: e.target.value })} /></Campo>
            <Campo etiqueta="Vigente hasta" ayuda="Al vencer se libera sola y genera una alerta."><Entrada type="date" value={form.fecha_vencimiento ?? ""} onChange={(e) => setForm({ ...form, fecha_vencimiento: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
    </>
  );
}
