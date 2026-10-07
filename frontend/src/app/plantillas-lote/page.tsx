"use client";

// Creador de lotes: constructor visual por bloques con vista previa, validacion de colisiones y versionado.

import { ArrowDown, ArrowUp, Copy, Plus, Power, PowerOff, RotateCcw, Save, Trash2, Zap } from "lucide-react";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, Cargando, cx, Encabezado, Entrada, Estado, Insignia, Selector, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { etiqueta, fecha } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

type Segmento = { k: number; tipo: string; configuracion: Record<string, any> };
let sig = 1;
const NOMBRES: Record<string, string> = {
  TEXTO: "Texto fijo", SEPARADOR: "Separador", ANIO: "Año", MES: "Mes", DIA: "Día", FECHA: "Fecha", FECHA_HORA: "Fecha/hora", CORRELATIVO: "Correlativo",
  MANUAL: "Campo manual", PRODUCTO: "Código producto", FAMILIA: "Código familia", SUBFAMILIA: "Código subfamilia", BODEGA: "Código bodega",
  EMPRESA: "Código empresa", TEMPORADA: "Código temporada", USUARIO: "Usuario", TURNO: "Turno", PROCESO: "Proceso",
};
const POR_DEFECTO: Record<string, Record<string, any>> = {
  TEXTO: { valor: "LOTE" }, SEPARADOR: { valor: "-" }, ANIO: { digitos: 2 }, MES: { formato: "NUMERO" }, FECHA: { formato: "YYYYMMDD" },
  FECHA_HORA: { formato: "YYYYMMDDHHMM" }, CORRELATIVO: { largo: 5, inicio: 1 }, MANUAL: { etiqueta: "Origen", clave: "origen", obligatorio: true },
};
const GRUPOS: [string, string[]][] = [
  ["Literales", ["TEXTO", "SEPARADOR"]],
  ["Fecha", ["ANIO", "MES", "DIA", "FECHA", "FECHA_HORA"]],
  ["Numeración", ["CORRELATIVO"]],
  ["Contexto", ["SUBFAMILIA", "FAMILIA", "PRODUCTO", "BODEGA", "EMPRESA", "TEMPORADA", "PROCESO", "USUARIO", "TURNO"]],
  ["Entrada", ["MANUAL"]],
];
const COLOR: Record<string, string> = { Literales: "bg-slate-100 text-slate-800 border-slate-300", Fecha: "bg-sky-100 text-sky-900 border-sky-300", Numeración: "bg-emerald-100 text-emerald-900 border-emerald-300", Contexto: "bg-violet-100 text-violet-900 border-violet-300", Entrada: "bg-amber-100 text-amber-900 border-amber-300" };
const grupoDe = (tipo: string) => GRUPOS.find(([, t]) => t.includes(tipo))?.[0] ?? "Literales";
const aSegmentos = (lista: any[] | undefined): Segmento[] => (lista ?? []).map((s) => ({ k: sig++, tipo: s.tipo, configuracion: { ...s.configuracion } }));

