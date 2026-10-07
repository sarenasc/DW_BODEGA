"use client";

// Ficha de una existencia. Es el destino del QR impreso (/q/<token>) y tambien la pantalla "Escanear".

import { ArrowLeftRight, GitBranch, Handshake, Lock, MapPin, PackageOpen, Printer, ScanLine, Split, Unlock, UserRound } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EntradaCodigo } from "@/components/Escaner";
import { Aviso, Boton, Campo, Cargando, Dato, Encabezado, EnlaceBoton, Entrada, Estado, Insignia, Modal, Selector, Tabla, Tarjeta, useAccion, useAviso } from "@/components/ui";
import { abrirArchivo, api } from "@/lib/api";
import { clp, diasDesde, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function FichaExistencia() {
  const idParam = useParametro("id");
  const token = useParametro("token");
  const router = useRouter();
  const { puede } = useSesion();
  const avisar = useAviso();
  const costos = puede("costos:ver");
  const [id, setId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { datos: e, recargar } = useDatos(id ? `/existencias/${id}` : null);
  const cat = useDatos("/catalogos");
  const [qr, setQr] = useState<string | null>(null);
  const [modal, setModal] = useState<string | null>(null);
  const [form, setForm] = useState<Record<string, any>>({});
  const { ejecutar, ocupado } = useAccion();
  const ubicaciones = useDatos(e && (modal === "ubicar" || modal === "trasladar") ? "/ubicaciones" : null, { bodega_id: modal === "trasladar" ? form.bodega_id || e?.bodega_id : e?.bodega_id, almacenable: true });

  useEffect(() => {
    setError(null);
    if (idParam) setId(idParam);
    else if (token) api.get("/existencias/por-codigo", { codigo: token }).then((x) => setId(String(x.id))).catch((err) => setError(err.message));
    else setId(null);
  }, [idParam, token]);
  useEffect(() => {
    if (!id) return;
    let enlace: string | null = null;
    api.blob(`/existencias/${id}/qr`).then(({ blob }) => { enlace = URL.createObjectURL(blob); setQr(enlace); }).catch(() => setQr(null));
    return () => { if (enlace) URL.revokeObjectURL(enlace); };
  }, [id]);

  if (!id)
    return (
      <div className="mx-auto max-w-lg">
        <Encabezado titulo="Escanear existencia" descripcion="Lea el QR de una etiqueta para ver su ficha." />
        {error && <Aviso tipo="error" className="mb-3">{error}</Aviso>}
        <Tarjeta>
          <EntradaCodigo autoCamara={false} onCodigo={(c) => api.get("/existencias/por-codigo", { codigo: c }).then((x) => router.push(`/existencia/?id=${x.id}`)).catch((err) => setError(err.message))} />
        </Tarjeta>
      </div>
    );
  if (!e) return <Cargando />;

  const abrir = (m: string, inicial: Record<string, any> = {}) => { setForm(inicial); setModal(m); };
  const hacer = (accion: () => Promise<unknown>, exito: string) => ejecutar(async () => { await accion(); setModal(null); recargar(); }, exito);
  const estadoVisible = e.lote_estado && e.lote_estado !== "DISPONIBLE" && e.estado === "DISPONIBLE" ? e.lote_estado : e.estado;
  const conStock = e.cantidad_fisica > 0 && e.estado !== "ANULADA";
  const partes = Math.max(1, Number(form.partes) || 1);

  return (
    <>
      <Encabezado titulo={e.codigo_publico} descripcion={`${e.producto} · ${e.producto_codigo}`} volver="/existencias/">
        <Estado valor={estadoVisible} />
        {puede("inventario:editar") && <Boton variante="secundario" icono={<Printer className="size-4" />} onClick={() => ejecutar(async () => { await abrirArchivo("/etiquetas", { existencias: e.id }); recargar(); })}>Imprimir QR</Boton>}
        {puede("movimientos:crear") && conStock && <EnlaceBoton variante="primario" href="/consumo/" icono={<ScanLine className="size-4" />}>Consumir</EnlaceBoton>}
        {puede("trazabilidad:ver") && <EnlaceBoton href={`/trazabilidad/?existencia=${e.id}`} icono={<GitBranch className="size-4" />}>Trazabilidad</EnlaceBoton>}
      </Encabezado>

      <div className="grid gap-3 lg:grid-cols-[1fr_300px]">
        <div className="space-y-3">
          <Tarjeta>
            <div className="mb-4 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-semibold text-slate-500 uppercase">Stock físico</p><p className="cifra text-xl font-semibold">{num(e.cantidad_fisica)} <span className="text-sm text-slate-500">{e.unidad}</span></p></div>
              <div className="rounded-xl bg-amber-50 p-3"><p className="text-[11px] font-semibold text-amber-700 uppercase">Reservado</p><p className="cifra text-xl font-semibold text-amber-800">{num(e.cantidad_reservada)}</p></div>
              <div className="rounded-xl bg-marca-50 p-3"><p className="text-[11px] font-semibold text-marca-700 uppercase">Disponible</p><p className="cifra text-xl font-semibold text-marca-700">{num(e.cantidad_disponible)}</p></div>
            </div>
            <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Dato etiqueta="Lote interno">{e.lote_id ? <Link className="font-medium text-marca-700 hover:underline" href={`/lotes/detalle/?id=${e.lote_id}`}>{e.lote}</Link> : "Sin lote"}</Dato>
              <Dato etiqueta="Fecha de ingreso">{fecha(e.fecha_ingreso)} ({diasDesde(e.fecha_ingreso)} d)</Dato>
              <Dato etiqueta="Vencimiento">{fecha(e.fecha_vencimiento)}</Dato>
              <Dato etiqueta="Cantidad inicial">{num(e.cantidad_inicial)} {e.unidad}</Dato>
              <Dato etiqueta="Bodega">{e.bodega}</Dato>
              <Dato etiqueta="Ubicación">{e.ubicacion ?? <span className="text-amber-700">Sin ubicar</span>}</Dato>
              <Dato etiqueta="Granularidad">{e.granularidad.replace(/_/g, " ").toLowerCase()}{e.envases ? ` · ${e.envases} envases` : ""}</Dato>
              <Dato etiqueta="Proveedor">{e.proveedor}</Dato>
              {costos && <Dato etiqueta="Costo unitario (ingreso)">{clp(e.costo_unitario, 2)} / {e.unidad}</Dato>}
              {costos && <Dato etiqueta="Valor disponible">{clp(e.valor_disponible)}</Dato>}
              <Dato etiqueta="Documento de origen">{e.documento_origen ? <Link className="text-marca-700 hover:underline" href={`/documentos/detalle/?id=${e.documento_origen.id}`}>{e.documento_origen.numero} · {e.documento_origen.numero_documento ?? ""}</Link> : e.existencia_padre_id ? <Link className="text-marca-700 hover:underline" href={`/existencia/?id=${e.existencia_padre_id}`}>Dividida desde otra existencia</Link> : "—"}</Dato>
              <Dato etiqueta="Apertura de envase">{e.fecha_apertura ? `${fecha(e.fecha_apertura)}${e.vence_abierta ? ` · usar antes del ${fecha(e.vence_abierta)}` : ""}` : "Cerrado"}</Dato>
            </dl>
          </Tarjeta>

          {conStock && (
            <div className="no-imprimir flex flex-wrap gap-2">
              {puede("inventario:editar") && <Boton variante="secundario" icono={<MapPin className="size-4" />} onClick={() => abrir("ubicar", { ubicacion_id: e.ubicacion_id ?? "" })}>{e.ubicacion ? "Cambiar ubicación" : "Asignar ubicación"}</Boton>}
              {puede("traslados:crear") && <Boton variante="secundario" icono={<ArrowLeftRight className="size-4" />} onClick={() => abrir("trasladar", { cantidad: e.cantidad_fisica, bodega_id: "" })}>Trasladar</Boton>}
              {puede("inventario:editar") && <Boton variante="secundario" icono={<Split className="size-4" />} onClick={() => abrir("fraccionar", { partes: 2, cantidad: e.cantidad_fisica / 2, sublotes: true })}>Fraccionar</Boton>}
              {puede("reservas:crear") && <Boton variante="secundario" icono={<Handshake className="size-4" />} onClick={() => abrir("reservar", { cantidad: e.cantidad_disponible })}>Reservar</Boton>}
              {puede("prestamos:administrar") && <Boton variante="secundario" icono={<UserRound className="size-4" />} onClick={() => abrir("prestar", { cantidad: 1 })}>Prestar</Boton>}
              {puede("movimientos:crear") && !e.fecha_apertura && <Boton variante="secundario" icono={<PackageOpen className="size-4" />} onClick={() => hacer(() => api.post(`/existencias/${e.id}/abrir`), "Apertura de envase registrada")}>Abrir envase</Boton>}
              {puede("lotes:bloquear") && (
                <Boton variante="secundario" icono={e.estado === "BLOQUEADA" ? <Unlock className="size-4" /> : <Lock className="size-4" />} onClick={() => { const motivo = prompt(e.estado === "BLOQUEADA" ? "Motivo del desbloqueo:" : "Motivo del bloqueo:"); if (motivo?.trim()) hacer(() => api.post(`/existencias/${e.id}/bloqueo`, { bloquear: e.estado !== "BLOQUEADA", motivo }), "Estado actualizado"); }}>
                  {e.estado === "BLOQUEADA" ? "Desbloquear" : "Bloquear"}
                </Boton>
              )}
            </div>
          )}

          <Tarjeta titulo="Movimientos de esta existencia" sinRelleno>
            <Tabla
              filas={[...e.movimientos].reverse()}
              columnas={[
                { clave: "fecha", titulo: "Fecha", render: (m) => fechaHora(m.fecha) },
                { clave: "tipo_nombre", titulo: "Tipo", render: (m) => <>{m.tipo_nombre} {m.anulado && <Insignia tono="rojo">Anulado</Insignia>}</> },
                { clave: "cantidad", titulo: "Cantidad", alinear: "derecha", render: (m) => <span className={m.cantidad < 0 ? "text-rose-700" : "text-emerald-700"}>{m.cantidad > 0 ? "+" : ""}{num(m.cantidad)} {m.unidad}</span> },
                ...(costos ? [{ clave: "costo_total", titulo: "Costo", alinear: "derecha" as const, ocultarMovil: true, render: (m: any) => clp(m.costo_total) }] : []),
                { clave: "proceso_id", titulo: "Proceso", ocultarMovil: true, render: (m) => (m.proceso_id ? <Link className="text-marca-700 hover:underline" href={`/procesos/detalle/?id=${m.proceso_id}`}>Ver proceso</Link> : "—") },
                { clave: "motivo_texto", titulo: "Motivo", ocultarMovil: true, render: (m) => m.motivo_texto ?? m.observacion ?? "—" },
              ]}
            />
          </Tarjeta>
        </div>

        <Tarjeta titulo="Etiqueta QR" className="self-start">
          <div className="flex flex-col items-center gap-2 text-center">
            {qr ? <img src={qr} alt={`QR de ${e.codigo_publico}`} className="size-52" /> : <div className="size-52 animate-pulse rounded-lg bg-slate-100" />}
            <p className="cifra text-lg font-bold tracking-wide">{e.codigo_publico}</p>
            <p className="text-xs text-slate-500">El QR contiene solo un identificador aleatorio; los datos se consultan al sistema.</p>
            <p className="text-xs text-slate-500">Etiquetas impresas: {e.etiquetas_impresas}</p>
          </div>
        </Tarjeta>
      </div>

      <Modal abierto={modal === "ubicar"} titulo="Ubicación dentro de la bodega" onCerrar={() => setModal(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => hacer(() => api.post(`/existencias/${e.id}/ubicar`, { ubicacion_id: form.ubicacion_id ? Number(form.ubicacion_id) : null }), "Ubicación actualizada")}>Guardar</Boton>}>
        <Campo etiqueta="Ubicación"><Selector vacio="Sin ubicación" value={form.ubicacion_id ?? ""} onChange={(ev) => setForm({ ...form, ubicacion_id: ev.target.value })} opciones={(ubicaciones.datos ?? []).map((u: any) => ({ valor: u.id, texto: u.codigo_completo }))} /></Campo>
      </Modal>

      <Modal abierto={modal === "trasladar"} titulo="Trasladar" onCerrar={() => setModal(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => hacer(() => api.post("/documentos", { clase: "TRASLADO", bodega_id: e.bodega_id, bodega_destino_id: Number(form.bodega_id) || e.bodega_id, observaciones: form.observacion || null, confirmar: true, detalles: [{ existencia_id: e.id, cantidad: Number(form.cantidad), ubicacion_destino_id: form.ubicacion_id ? Number(form.ubicacion_id) : null }] }), "Traslado registrado")}>Trasladar</Boton>}>
        <div className="grid gap-3">
          <Campo etiqueta={`Cantidad (${e.unidad})`} ayuda="Un traslado parcial crea una existencia nueva con su propio QR, el mismo lote, costo y fecha de ingreso."><Entrada inputMode="decimal" value={form.cantidad ?? ""} onChange={(ev) => setForm({ ...form, cantidad: ev.target.value })} /></Campo>
          <Campo etiqueta="Bodega destino"><Selector vacio={`${e.bodega} (misma bodega)`} value={form.bodega_id ?? ""} onChange={(ev) => setForm({ ...form, bodega_id: ev.target.value, ubicacion_id: "" })} opciones={(cat.datos?.bodegas ?? []).filter((b: any) => b.id !== e.bodega_id).map((b: any) => ({ valor: b.id, texto: b.nombre }))} /></Campo>
          <Campo etiqueta="Ubicación destino"><Selector vacio="Sin ubicación" value={form.ubicacion_id ?? ""} onChange={(ev) => setForm({ ...form, ubicacion_id: ev.target.value })} opciones={(ubicaciones.datos ?? []).map((u: any) => ({ valor: u.id, texto: u.codigo_completo }))} /></Campo>
          <Campo etiqueta="Observación"><Entrada value={form.observacion ?? ""} onChange={(ev) => setForm({ ...form, observacion: ev.target.value })} /></Campo>
        </div>
      </Modal>

      <Modal abierto={modal === "fraccionar"} titulo="Fraccionar existencia" onCerrar={() => setModal(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { const r = await api.post(`/existencias/${e.id}/fraccionar`, { partes: Array.from({ length: partes }, () => ({ cantidad: Number(form.cantidad) })), crear_sublotes: !!form.sublotes }); setModal(null); recargar(); avisar("info", `Nuevas existencias: ${r.nuevas.map((n: any) => n.codigo_publico).join(", ")}`); }, "Fraccionamiento registrado")}>Fraccionar</Boton>}>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta="Número de partes"><Entrada type="number" min={1} max={200} value={form.partes ?? ""} onChange={(ev) => setForm({ ...form, partes: ev.target.value })} /></Campo>
          <Campo etiqueta={`Cantidad por parte (${e.unidad})`}><Entrada inputMode="decimal" value={form.cantidad ?? ""} onChange={(ev) => setForm({ ...form, cantidad: ev.target.value })} /></Campo>
          <label className="col-span-2 flex items-center gap-2 text-sm"><input type="checkbox" className="size-4 accent-emerald-600" checked={!!form.sublotes} onChange={(ev) => setForm({ ...form, sublotes: ev.target.checked })} /> Crear sublotes ({e.lote ?? "lote"}-01, -02…)</label>
          <Aviso className="col-span-2" tipo={partes * Number(form.cantidad) > e.cantidad_fisica ? "error" : "info"}>
            Total a fraccionar: {num(partes * Number(form.cantidad || 0))} de {num(e.cantidad_fisica)} {e.unidad}. Cada parte hereda el costo unitario y la fecha de ingreso.
          </Aviso>
        </div>
      </Modal>

      <Modal abierto={modal === "reservar"} titulo="Reservar esta existencia" onCerrar={() => setModal(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => hacer(() => api.post("/reservas", { producto_id: e.producto_id, existencia_id: e.id, cantidad: Number(form.cantidad), area: form.area || null, motivo: form.motivo || null }), "Reserva creada")}>Reservar</Boton>}>
        <div className="grid gap-3">
          <Campo etiqueta={`Cantidad (${e.unidad})`} ayuda={`Disponible: ${num(e.cantidad_disponible)} ${e.unidad}. Reservar no descuenta stock.`}><Entrada inputMode="decimal" value={form.cantidad ?? ""} onChange={(ev) => setForm({ ...form, cantidad: ev.target.value })} /></Campo>
          <Campo etiqueta="Área"><Entrada value={form.area ?? ""} onChange={(ev) => setForm({ ...form, area: ev.target.value })} /></Campo>
          <Campo etiqueta="Motivo"><Entrada value={form.motivo ?? ""} onChange={(ev) => setForm({ ...form, motivo: ev.target.value })} /></Campo>
        </div>
      </Modal>

      <Modal abierto={modal === "prestar"} titulo="Registrar préstamo" onCerrar={() => setModal(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => hacer(() => api.post("/prestamos", { existencia_id: e.id, cantidad: Number(form.cantidad), persona: form.persona ?? "", area: form.area || null, fecha_devolucion_esperada: form.fecha || null, observacion: form.observacion || null }), "Préstamo registrado")}>Prestar</Boton>}>
        <div className="grid grid-cols-2 gap-3">
          <Campo etiqueta={`Cantidad (${e.unidad})`}><Entrada inputMode="decimal" value={form.cantidad ?? ""} onChange={(ev) => setForm({ ...form, cantidad: ev.target.value })} /></Campo>
          <Campo etiqueta="Devolución esperada"><Entrada type="date" value={form.fecha ?? ""} onChange={(ev) => setForm({ ...form, fecha: ev.target.value })} /></Campo>
          <Campo etiqueta="Persona" requerido><Entrada value={form.persona ?? ""} onChange={(ev) => setForm({ ...form, persona: ev.target.value })} /></Campo>
          <Campo etiqueta="Área"><Entrada value={form.area ?? ""} onChange={(ev) => setForm({ ...form, area: ev.target.value })} /></Campo>
          <Campo etiqueta="Observación" className="col-span-2"><Entrada value={form.observacion ?? ""} onChange={(ev) => setForm({ ...form, observacion: ev.target.value })} /></Campo>
        </div>
      </Modal>
    </>
  );
}
