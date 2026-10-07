"use client";

import { AlertTriangle, BellRing, CheckCheck, ExternalLink, Info, Play, Settings2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, Cargando, cx, Encabezado, Entrada, Estado, Indicador, Insignia, Interruptor, Modal, Paginacion, Pestanas, Selector, Tarjeta, useAccion, useAviso } from "@/components/ui";
import { api } from "@/lib/api";
import { etiqueta, fechaHora } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

const BORDE: Record<string, string> = { CRITICA: "border-l-rose-600", ALTA: "border-l-rose-400", MEDIA: "border-l-amber-400", BAJA: "border-l-sky-400", INFORMATIVA: "border-l-slate-300" };

export default function Alertas() {
  const { puede } = useSesion();
  const avisar = useAviso();
  const gestionar = puede("alertas:gestionar");
  const [tab, setTab] = useState("abiertas");
  const [f, setF] = useState<Record<string, any>>({});
  const [pagina, setPagina] = useState(1);
  const op = useDatos("/alertas/opciones");
  const cat = useDatos("/catalogos");
  const resumen = useDatos("/alertas/resumen");
  const lista = useDatos(tab === "reglas" ? null : "/alertas", { ...f, abiertas: tab === "abiertas" ? true : tab === "cerradas" ? false : undefined, pagina, tam: 30 });
  const reglas = useDatos<any[]>(tab === "reglas" ? "/reglas-alertas" : null);
  const [cierre, setCierre] = useState<{ alerta: any; estado: string; observacion: string } | null>(null);
  const { ejecutar, ocupado } = useAccion();
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave, tab]);
  const refrescar = () => { lista.recargar(); resumen.recargar(); };
  const cambiar = (a: any, estado: string, observacion?: string) => ejecutar(async () => { await api.post(`/alertas/${a.id}/estado`, { estado, observacion }); refrescar(); });
  const r = resumen.datos;

  return (
    <>
      <Encabezado titulo="Centro de alertas" descripcion="Alertas persistentes con estado, severidad y enlace a la entidad relacionada. Las reglas son configurables.">
        {gestionar && <Boton variante="secundario" icono={<Play className="size-4" />} cargando={ocupado} onClick={() => ejecutar(async () => { const x = await api.post("/alertas/evaluar"); avisar("info", `Evaluación completa: ${x.creadas} nueva(s), ${x.resueltas} resuelta(s) automáticamente.`); refrescar(); })}>Evaluar reglas ahora</Boton>}
      </Encabezado>
      {r && (
        <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
          <Indicador titulo="Nuevas" valor={r.nuevas} tono={r.nuevas ? "alerta" : "ok"} icono={<BellRing className="size-4" />} />
          <Indicador titulo="Críticas" valor={r.criticas} tono={r.criticas ? "peligro" : "ok"} icono={<AlertTriangle className="size-4" />} />
          <Indicador titulo="Stock bajo" valor={r.stock_bajo} />
          <Indicador titulo="Por vencer" valor={r.proximos_a_vencer} />
          <Indicador titulo="Vencidos" valor={r.vencidos} tono={r.vencidos ? "peligro" : "normal"} />
          <Indicador titulo="Fuera de FIFO" valor={r.fuera_de_fifo} />
          <Indicador titulo="Reservas vencidas" valor={r.reservas_vencidas} />
          <Indicador titulo="Procesos sin sincr." valor={r.procesos_sin_sincronizar} />
        </div>
      )}
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "abiertas", texto: "Abiertas", contador: r?.abiertas }, { valor: "cerradas", texto: "Resueltas y descartadas" }, { valor: "todas", texto: "Todas" }, ...(puede("alertas:ver") ? [{ valor: "reglas", texto: "Reglas" }] : [])]} />

      {tab !== "reglas" ? (
        <>
          <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
            <Selector vacio="Todos los tipos" value={f.tipo ?? ""} onChange={(e) => setF({ ...f, tipo: e.target.value })} opciones={(op.datos?.tipos ?? []).map((t: string) => ({ valor: t, texto: etiqueta(t) }))} />
            <Selector vacio="Toda severidad" value={f.severidad ?? ""} onChange={(e) => setF({ ...f, severidad: e.target.value })} opciones={(op.datos?.severidades ?? []).map((t: string) => ({ valor: t, texto: etiqueta(t) }))} />
            <Selector vacio="Todos los estados" value={f.estado ?? ""} onChange={(e) => setF({ ...f, estado: e.target.value })} opciones={(op.datos?.estados ?? []).map((t: string) => ({ valor: t, texto: etiqueta(t) }))} />
            <Selector vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => setF({ ...f, bodega_id: e.target.value })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} />
          </div>
          {!lista.datos ? (
            <Cargando />
          ) : (
            <ul className="space-y-2">
              {lista.datos.items.length === 0 && <li className="rounded-xl border border-slate-200 bg-white p-10 text-center text-sm text-slate-500">No hay alertas para estos filtros.</li>}
              {lista.datos.items.map((a: any) => (
                <li key={a.id} className={cx("rounded-xl border border-l-4 border-slate-200 bg-white p-3 shadow-sm sm:p-4", BORDE[a.severidad], a.estado === "NUEVA" && "bg-amber-50/40")}>
                  <div className="flex flex-wrap items-start gap-x-3 gap-y-2">
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex flex-wrap items-center gap-1.5">
                        <Estado valor={a.severidad} />
                        <Insignia>{etiqueta(a.tipo)}</Insignia>
                        <Estado valor={a.estado} />
                        {a.bodega && <span className="text-xs text-slate-500">{a.bodega}</span>}
                      </div>
                      <p className={cx("text-sm text-slate-900", a.estado === "NUEVA" ? "font-semibold" : "font-medium")}>{a.titulo}</p>
                      {a.descripcion && <p className="mt-0.5 text-sm text-slate-600">{a.descripcion}</p>}
                      <p className="mt-1 text-xs text-slate-500">
                        {fechaHora(a.fecha_creacion)}
                        {a.fecha_resolucion && ` · cerrada ${fechaHora(a.fecha_resolucion)}${a.resuelta_por_nombre ? ` por ${a.resuelta_por_nombre}` : ""}`}
                        {a.observacion && ` · “${a.observacion}”`}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {a.enlace && <Link href={a.enlace} className="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-300 px-3 text-xs font-medium text-slate-700 hover:bg-slate-50"><ExternalLink className="size-3.5" /> Ver {a.entidad}</Link>}
                      {a.estado === "NUEVA" && <Boton tam="sm" variante="fantasma" onClick={() => cambiar(a, "LEIDA")}>Marcar leída</Boton>}
                      {gestionar && a.abierta && a.estado !== "EN_GESTION" && <Boton tam="sm" variante="secundario" onClick={() => cambiar(a, "EN_GESTION")}>En gestión</Boton>}
                      {gestionar && a.abierta && <Boton tam="sm" icono={<CheckCheck className="size-3.5" />} onClick={() => setCierre({ alerta: a, estado: "RESUELTA", observacion: "" })}>Resolver</Boton>}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
          {lista.datos && <Paginacion pagina={pagina} tam={30} total={lista.datos.total} onCambio={setPagina} />}
        </>
      ) : (
        <Tarjeta titulo="Reglas: cuándo se genera cada alerta" accion={<Settings2 className="size-4 text-slate-400" />}>
          {!reglas.datos ? (
            <Cargando />
          ) : (
            <div className="space-y-2">
              <Aviso><Info className="mr-1 inline size-4" />Stock bajo y crítico usan el mínimo y el nivel crítico definidos en cada producto. Los canales de notificación (correo, Teams, Telegram, WhatsApp) quedan preparados; hoy las alertas se muestran dentro del sistema.</Aviso>
              {reglas.datos.map((regla) => (
                <Regla key={regla.id} regla={regla} editable={puede("alertas:configurar")} severidades={op.datos?.severidades ?? []} onGuardar={(cambios) => ejecutar(async () => { await api.put(`/reglas-alertas/${regla.id}`, cambios); reglas.recargar(); }, "Regla actualizada")} />
              ))}
            </div>
          )}
        </Tarjeta>
      )}

      <Modal abierto={!!cierre} titulo="Cerrar alerta" onCerrar={() => setCierre(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} disabled={!cierre?.observacion.trim()} onClick={async () => { await cambiar(cierre!.alerta, cierre!.estado, cierre!.observacion); setCierre(null); }}>Confirmar</Boton>}>
        {cierre && (
          <div className="grid gap-3">
            <p className="text-sm font-medium text-slate-800">{cierre.alerta.titulo}</p>
            <Campo etiqueta="Resultado"><Selector value={cierre.estado} onChange={(e) => setCierre({ ...cierre, estado: e.target.value })} opciones={[{ valor: "RESUELTA", texto: "Resuelta" }, { valor: "DESCARTADA", texto: "Descartada" }]} /></Campo>
            <Campo etiqueta="Observación" requerido><textarea className="campo" rows={3} value={cierre.observacion} onChange={(e) => setCierre({ ...cierre, observacion: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
    </>
  );
}

const UNIDAD_PARAMETRO: Record<string, string> = { dias: "días", horas: "horas", porcentaje: "%" };

function Regla({ regla, editable, severidades, onGuardar }: { regla: any; editable: boolean; severidades: string[]; onGuardar: (c: Record<string, any>) => void }) {
  const [params, setParams] = useState<Record<string, any>>(regla.parametros ?? {});
  const cambiado = JSON.stringify(params) !== JSON.stringify(regla.parametros ?? {});
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 p-3">
      <Interruptor valor={regla.activa} deshabilitado={!editable} onCambio={(v) => onGuardar({ activa: v })} />
      <div className="min-w-48 flex-1">
        <p className="text-sm font-medium text-slate-900">{regla.nombre}</p>
        <p className="text-xs text-slate-500">{etiqueta(regla.tipo)}</p>
      </div>
      {Object.keys(params).map((k) => (
        <label key={k} className="flex items-center gap-1.5 text-sm text-slate-700">
          <Entrada type="number" min={0} disabled={!editable} className="!h-9 !w-20" value={params[k]} onChange={(e) => setParams({ ...params, [k]: Number(e.target.value) })} />
          {UNIDAD_PARAMETRO[k] ?? k}
        </label>
      ))}
      <Selector aria-label="Severidad" disabled={!editable} className="!h-9 !w-36" value={regla.severidad} onChange={(e) => onGuardar({ severidad: e.target.value })} opciones={severidades.map((s) => ({ valor: s, texto: etiqueta(s) }))} />
      {cambiado && <Boton tam="sm" onClick={() => onGuardar({ parametros: params })}>Guardar</Boton>}
    </div>
  );
}