export default function PlantillasLote() {
  const { puede } = useSesion();
  const editable = puede("lotes:administrar");
  const { datos: plantillas, recargar } = useDatos<any[]>("/plantillas-lotes");
  const op = useDatos("/plantillas-lotes/opciones");
  const [id, setId] = useState<number | "nueva" | null>(null);
  const [cab, setCab] = useState<Record<string, any>>({});
  const [segmentos, setSegmentos] = useState<Segmento[]>([]);
  const [alcance, setAlcance] = useState<string[]>([]);
  const [reinicio, setReinicio] = useState("NUNCA");
  const [sel, setSel] = useState<number | null>(null);
  const [previa, setPrevia] = useState<any>(null);
  const { ejecutar, ocupado } = useAccion();
  const actual = typeof id === "number" ? plantillas?.find((p) => p.id === id) : null;

  const abrir = (p: any | null) => {
    const v = p ? (p.borrador ?? p.vigente) : null;
    setId(p ? p.id : "nueva");
    setCab(p ? { codigo: p.codigo, nombre: p.nombre, descripcion: p.descripcion ?? "", modo: p.modo, momento_creacion: p.momento_creacion } : { codigo: "", nombre: "", descripcion: "", modo: "AUTOMATICO", momento_creacion: "AL_CONFIRMAR_RECEPCION" });
    setSegmentos(aSegmentos(v?.segmentos ?? (p ? [] : [{ tipo: "SUBFAMILIA", configuracion: {} }, { tipo: "SEPARADOR", configuracion: { valor: "-" } }, { tipo: "ANIO", configuracion: { digitos: 2 } }, { tipo: "SEPARADOR", configuracion: { valor: "-" } }, { tipo: "CORRELATIVO", configuracion: { largo: 5 } }])));
    setAlcance(v?.alcance ?? (p ? [] : ["SUBFAMILIA"]));
    setReinicio(v?.reinicio ?? (p ? "NUNCA" : "ANUAL"));
    setSel(null);
  };
  useEffect(() => {
    if (plantillas && id === null && plantillas[0]) abrir(plantillas[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plantillas]);

  // Vista previa y validacion en vivo, con el mismo motor que genera los lotes reales.
  const firma = JSON.stringify([segmentos.map((s) => [s.tipo, s.configuracion]), alcance, reinicio, cab.modo]);
  useEffect(() => {
    if (id === null) return;
    const t = setTimeout(() => {
      api.post("/plantillas-lotes/vista-previa", { modo: cab.modo ?? "AUTOMATICO", segmentos: segmentos.map(({ tipo, configuracion }) => ({ tipo, configuracion })), alcance, reinicio }).then(setPrevia).catch(() => setPrevia(null));
    }, 250);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [firma, id]);

  const mover = (i: number, d: number) => setSegmentos((s) => { const n = [...s]; const j = i + d; if (j < 0 || j >= n.length) return s; [n[i], n[j]] = [n[j], n[i]]; return n; });
  const cfg = (k: number, cambios: Record<string, any>) => setSegmentos((s) => s.map((x) => (x.k === k ? { ...x, configuracion: { ...x.configuracion, ...cambios } } : x)));
  const seg = segmentos.find((s) => s.k === sel);

  const guardar = (activar: boolean) =>
    ejecutar(async () => {
      const cuerpo = { ...cab, segmentos: segmentos.map(({ tipo, configuracion }) => ({ tipo, configuracion })), alcance, reinicio };
      let p = id === "nueva" ? await api.post("/plantillas-lotes", cuerpo) : await api.put(`/plantillas-lotes/${id}`, cuerpo);
      if (activar) p = await api.post(`/plantillas-lotes/${p.id}/activar`);
      recargar();
      setId(p.id);
    }, activar ? "Plantilla activada: nueva versión vigente" : "Borrador guardado");

  if (!plantillas || !op.datos) return <Cargando />;
  const errores: string[] = previa?.errores ?? [];

  return (
    <>
      <Encabezado titulo="Creador de lotes" descripcion="Defina cómo se construye el lote interno. Las plantillas se asocian a familias, subfamilias o productos.">
        {editable && <Boton icono={<Plus className="size-4" />} onClick={() => abrir(null)}>Nueva plantilla</Boton>}
      </Encabezado>
      <div className="grid gap-3 lg:grid-cols-[280px_1fr]">
        <Tarjeta titulo="Plantillas" sinRelleno className="self-start">
          <ul>
            {plantillas.length === 0 && <li className="p-4 text-sm text-slate-500">Aún no hay plantillas.</li>}
            {plantillas.map((p) => (
              <li key={p.id}>
                <button onClick={() => abrir(p)} className={cx("block w-full border-b border-slate-100 px-4 py-3 text-left transition hover:bg-slate-50", id === p.id && "bg-marca-50")}>
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-slate-900">{p.nombre}</span>
                    <Insignia tono={p.activa ? "verde" : "gris"}>{p.activa ? "Activa" : "Inactiva"}</Insignia>
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-500">
                    {p.codigo} · {etiqueta(p.modo)} · v{p.version_vigente ?? "—"}
                    {p.borrador && " · borrador pendiente"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </Tarjeta>

        {id !== null && (
          <div className="space-y-3">
            <Tarjeta titulo={id === "nueva" ? "Nueva plantilla" : `Plantilla ${actual?.codigo ?? ""}`}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Campo etiqueta="Código" requerido><Entrada value={cab.codigo ?? ""} disabled={id !== "nueva"} onChange={(e) => setCab({ ...cab, codigo: e.target.value.toUpperCase() })} /></Campo>
                <Campo etiqueta="Nombre" requerido><Entrada value={cab.nombre ?? ""} onChange={(e) => setCab({ ...cab, nombre: e.target.value })} /></Campo>
                <Campo etiqueta="Modo de creación"><Selector value={cab.modo} onChange={(e) => setCab({ ...cab, modo: e.target.value })} opciones={op.datos.modos.map((m: string) => ({ valor: m, texto: etiqueta(m) }))} /></Campo>
                <Campo etiqueta="Momento de creación"><Selector value={cab.momento_creacion} onChange={(e) => setCab({ ...cab, momento_creacion: e.target.value })} opciones={op.datos.momentos.map((m: string) => ({ valor: m, texto: etiqueta(m) }))} /></Campo>
              </div>
            </Tarjeta>

            <Tarjeta titulo="Formato del lote">
              <div className="rounded-xl bg-slate-900 p-4 text-center">
                <p className="text-[11px] font-semibold tracking-widest text-slate-400 uppercase">Vista previa</p>
                <p className="cifra mt-1 text-3xl font-semibold tracking-wide break-all text-white">{previa?.vista_previa || "—"}</p>
                {previa?.ejemplos?.length > 1 && <p className="mt-2 text-xs break-all text-slate-400">Siguientes: {previa.ejemplos.slice(1, 5).join(" · ")}</p>}
              </div>

              <div className="mt-4 flex min-h-14 flex-wrap items-center gap-1.5 rounded-xl border-2 border-dashed border-slate-200 p-2">
                {segmentos.length === 0 && <span className="px-2 text-sm text-slate-400">Agregue bloques desde la paleta inferior.</span>}
                {segmentos.map((s, i) => (
                  <span key={s.k} className={cx("group inline-flex items-center gap-1 rounded-lg border px-2 py-1.5 text-sm font-medium", COLOR[grupoDe(s.tipo)], sel === s.k && "ring-2 ring-marca-500")}>
                    <button onClick={() => setSel(s.k)} className="max-w-40 truncate" title="Configurar">
                      {s.tipo === "TEXTO" || s.tipo === "SEPARADOR" ? `“${s.configuracion.valor ?? ""}”` : NOMBRES[s.tipo]}
                      {s.tipo === "CORRELATIVO" && ` ${s.configuracion.largo ?? 4}`}
                      {s.tipo === "ANIO" && ` ${s.configuracion.digitos ?? 4} díg.`}
                    </button>
                    {editable && (
                      <span className="flex items-center opacity-60 group-hover:opacity-100">
                        <button aria-label="Mover a la izquierda" disabled={i === 0} onClick={() => mover(i, -1)} className="disabled:opacity-30"><ArrowUp className="size-3.5 -rotate-90" /></button>
                        <button aria-label="Mover a la derecha" disabled={i === segmentos.length - 1} onClick={() => mover(i, 1)} className="disabled:opacity-30"><ArrowDown className="size-3.5 -rotate-90" /></button>
                        <button aria-label="Duplicar" onClick={() => setSegmentos((x) => [...x.slice(0, i + 1), { k: sig++, tipo: s.tipo, configuracion: { ...s.configuracion } }, ...x.slice(i + 1)])}><Copy className="size-3.5" /></button>
                        <button aria-label="Eliminar" onClick={() => setSegmentos((x) => x.filter((y) => y.k !== s.k))}><Trash2 className="size-3.5 text-rose-600" /></button>
                      </span>
                    )}
                  </span>
                ))}
              </div>

              {editable && (
                <div className="mt-3 space-y-1.5">
                  {GRUPOS.map(([grupo, tipos]) => (
                    <div key={grupo} className="flex flex-wrap items-center gap-1.5">
                      <span className="w-20 text-[11px] font-semibold text-slate-500 uppercase">{grupo}</span>
                      {tipos.map((t) => (
                        <button key={t} onClick={() => { const k = sig++; setSegmentos((s) => [...s, { k, tipo: t, configuracion: { ...(POR_DEFECTO[t] ?? {}) } }]); setSel(k); }} className={cx("rounded-md border px-2 py-1 text-xs font-medium transition hover:brightness-95", COLOR[grupo])}>
                          + {NOMBRES[t]}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {seg && (
                <div className="mt-4 grid gap-3 rounded-xl bg-slate-50 p-3 sm:grid-cols-3">
                  <p className="text-sm font-semibold text-slate-800 sm:col-span-3">Configurar: {NOMBRES[seg.tipo]}</p>
                  {(seg.tipo === "TEXTO" || seg.tipo === "SEPARADOR") && <Campo etiqueta="Valor"><Entrada value={seg.configuracion.valor ?? ""} onChange={(e) => cfg(seg.k, { valor: e.target.value })} /></Campo>}
                  {seg.tipo === "ANIO" && <Campo etiqueta="Dígitos"><Selector value={seg.configuracion.digitos ?? 4} onChange={(e) => cfg(seg.k, { digitos: Number(e.target.value) })} opciones={[{ valor: 4, texto: "4 (2026)" }, { valor: 2, texto: "2 (26)" }]} /></Campo>}
                  {seg.tipo === "MES" && <Campo etiqueta="Formato"><Selector value={seg.configuracion.formato ?? "NUMERO"} onChange={(e) => cfg(seg.k, { formato: e.target.value })} opciones={[{ valor: "NUMERO", texto: "10" }, { valor: "ABREV", texto: "OCT" }, { valor: "NOMBRE", texto: "OCTUBRE" }]} /></Campo>}
                  {seg.tipo === "FECHA" && <Campo etiqueta="Formato"><Selector value={seg.configuracion.formato ?? "YYYYMMDD"} onChange={(e) => cfg(seg.k, { formato: e.target.value })} opciones={op.datos.formatos_fecha.map((f: string) => ({ valor: f, texto: f }))} /></Campo>}
                  {seg.tipo === "FECHA_HORA" && <Campo etiqueta="Formato"><Selector value={seg.configuracion.formato ?? "YYYYMMDDHHMM"} onChange={(e) => cfg(seg.k, { formato: e.target.value })} opciones={op.datos.formatos_fecha_hora.map((f: string) => ({ valor: f, texto: f }))} /></Campo>}
                  {seg.tipo === "CORRELATIVO" && (
                    <>
                      <Campo etiqueta="Largo (dígitos)"><Entrada type="number" min={1} max={10} value={seg.configuracion.largo ?? 4} onChange={(e) => cfg(seg.k, { largo: Number(e.target.value) })} /></Campo>
                      <Campo etiqueta="Valor inicial"><Entrada type="number" min={0} value={seg.configuracion.inicio ?? 1} onChange={(e) => cfg(seg.k, { inicio: Number(e.target.value) })} /></Campo>
                    </>
                  )}
                  {op.datos.dimensiones_alcance.concat(["USUARIO", "TURNO"]).includes(seg.tipo) && <Campo etiqueta="Largo máximo (opcional)"><Entrada type="number" min={1} value={seg.configuracion.largo ?? ""} onChange={(e) => cfg(seg.k, { largo: e.target.value ? Number(e.target.value) : undefined })} /></Campo>}
                  {seg.tipo === "MANUAL" && (
                    <>
                      <Campo etiqueta="Etiqueta"><Entrada value={seg.configuracion.etiqueta ?? ""} onChange={(e) => cfg(seg.k, { etiqueta: e.target.value, clave: e.target.value.toLowerCase().replace(/\W+/g, "_") })} /></Campo>
                      <Campo etiqueta="Validación (expresión regular)" ayuda="Ej.: [A-Z]{2}[0-9]{3}"><Entrada value={seg.configuracion.patron ?? ""} onChange={(e) => cfg(seg.k, { patron: e.target.value || undefined })} /></Campo>
                    </>
                  )}
                </div>
              )}
            </Tarjeta>

            <Tarjeta titulo="Correlativo: alcance y reinicio">
              <div className="grid gap-4 sm:grid-cols-[1fr_220px]">
                <div>
                  <p className="mb-1.5 text-xs font-medium text-slate-700">Numeración separada por (combinable)</p>
                  <div className="flex flex-wrap gap-1.5">
                    {op.datos.dimensiones_alcance.map((d: string) => {
                      const activo = alcance.includes(d);
                      return (
                        <button key={d} disabled={!editable} onClick={() => setAlcance(activo ? alcance.filter((x) => x !== d) : [...alcance, d])} className={cx("rounded-lg border px-3 py-1.5 text-sm font-medium transition", activo ? "border-marca-600 bg-marca-600 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>
                          {etiqueta(d)}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">{alcance.length ? `Cada ${alcance.map((a) => a.toLowerCase()).join(" + ")} lleva su propia numeración.` : "Numeración global: única para toda la plantilla."}</p>
                </div>
                <Campo etiqueta="Reinicio del correlativo">
                  <Selector disabled={!editable} value={reinicio} onChange={(e) => setReinicio(e.target.value)} opciones={op.datos.reinicios.map((r: string) => ({ valor: r, texto: etiqueta(r) }))} />
                </Campo>
              </div>
              <div className="mt-4 space-y-2">
                {errores.map((e) => <Aviso key={e} tipo="error" titulo="No puede activarse">{e}</Aviso>)}
                {(previa?.advertencias ?? []).map((e: string) => <Aviso key={e} tipo="alerta">{e}</Aviso>)}
                {previa && !errores.length && <Aviso tipo="exito">Validación correcta: no se detectan colisiones al simular productos, bodegas y cambios de período.</Aviso>}
              </div>
            </Tarjeta>

            {editable && (
              <div className="flex flex-wrap items-center justify-end gap-2">
                {actual?.activa && <Boton variante="fantasma" icono={<PowerOff className="size-4" />} onClick={() => ejecutar(async () => { await api.post(`/plantillas-lotes/${actual.id}/desactivar`); recargar(); }, "Plantilla desactivada")}>Desactivar</Boton>}
                {actual && !actual.activa && actual.version_vigente && <Boton variante="fantasma" icono={<Power className="size-4" />} onClick={() => ejecutar(async () => { await api.post(`/plantillas-lotes/${actual.id}/activar`); recargar(); }, "Plantilla activada")}>Reactivar</Boton>}
                {actual?.vigente?.reinicio === "MANUAL" && <Boton variante="fantasma" icono={<RotateCcw className="size-4" />} onClick={() => confirm("¿Reiniciar el correlativo ahora?") && ejecutar(() => api.post(`/plantillas-lotes/${actual.id}/reiniciar-correlativo`), "Correlativo reiniciado")}>Reiniciar correlativo</Boton>}
                <Boton variante="secundario" icono={<Save className="size-4" />} cargando={ocupado} onClick={() => guardar(false)}>Guardar borrador</Boton>
                <Boton icono={<Zap className="size-4" />} cargando={ocupado} disabled={errores.length > 0 || !cab.codigo || !cab.nombre} onClick={() => guardar(true)}>Guardar y activar</Boton>
              </div>
            )}

            {actual && (
              <Tarjeta titulo="Versiones y asociaciones">
                <ul className="space-y-1.5 text-sm">
                  {[...actual.versiones].reverse().map((v: any) => (
                    <li key={v.id} className="flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2">
                      <b>v{v.version}</b> <Estado valor={v.estado} />
                      <span className="text-slate-600">{v.vigente_desde ? `desde ${fecha(v.vigente_desde)}` : "sin publicar"}{v.vigente_hasta ? ` hasta ${fecha(v.vigente_hasta)}` : ""}</span>
                      <span className="ml-auto text-xs text-slate-500">{v.segmentos.length} segmentos · reinicio {v.reinicio.toLowerCase()}</span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-sm text-slate-600">
                  Asociada a: {[...actual.asignada_a.familias.map((x: string) => `familia ${x}`), ...actual.asignada_a.subfamilias.map((x: string) => `subfamilia ${x}`), ...actual.asignada_a.productos.map((x: string) => `producto ${x}`)].join(", ") || "ninguna familia, subfamilia ni producto (asóciela desde Familias o Productos)"}.
                </p>
                <p className="mt-1 text-xs text-slate-500">Cambiar la plantilla no modifica los lotes ya creados: cada lote conserva la versión con que se generó.</p>
              </Tarjeta>
            )}
          </div>
        )}
      </div>
    </>
  );
}
