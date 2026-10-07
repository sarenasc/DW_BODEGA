"use client";

// Consumo rapido: 1) proceso fijado  2) escanear  3) ficha  4) cantidad  5) registrar  6) listo para el siguiente.

import { AlertTriangle, ArrowLeft, Check, CheckCircle2, Delete, Factory, History, ListFilter, Undo2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { EntradaCodigo, pitido, vibrar } from "@/components/Escaner";
import { SelectorExistencia, SelectorProceso } from "@/components/Selectores";
import { Aviso, Boton, Cargando, cx, Estado, Insignia, Modal, Selector, useAviso } from "@/components/ui";
import { api, claveIdempotencia, ErrorApi } from "@/lib/api";
import { clp, fecha, hora, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

const TECLAS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ",", "0", "⌫"];

export default function ConsumoRapido() {
  const { puede } = useSesion();
  const avisar = useAviso();
  const cat = useDatos("/catalogos");
  const [proceso, setProceso] = useState<any>(null);
  const [motivo, setMotivo] = useState("PROCESO");
  const [eligiendo, setEligiendo] = useState(false);
  const [ficha, setFicha] = useState<any>(null);
  const [cantidad, setCantidad] = useState("");
  const [fifoAceptado, setFifoAceptado] = useState(false);
  const [justificacion, setJustificacion] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<any>(null);
  const [lista, setLista] = useState(false);
  const clave = useRef("");
  const recientes = useDatos(puede("movimientos:crear") ? "/consumos/recientes" : null, { proceso_id: proceso?.id, limite: 12 });
  const motivos = (cat.datos?.motivos ?? []).filter((m: any) => m.clase === "SALIDA");
  const requiereProceso = motivos.find((m: any) => m.codigo === motivo)?.requiere_proceso ?? true;

  // El proceso elegido se recuerda en el dispositivo para no pedirlo en cada escaneo.
  useEffect(() => {
    const guardado = localStorage.getItem("wms.proceso");
    if (guardado) api.get(`/procesos/${guardado}`).then((p) => p.estado === "ABIERTO" && setProceso(p)).catch(() => localStorage.removeItem("wms.proceso"));
  }, []);
  const fijarProceso = (p: any) => {
    setProceso(p);
    setEligiendo(false);
    if (p) localStorage.setItem("wms.proceso", String(p.id));
    else localStorage.removeItem("wms.proceso");
  };

  const limpiar = useCallback(() => {
    setFicha(null);
    setCantidad("");
    setFifoAceptado(false);
    setJustificacion("");
    setError(null);
  }, []);

  const buscar = useCallback(
    async (codigo: string) => {
      setError(null);
      setHecho(null);
      try {
        const f = await api.get("/consumo/escanear", { codigo, proceso_id: proceso?.id });
        clave.current = claveIdempotencia(); // una clave por ficha: un doble toque o un reintento no duplica el consumo
        setFicha(f);
        setCantidad("");
        setFifoAceptado(false);
        setJustificacion("");
        vibrar(40);
        pitido(true);
      } catch (e: any) {
        setError(e.message);
        vibrar([80, 60, 80]);
        pitido(false);
      }
    },
    [proceso?.id],
  );

  const tecla = (t: string) => {
    if (t === "⌫") return setCantidad((c) => c.slice(0, -1));
    if (t === "," && cantidad.includes(",")) return;
    setCantidad((c) => (c.length >= 9 ? c : (c === "0" && t !== "," ? "" : c) + t));
  };
  const valor = Number(cantidad.replace(",", "."));
  const fifo = ficha?.fifo;
  const politica = fifo?.politica;
  const fifoBloquea = fifo && (politica === "BLOQUEAR" || (politica === "PERMISO" && !ficha.puede_omitir_fifo));
  const fifoListo = !fifo || (!fifoBloquea && (politica === "JUSTIFICAR" ? justificacion.trim().length > 3 : fifoAceptado));
  const puedeRegistrar = !!ficha && !ficha.bloqueo && valor > 0 && fifoListo && (!requiereProceso || !!proceso);

  async function registrar() {
    if (!puedeRegistrar || ocupado) return;
    setOcupado(true);
    setError(null);
    try {
      const r = await api.post("/consumos", {
        proceso_id: requiereProceso ? proceso.id : (proceso?.id ?? null),
        existencia_id: ficha.id,
        cantidad: valor,
        unidad_id: ficha.unidad_id,
        confirmar_fifo: !!fifo,
        justificacion: justificacion || null,
        motivo_codigo: motivo,
        clave_idempotencia: clave.current,
      });
      vibrar([40, 40, 120]);
      pitido(true);
      setHecho({ producto: ficha.producto, cantidad: valor, unidad: ficha.unidad, restante: r.existencia.cantidad_fisica, duplicado: r.duplicado });
      limpiar();
      recientes.recargar();
      setTimeout(() => setHecho(null), 2600);
    } catch (e: any) {
      const err = e as ErrorApi;
      setError(err.message);
      vibrar([80, 60, 80]);
      pitido(false);
      if (err.codigo === "STOCK_INSUFICIENTE" || err.codigo === "STOCK_RESERVADO") buscar(ficha.codigo_publico);
    } finally {
      setOcupado(false);
    }
  }

  async function anular(m: any) {
    const texto = prompt(`Anular el consumo de ${num(-m.cantidad)} ${m.unidad} de ${m.producto}.\nMotivo de la anulación:`);
    if (!texto?.trim()) return;
    try {
      await api.post(`/movimientos/${m.id}/anular`, { motivo: texto });
      avisar("exito", "Consumo anulado: se generó el movimiento inverso.");
      recientes.recargar();
    } catch (e: any) {
      avisar("error", e.message);
    }
  }

  if (!cat.datos) return <Cargando />;

  return (
    <div className="mx-auto max-w-lg">
      {/* 1. Proceso fijado */}
      <button onClick={() => setEligiendo(true)} className={cx("mb-3 flex w-full items-center gap-3 rounded-2xl border-2 p-3 text-left transition", proceso ? "border-marca-500 bg-marca-50" : "border-dashed border-amber-400 bg-amber-50")}>
        <span className={cx("flex size-11 shrink-0 items-center justify-center rounded-xl text-white", proceso ? "bg-marca-600" : "bg-amber-500")}>
          <Factory className="size-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-semibold tracking-wide text-slate-500 uppercase">{motivo === "PROCESO" ? "Proceso" : `Rebaja: ${motivos.find((m: any) => m.codigo === motivo)?.nombre ?? motivo}`}</span>
          <span className="block truncate text-base font-semibold text-slate-900">{proceso ? proceso.codigo : requiereProceso ? "Seleccione un proceso" : "Sin proceso"}</span>
          {proceso && <span className="block truncate text-xs text-slate-600">{[proceso.especie, proceso.variedad, proceso.productor].filter(Boolean).join(" · ")}</span>}
        </span>
        <span className="text-sm font-medium text-marca-700">Cambiar</span>
      </button>

      {hecho && (
        <div className="aparecer mb-3 flex items-center gap-3 rounded-2xl bg-emerald-600 p-4 text-white shadow-lg" role="status">
          <CheckCircle2 className="size-9 shrink-0" />
          <div>
            <p className="text-lg leading-tight font-semibold">
              {hecho.duplicado ? "Ya estaba registrado" : "Registrado"}: {num(hecho.cantidad)} {hecho.unidad}
            </p>
            <p className="text-sm text-emerald-50">
              {hecho.producto} · quedan {num(hecho.restante)} {hecho.unidad}
            </p>
          </div>
        </div>
      )}
      {error && (
        <Aviso tipo="error" className="mb-3">
          {error}
        </Aviso>
      )}

      {!ficha ? (
        /* 2. Escanear */
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h1 className="mb-3 text-lg font-semibold text-slate-900">Escanee el QR de la existencia</h1>
          <EntradaCodigo onCodigo={buscar} activa={!eligiendo && !lista} />
          <Boton variante="fantasma" className="mt-2 w-full" icono={<ListFilter className="size-4" />} onClick={() => setLista(true)}>
            Elegir de la lista de existencias
          </Boton>
        </div>
      ) : (
        /* 3 a 5. Ficha, cantidad y registro */
        <div className="aparecer rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 p-4">
            <button onClick={limpiar} className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-slate-500">
              <ArrowLeft className="size-4" /> Escanear otro
            </button>
            <h1 className="text-xl leading-tight font-semibold text-slate-900">{ficha.producto}</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {ficha.codigo_publico} · {ficha.ubicacion ?? ficha.bodega}
            </p>
            <dl className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-slate-50 p-2">
                <dt className="text-[10px] font-semibold text-slate-500 uppercase">Lote</dt>
                <dd className="truncate text-sm font-semibold">{ficha.lote ?? "—"}</dd>
              </div>
              <div className="rounded-xl bg-slate-50 p-2">
                <dt className="text-[10px] font-semibold text-slate-500 uppercase">Ingreso</dt>
                <dd className="text-sm font-semibold">{fecha(ficha.fecha_ingreso)}</dd>
              </div>
              <div className="rounded-xl bg-marca-50 p-2">
                <dt className="text-[10px] font-semibold text-marca-700 uppercase">Disponible</dt>
                <dd className="cifra text-sm font-bold text-marca-700">
                  {num(ficha.disponible_para_proceso)} {ficha.unidad}
                </dd>
              </div>
            </dl>
            {ficha.disponible_para_proceso < ficha.cantidad_fisica && (
              <p className="mt-2 text-xs text-amber-700">
                Stock físico {num(ficha.cantidad_fisica)} {ficha.unidad}; el resto está reservado.
              </p>
            )}
            {ficha.fecha_vencimiento && <p className="mt-1 text-xs text-slate-500">Vence el {fecha(ficha.fecha_vencimiento)}</p>}
            {ficha.avisos?.map((a: string) => (
              <Aviso key={a} tipo="alerta" className="mt-2">
                {a}
              </Aviso>
            ))}
            {ficha.bloqueo && (
              <Aviso tipo="error" className="mt-2" titulo="No se puede consumir">
                {ficha.bloqueo.mensaje}
              </Aviso>
            )}
          </div>

          {fifo && !ficha.bloqueo && (
            <div className="border-b border-amber-200 bg-amber-50 p-4" role="alert">
              <p className="flex items-start gap-2 text-sm font-semibold text-amber-900">
                <AlertTriangle className="mt-0.5 size-5 shrink-0" /> {fifo.mensaje}
              </p>
              <div className="mt-2 rounded-xl bg-white p-3 text-sm shadow-sm">
                <p className="text-[11px] font-semibold text-slate-500 uppercase">Recomendada ({fifo.estrategia.replace("_", " + ")})</p>
                <p className="font-semibold text-slate-900">
                  {fifo.producto} · Lote {fifo.lote ?? "—"}
                </p>
                <p className="text-slate-600">
                  Ingreso {fecha(fifo.fecha_ingreso)}
                  {fifo.fecha_vencimiento && ` · vence ${fecha(fifo.fecha_vencimiento)}`} · {num(fifo.cantidad_disponible)} {fifo.unidad}
                </p>
                <p className="text-slate-600">
                  {fifo.bodega} · <b>{fifo.ubicacion ?? "sin ubicación"}</b> · {fifo.codigo_publico}
                </p>
              </div>
              <div className="mt-3 grid gap-2">
                <Boton tam="lg" variante="oscuro" onClick={() => buscar(fifo.codigo_publico)}>
                  Usar la recomendada
                </Boton>
                {fifoBloquea ? (
                  <p className="text-center text-sm font-medium text-rose-700">{politica === "BLOQUEAR" ? "La política no permite consumir esta existencia." : "Consumir fuera de orden requiere un permiso especial."}</p>
                ) : politica === "JUSTIFICAR" ? (
                  <textarea className="campo" rows={2} placeholder="Justificación para continuar con esta existencia…" value={justificacion} onChange={(e) => setJustificacion(e.target.value)} />
                ) : (
                  <Boton tam="lg" variante={fifoAceptado ? "primario" : "secundario"} icono={fifoAceptado ? <Check className="size-5" /> : undefined} onClick={() => setFifoAceptado(!fifoAceptado)}>
                    {fifoAceptado ? "Continuaré con esta existencia" : "Continuar con esta de todos modos"}
                  </Boton>
                )}
              </div>
            </div>
          )}

          {!ficha.bloqueo && (
            <div className="p-4">
              <p className="text-center text-[11px] font-semibold tracking-wide text-slate-500 uppercase">Cantidad utilizada</p>
              <p className="cifra my-1 text-center text-5xl font-semibold tracking-tight text-slate-900" aria-live="polite">
                {cantidad || "0"} <span className="text-2xl font-medium text-slate-400">{ficha.unidad}</span>
              </p>
              {valor > ficha.disponible_para_proceso && <p className="text-center text-sm font-medium text-rose-600">Supera el disponible.</p>}
              <div className="mt-3 grid grid-cols-3 gap-2">
                {TECLAS.map((t) => (
                  <button key={t} type="button" onClick={() => tecla(t)} aria-label={t === "⌫" ? "Borrar" : t} className="flex h-16 items-center justify-center rounded-2xl bg-slate-100 text-2xl font-semibold text-slate-900 transition active:scale-95 active:bg-slate-200">
                    {t === "⌫" ? <Delete className="size-6" /> : t}
                  </button>
                ))}
              </div>
              <div className="mt-2 grid grid-cols-[auto_1fr] gap-2">
                <Boton tam="xl" variante="secundario" onClick={() => setCantidad(String(ficha.disponible_para_proceso).replace(".", ","))}>
                  Todo
                </Boton>
                <Boton tam="xl" onClick={registrar} cargando={ocupado} disabled={!puedeRegistrar}>
                  REGISTRAR
                </Boton>
              </div>
              {requiereProceso && !proceso && <p className="mt-2 text-center text-sm text-amber-700">Seleccione un proceso para registrar.</p>}
            </div>
          )}
        </div>
      )}

      {/* Ultimos consumos */}
      <section className="mt-4">
        <h2 className="mb-2 flex items-center gap-2 px-1 text-sm font-semibold text-slate-700">
          <History className="size-4" /> Últimos consumos
        </h2>
        <ul className="space-y-1.5">
          {(recientes.datos ?? []).length === 0 && <li className="rounded-xl bg-white p-4 text-center text-sm text-slate-500">Aún no registra consumos{proceso ? " en este proceso" : ""}.</li>}
          {(recientes.datos ?? []).map((m: any) => (
            <li key={m.id} className={cx("flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-3", m.anulado && "opacity-60")}>
              <span className="cifra w-14 shrink-0 text-sm font-medium text-slate-500">{new Date(m.fecha).toDateString() === new Date().toDateString() ? hora(m.fecha) : fecha(m.fecha).slice(0, 5)}</span>
              <span className="min-w-0 flex-1">
                <span className={cx("block truncate text-sm font-medium text-slate-900", m.anulado && "line-through")}>{m.producto}</span>
                <span className="block truncate text-xs text-slate-500">
                  {m.lote ?? m.codigo_publico} {m.proceso && `· ${m.proceso}`} {m.costo_total != null && `· ${clp(-m.costo_total)}`}
                </span>
              </span>
              <span className="cifra shrink-0 text-base font-semibold text-slate-900">
                {num(-m.cantidad)} {m.unidad}
              </span>
              {m.anulado ? (
                <Insignia tono="rojo">Anulado</Insignia>
              ) : (
                m.puede_anular && (
                  <button onClick={() => anular(m)} aria-label="Anular consumo" title="Anular (genera movimiento inverso)" className="rounded-lg p-2 text-rose-600 hover:bg-rose-50">
                    <Undo2 className="size-5" />
                  </button>
                )
              )}
            </li>
          ))}
        </ul>
      </section>

      <Modal abierto={eligiendo} titulo="Proceso y tipo de rebaja" onCerrar={() => setEligiendo(false)} ancho="max-w-lg">
        <div className="space-y-4">
          <div>
            <p className="mb-1 text-xs font-medium text-slate-700">Tipo de rebaja</p>
            <Selector value={motivo} onChange={(e) => setMotivo(e.target.value)} opciones={motivos.map((m: any) => ({ valor: m.codigo, texto: m.nombre }))} />
          </div>
          <div>
            <p className="mb-1 text-xs font-medium text-slate-700">Proceso abierto {requiereProceso ? "" : "(opcional)"}</p>
            <SelectorProceso valor={proceso} onCambio={fijarProceso} />
            {proceso && <div className="mt-2 flex items-center gap-2 text-xs text-slate-500"><Estado valor={proceso.estado} /> {num(proceso.kilos_base, 0)} kg · {fecha(proceso.fecha)}</div>}
          </div>
          <Boton className="w-full" tam="lg" onClick={() => setEligiendo(false)}>
            Listo
          </Boton>
        </div>
      </Modal>

      <Modal abierto={lista} titulo="Elegir existencia" onCerrar={() => setLista(false)} ancho="max-w-lg">
        <div className="min-h-72">
          <SelectorExistencia valor={null} onCambio={(e) => { if (e) { setLista(false); buscar(e.codigo_publico); } }} />
          <p className="mt-2 text-xs text-slate-500">Las existencias se ordenan por fecha de ingreso: la primera es la más antigua.</p>
        </div>
      </Modal>
    </div>
  );
}
