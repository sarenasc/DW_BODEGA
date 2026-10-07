"use client";

import { Ban, GitBranch, Lock, LockOpen, Play, RefreshCw, ScanLine } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { BarrasLista } from "@/components/Graficos";
import { Aviso, Boton, Campo, Cargando, Dato, Encabezado, EnlaceBoton, Entrada, Estado, Indicador, Insignia, Modal, Pestanas, Selector, Tabla, Tarjeta, useAccion, useAviso } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, etiqueta, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function DetalleProceso() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const avisar = useAviso();
  const costos = puede("costos:ver");
  const { datos: p, error, setDatos, recargar } = useDatos(id ? `/procesos/${id}` : null);
  const consumos = useDatos(id ? `/procesos/${id}/consumos` : null);
  const val = useDatos("/procesos/valores");
  const [tab, setTab] = useState("consumos");
  const [cierre, setCierre] = useState<{ kilos: string; observacion: string } | null>(null);
  const [falloCierre, setFalloCierre] = useState<string | null>(null);
  const { ejecutar, ocupado } = useAccion();
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!p) return <Cargando />;
  const c = p.costos;
  const abierto = p.estado === "ABIERTO";

  const actualizar = () =>
    ejecutar(async () => {
      const r = await api.post(`/procesos/${p.id}/actualizar`);
      setDatos(r);
      avisar("info", r.sincronizacion.cambios ? `${r.sincronizacion.cambios} campo(s) actualizado(s) desde producción.` : "Sin cambios en producción.");
      setTab("cambios");
    });
  async function cerrar(sincronizar: boolean) {
    setFalloCierre(null);
    try {
      const r = await api.post(`/procesos/${p.id}/cerrar`, { actualizar: sincronizar, kilos: !sincronizar && cierre!.kilos !== "" ? Number(cierre!.kilos.replace(",", ".")) : null, observacion: cierre!.observacion || null });
      setDatos(r);
      setCierre(null);
      consumos.recargar();
      avisar("exito", "Proceso cerrado con kilos definitivos.");
    } catch (e: any) {
      setFalloCierre(e.message);
      recargar();
    }
  }
  const conMotivo = (texto: string, accion: string, exito: string) => {
    const motivo = prompt(texto);
    if (motivo?.trim()) ejecutar(async () => setDatos(await api.post(`/procesos/${p.id}/${accion}`, { motivo })), exito);
  };

  return (
    <>
      <Encabezado titulo={p.codigo} descripcion={[p.especie, p.variedad, p.productor, fecha(p.fecha)].filter(Boolean).join(" · ")} volver="/procesos/">
        <Estado valor={p.estado} />
        {p.estado === "BORRADOR" && puede("procesos:abrir") && <Boton icono={<Play className="size-4" />} onClick={() => ejecutar(async () => setDatos(await api.post(`/procesos/${p.id}/abrir`)), "Proceso abierto")}>Abrir proceso</Boton>}
        {abierto && puede("movimientos:crear") && <EnlaceBoton href="/consumo/" icono={<ScanLine className="size-4" />}>Consumir</EnlaceBoton>}
        {abierto && p.tiene_fuente && puede("procesos:actualizar") && <Boton variante="secundario" icono={<RefreshCw className="size-4" />} cargando={ocupado} onClick={actualizar}>Actualizar proceso</Boton>}
        {abierto && puede("procesos:cerrar") && <Boton icono={<Lock className="size-4" />} onClick={() => { setFalloCierre(null); setCierre({ kilos: p.kilos_base != null ? String(p.kilos_base) : "", observacion: "" }); }}>Cerrar proceso</Boton>}
        {p.estado === "CERRADO" && puede("procesos:reabrir") && <Boton variante="secundario" icono={<LockOpen className="size-4" />} onClick={() => conMotivo("Motivo de la reapertura:", "reabrir", "Proceso reabierto")}>Reabrir</Boton>}
        {(p.estado === "BORRADOR" || abierto) && puede("procesos:cerrar") && <Boton variante="fantasma" icono={<Ban className="size-4 text-rose-600" />} onClick={() => conMotivo("Motivo de la anulación del proceso:", "anular", "Proceso anulado")}>Anular</Boton>}
        {puede("trazabilidad:ver") && <EnlaceBoton href={`/trazabilidad/?proceso=${p.id}`} icono={<GitBranch className="size-4" />}>Trazabilidad</EnlaceBoton>}
      </Encabezado>

      {p.estado === "CERRADO" && (
        <Aviso tipo={p.cerrado_sincronizado === false ? "alerta" : "exito"} className="mb-3" titulo={p.cerrado_sincronizado === false ? "Cerrado manualmente, sin actualizar desde producción" : p.cerrado_sincronizado ? "Cerrado y sincronizado con producción" : "Proceso cerrado"}>
          {fechaHora(p.cerrado_en)} · {p.cerrado_por_nombre} · kilos definitivos: <b>{num(p.kilos_definitivos, 0)}</b>
          {p.tiene_fuente && <> · última sincronización: {fechaHora(p.ultima_sincronizacion)}</>}
        </Aviso>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Indicador titulo="Costo total del proceso" valor={costos ? clp(c.costo_total) : "—"} detalle="Suma de consumos valorizados" />
        <Indicador titulo={c.base_costeo_nombre} valor={`${num(c.kilos, 0)} kg`} tono={c.estado_kilos === "DEFINITIVO" ? "ok" : "alerta"} detalle={`Kilos ${c.estado_kilos.toLowerCase()}s`} />
        <Indicador titulo="Costo por kilo" valor={costos && c.costo_por_kilo != null ? clp(c.costo_por_kilo, 2) : "—"} detalle={c.kilos ? "Costo total ÷ kilos base" : "Sin kilos informados"} />
        <Indicador titulo="Sincronización" valor={p.tiene_fuente ? (p.ultima_sincronizacion ? fechaHora(p.ultima_sincronizacion) : "Nunca") : "Manual"} detalle={p.tiene_fuente ? `${p.fuente} · ${p.capturas} lectura(s)` : "Sin origen externo"} />
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-3">
        <Tarjeta titulo="Información del proceso" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Dato etiqueta="Id externo">{p.id_externo}</Dato>
            <Dato etiqueta="Temporada">{p.temporada_codigo}</Dato>
            <Dato etiqueta="Fecha">{fecha(p.fecha)}</Dato>
            <Dato etiqueta="Horario">{[p.hora_inicio, p.hora_termino].filter(Boolean).join(" – ") || "—"}</Dato>
            <Dato etiqueta="Exportadora">{p.exportadora}</Dato>
            <Dato etiqueta="Productor">{p.productor}{p.codigo_productor ? ` (${p.codigo_productor})` : ""}</Dato>
            <Dato etiqueta="Campo / predio">{[p.campo, p.predio].filter(Boolean).join(" / ")}</Dato>
            <Dato etiqueta="Lote productivo">{p.lote_productivo ?? p.numero_lote}</Dato>
            <Dato etiqueta="Kilos recepcionados">{num(p.kilos_recepcionados, 0)}</Dato>
            <Dato etiqueta="Kilos procesados">{num(p.kilos_procesados, 0)}</Dato>
            <Dato etiqueta="Kilos producidos">{num(p.kilos_producidos, 0)}</Dato>
            <Dato etiqueta="Kilos despachados">{num(p.kilos_despachados, 0)}</Dato>
            <Dato etiqueta="Bins / cajas">{num(p.bins, 0)} / {num(p.cajas, 0)}</Dato>
            <Dato etiqueta="Turno / línea">{[p.turno, p.linea].filter(Boolean).join(" / ")}</Dato>
            <Dato etiqueta="Guía">{p.guia}</Dato>
            <Dato etiqueta="Estado en origen">{p.estado_externo}</Dato>
            {Object.entries(p.datos_adicionales ?? {}).filter(([, v]) => v !== null && v !== "").slice(0, 12).map(([k, v]) => (
              <Dato key={k} etiqueta={k.replace(/_/g, " ")}>{String(v)}</Dato>
            ))}
          </dl>
          {abierto && puede("procesos:actualizar") && (
            <div className="mt-4 flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
              <Campo etiqueta="Base de costeo por kilo" className="w-64" ayuda="Vacío = configuración general.">
                <Selector vacio="Configuración general" value={p.base_costeo ?? ""} onChange={(e) => ejecutar(async () => setDatos(await api.put(`/procesos/${p.id}`, { base_costeo: e.target.value || null })))} opciones={(val.datos?.bases_costeo ?? []).map((b: any) => ({ valor: b.codigo, texto: b.nombre }))} />
              </Campo>
              {!p.tiene_fuente && (
                <Campo etiqueta="Kilos procesados" className="w-44">
                  <Entrada inputMode="decimal" defaultValue={p.kilos_procesados ?? ""} onBlur={(e) => e.target.value !== String(p.kilos_procesados ?? "") && ejecutar(async () => setDatos(await api.put(`/procesos/${p.id}`, { kilos_procesados: e.target.value === "" ? null : Number(e.target.value) })), "Kilos actualizados")} />
                </Campo>
              )}
            </div>
          )}
        </Tarjeta>
        {costos && (
          <Tarjeta titulo="Costo por producto">
            <BarrasLista vacio="Aún no hay consumos." datos={c.por_producto.map((x: any) => ({ nombre: x.producto, valor: x.costo, detalle: `${num(x.cantidad)} ${x.unidad}` }))} />
          </Tarjeta>
        )}
      </div>

      <div className="mt-4">
        <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "consumos", texto: "Consumos", contador: consumos.datos?.length }, { valor: "cambios", texto: "Historial de cambios", contador: p.cambios.length }]} />
        <Tarjeta sinRelleno>
          {tab === "consumos" ? (
            <Tabla
              filas={consumos.datos ?? []}
              vacio="Este proceso aún no tiene consumos."
              columnas={[
                { clave: "fecha", titulo: "Fecha", render: (m) => fechaHora(m.fecha) },
                { clave: "tipo_nombre", titulo: "Tipo", render: (m) => <>{m.tipo === "ANULACION" ? <Insignia tono="rojo">Anulación</Insignia> : m.tipo_nombre}{m.anulado && <span className="ml-1"><Insignia tono="rojo">Anulado</Insignia></span>}</> },
                { clave: "producto", titulo: "Producto", render: (m) => <span className="font-medium text-slate-900">{m.producto}</span> },
                { clave: "codigo_publico", titulo: "Existencia (QR)", render: (m) => <Link className="cifra text-marca-700 hover:underline" href={`/existencia/?id=${m.existencia_id}`}>{m.codigo_publico}</Link> },
                { clave: "lote", titulo: "Lote", ocultarMovil: true },
                { clave: "cantidad", titulo: "Cantidad", alinear: "derecha", render: (m) => `${num(-m.cantidad)} ${m.unidad}` },
                ...(costos ? [{ clave: "costo_unitario", titulo: "Costo unit.", alinear: "derecha" as const, ocultarMovil: true, render: (m: any) => clp(m.costo_unitario, 2) }, { clave: "costo_total", titulo: "Costo", alinear: "derecha" as const, render: (m: any) => clp(-m.costo_total) }] : []),
                { clave: "ubicacion", titulo: "Bodega / ubicación", ocultarMovil: true, render: (m) => m.ubicacion ?? m.bodega },
                { clave: "usuario", titulo: "Usuario", ocultarMovil: true },
              ]}
            />
          ) : (
            <Tabla
              filas={p.cambios}
              vacio="Sin cambios registrados."
              columnas={[
                { clave: "fecha", titulo: "Fecha", render: (x) => fechaHora(x.fecha) },
                { clave: "campo", titulo: "Campo", render: (x) => etiqueta(x.campo.replace("extra.", "")) },
                { clave: "valor_anterior", titulo: "Valor anterior", render: (x) => <span className="text-slate-500 line-through">{x.valor_anterior ?? "—"}</span> },
                { clave: "valor_nuevo", titulo: "Valor nuevo", render: (x) => <b>{x.valor_nuevo ?? "—"}</b> },
                { clave: "origen", titulo: "Origen", render: (x) => <Insignia tono={x.origen === "MANUAL" ? "ambar" : "azul"}>{etiqueta(x.origen)}</Insignia> },
                { clave: "usuario", titulo: "Usuario", render: (x) => x.usuario ?? "Sistema" },
              ]}
            />
          )}
        </Tarjeta>
      </div>

      <Modal abierto={!!cierre} titulo={`Cerrar proceso ${p.codigo}`} onCerrar={() => setCierre(null)} ancho="max-w-lg">
        {cierre && (
          <div className="space-y-4">
            {falloCierre && <Aviso tipo="error" titulo="No se pudo cerrar">{falloCierre}</Aviso>}
            <p className="text-sm text-slate-600">Al cerrar se guardan los kilos definitivos y el costo por kilo deja de ser provisorio. El proceso no volverá a consultar la base productiva.</p>
            {costos && <p className="rounded-lg bg-slate-50 p-3 text-sm">Costo total: <b>{clp(c.costo_total)}</b> · {p.reservas_activas} reserva(s) activa(s) se liberarán.</p>}
            {p.tiene_fuente ? (
              <>
                <Boton tam="lg" className="w-full" icono={<RefreshCw className="size-5" />} cargando={ocupado} onClick={() => cerrar(true)}>
                  ACTUALIZAR Y CERRAR
                </Boton>
                <p className="-mt-2 text-center text-xs text-slate-500">Lee los datos finales desde producción y cierra con esos kilos.</p>
                {puede("procesos:cerrar_sin_sincronizar") ? (
                  <details className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                    <summary className="cursor-pointer text-sm font-medium text-amber-900">Cerrar sin actualizar (permiso especial)</summary>
                    <div className="mt-3 grid gap-3">
                      <Campo etiqueta={`Kilos definitivos (${c.base_costeo_nombre.toLowerCase()})`}><Entrada inputMode="decimal" value={cierre.kilos} onChange={(e) => setCierre({ ...cierre, kilos: e.target.value })} /></Campo>
                      <Campo etiqueta="Motivo"><Entrada value={cierre.observacion} onChange={(e) => setCierre({ ...cierre, observacion: e.target.value })} /></Campo>
                      <Boton variante="secundario" onClick={() => cerrar(false)}>Cerrar sin actualizar</Boton>
                      <p className="text-xs text-amber-800">Quedará marcado como cierre manual y generará una alerta.</p>
                    </div>
                  </details>
                ) : (
                  <p className="text-center text-xs text-slate-500">Cerrar sin actualizar requiere un permiso especial.</p>
                )}
              </>
            ) : (
              <div className="grid gap-3">
                <Campo etiqueta={`Kilos definitivos (${c.base_costeo_nombre.toLowerCase()})`} ayuda="Puede quedar vacío si el proceso no tiene kilos asociados."><Entrada inputMode="decimal" value={cierre.kilos} onChange={(e) => setCierre({ ...cierre, kilos: e.target.value })} /></Campo>
                <Campo etiqueta="Observación"><Entrada value={cierre.observacion} onChange={(e) => setCierre({ ...cierre, observacion: e.target.value })} /></Campo>
                <Boton tam="lg" icono={<Lock className="size-5" />} onClick={() => cerrar(false)}>Cerrar proceso</Boton>
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
