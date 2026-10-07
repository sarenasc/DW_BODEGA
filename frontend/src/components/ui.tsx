"use client";

// Componentes base de la interfaz (estilo shadcn/ui, escritos a mano para no depender de su generador).

import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Info, Loader2, X, XCircle } from "lucide-react";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";

export function cx(...clases: (string | false | null | undefined)[]) {
  return clases.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- botones

const VARIANTES = {
  primario: "bg-marca-600 text-white hover:bg-marca-700 shadow-sm",
  secundario: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm",
  peligro: "bg-rose-600 text-white hover:bg-rose-700 shadow-sm",
  fantasma: "text-slate-600 hover:bg-slate-100",
  oscuro: "bg-slate-900 text-white hover:bg-slate-800 shadow-sm",
};
const TAMANOS = { sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-14 px-6 text-base", xl: "h-16 px-6 text-lg" };

type PropsBoton = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: keyof typeof VARIANTES;
  tam?: keyof typeof TAMANOS;
  cargando?: boolean;
  icono?: React.ReactNode;
};

export function Boton({ variante = "primario", tam = "md", cargando, icono, className, children, disabled, ...p }: PropsBoton) {
  return (
    <button
      {...p}
      disabled={disabled || cargando}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
        VARIANTES[variante],
        TAMANOS[tam],
        className,
      )}
    >
      {cargando ? <Loader2 className="size-4 animate-spin" /> : icono}
      {children}
    </button>
  );
}

export function EnlaceBoton({ href, variante = "secundario", tam = "md", icono, children, className }: { href: string; variante?: keyof typeof VARIANTES; tam?: keyof typeof TAMANOS; icono?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <Link href={href} className={cx("inline-flex items-center justify-center gap-2 rounded-lg font-medium whitespace-nowrap transition", VARIANTES[variante], TAMANOS[tam], className)}>
      {icono}
      {children}
    </Link>
  );
}

// ---------------------------------------------------------------- estructura

export function Tarjeta({ titulo, accion, children, className, sinRelleno }: { titulo?: React.ReactNode; accion?: React.ReactNode; children: React.ReactNode; className?: string; sinRelleno?: boolean }) {
  return (
    <section className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {(titulo || accion) && (
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <h2 className="text-sm font-semibold text-slate-800">{titulo}</h2>
          {accion}
        </header>
      )}
      <div className={sinRelleno ? "" : "p-4"}>{children}</div>
    </section>
  );
}

export function Encabezado({ titulo, descripcion, volver, children }: { titulo: React.ReactNode; descripcion?: React.ReactNode; volver?: string; children?: React.ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {volver && (
          <Link href={volver} className="mb-1 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800">
            <ChevronLeft className="size-3.5" /> Volver
          </Link>
        )}
        <h1 className="truncate text-xl font-semibold tracking-tight text-slate-900 sm:text-2xl">{titulo}</h1>
        {descripcion && <p className="mt-0.5 text-sm text-slate-500">{descripcion}</p>}
      </div>
      {children && <div className="no-imprimir flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

const TONOS = {
  gris: "bg-slate-100 text-slate-700",
  verde: "bg-emerald-100 text-emerald-800",
  rojo: "bg-rose-100 text-rose-800",
  ambar: "bg-amber-100 text-amber-800",
  azul: "bg-sky-100 text-sky-800",
  violeta: "bg-violet-100 text-violet-800",
};
export type Tono = keyof typeof TONOS;

export function Insignia({ tono = "gris", children }: { tono?: Tono; children: React.ReactNode }) {
  return <span className={cx("inline-flex items-center rounded-md px-2 py-0.5 text-[11px] font-semibold whitespace-nowrap", TONOS[tono])}>{children}</span>;
}

const TONO_ESTADO: Record<string, Tono> = {
  DISPONIBLE: "verde", ABIERTO: "verde", ACTIVA: "verde", ACTIVO: "verde", CONFIRMADO: "verde", VIGENTE: "verde", DEVUELTO: "verde", AUTORIZADO: "verde", RESUELTA: "verde", DEFINITIVO: "verde", OK: "verde",
  BORRADOR: "gris", AGOTADO: "gris", AGOTADA: "gris", LIBERADA: "gris", RETIRADA: "gris", DESCARTADA: "gris", LEIDA: "gris", CERRADO: "azul", CONSUMIDA: "azul", EN_REVISION: "azul", EN_GESTION: "azul", INFORMATIVA: "azul", BAJA: "azul",
  BLOQUEADO: "rojo", BLOQUEADA: "rojo", VENCIDO: "rojo", VENCIDA: "rojo", ANULADO: "rojo", ANULADA: "rojo", ERROR: "rojo", CRITICA: "rojo", ALTA: "rojo",
  CUARENTENA: "ambar", PROVISORIO: "ambar", PARCIAL: "ambar", NUEVA: "ambar", MEDIA: "ambar",
};

export function Estado({ valor }: { valor: string | null | undefined }) {
  if (!valor) return <span className="text-slate-400">—</span>;
  return <Insignia tono={TONO_ESTADO[valor] ?? "gris"}>{valor.replace(/_/g, " ")}</Insignia>;
}

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-sm text-slate-500">
      <Loader2 className="size-4 animate-spin" /> {texto}
    </div>
  );
}

export function Vacio({ titulo, descripcion, children }: { titulo: string; descripcion?: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <p className="text-sm font-medium text-slate-700">{titulo}</p>
      {descripcion && <p className="max-w-md text-sm text-slate-500">{descripcion}</p>}
      {children}
    </div>
  );
}

const AVISOS = {
  info: ["border-sky-200 bg-sky-50 text-sky-900", Info],
  exito: ["border-emerald-200 bg-emerald-50 text-emerald-900", CheckCircle2],
  alerta: ["border-amber-300 bg-amber-50 text-amber-900", AlertTriangle],
  error: ["border-rose-200 bg-rose-50 text-rose-900", XCircle],
} as const;

export function Aviso({ tipo = "info", titulo, children, className }: { tipo?: keyof typeof AVISOS; titulo?: React.ReactNode; children?: React.ReactNode; className?: string }) {
  const [estilo, Icono] = AVISOS[tipo];
  return (
    <div role={tipo === "error" || tipo === "alerta" ? "alert" : "status"} className={cx("flex gap-3 rounded-lg border px-3 py-2.5 text-sm", estilo, className)}>
      <Icono className="mt-0.5 size-4 shrink-0" />
      <div className="min-w-0">
        {titulo && <p className="font-semibold">{titulo}</p>}
        {children && <div className={titulo ? "mt-0.5" : ""}>{children}</div>}
      </div>
    </div>
  );
}

export function Indicador({ titulo, valor, detalle, tono, icono, href }: { titulo: string; valor: React.ReactNode; detalle?: React.ReactNode; tono?: "normal" | "alerta" | "peligro" | "ok"; icono?: React.ReactNode; href?: string }) {
  const color = { normal: "text-slate-900", alerta: "text-amber-600", peligro: "text-rose-600", ok: "text-emerald-600" }[tono ?? "normal"];
  const cuerpo = (
    <div className={cx("h-full rounded-xl border border-slate-200 bg-white p-4 shadow-sm", href && "transition hover:border-marca-500 hover:shadow")}>
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] font-semibold tracking-wide text-slate-500 uppercase">{titulo}</p>
        {icono && <span className="text-slate-400">{icono}</span>}
      </div>
      <p className={cx("cifra mt-1 text-2xl font-semibold tracking-tight", color)}>{valor}</p>
      {detalle && <p className="mt-0.5 text-xs text-slate-500">{detalle}</p>}
    </div>
  );
  return href ? <Link href={href}>{cuerpo}</Link> : cuerpo;
}

// ---------------------------------------------------------------- formularios

export function Campo({ etiqueta, ayuda, error, requerido, children, className }: { etiqueta?: string; ayuda?: React.ReactNode; error?: string | null; requerido?: boolean; children: React.ReactNode; className?: string }) {
  return (
    <label className={cx("block", className)}>
      {etiqueta && (
        <span className="mb-1 block text-xs font-medium text-slate-700">
          {etiqueta}
          {requerido && <span className="text-rose-600"> *</span>}
        </span>
      )}
      {children}
      {error ? <span className="mt-1 block text-xs text-rose-600">{error}</span> : ayuda ? <span className="mt-1 block text-xs text-slate-500">{ayuda}</span> : null}
    </label>
  );
}

export function Entrada(p: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={cx("campo", p.className)} />;
}

export function Selector({ opciones, vacio, ...p }: React.SelectHTMLAttributes<HTMLSelectElement> & { opciones: { valor: string | number; texto: string }[]; vacio?: string }) {
  return (
    <select {...p} className={cx("campo pr-8", p.className)}>
      {vacio !== undefined && <option value="">{vacio}</option>}
      {opciones.map((o) => (
        <option key={o.valor} value={o.valor}>
          {o.texto}
        </option>
      ))}
    </select>
  );
}

export function Interruptor({ valor, onCambio, etiqueta, deshabilitado }: { valor: boolean; onCambio: (v: boolean) => void; etiqueta?: string; deshabilitado?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={valor} disabled={deshabilitado} onClick={() => onCambio(!valor)} className="inline-flex items-center gap-2 text-sm text-slate-700 disabled:opacity-50">
      <span className={cx("relative h-6 w-11 rounded-full transition", valor ? "bg-marca-600" : "bg-slate-300")}>
        <span className={cx("absolute top-0.5 size-5 rounded-full bg-white shadow transition-all", valor ? "left-[22px]" : "left-0.5")} />
      </span>
      {etiqueta}
    </button>
  );
}

// ---------------------------------------------------------------- ventana modal

export function Modal({ abierto, titulo, onCerrar, children, pie, ancho = "max-w-2xl" }: { abierto: boolean; titulo: React.ReactNode; onCerrar: () => void; children: React.ReactNode; pie?: React.ReactNode; ancho?: string }) {
  useEffect(() => {
    if (!abierto) return;
    const tecla = (e: KeyboardEvent) => e.key === "Escape" && onCerrar();
    document.addEventListener("keydown", tecla);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", tecla);
      document.body.style.overflow = "";
    };
  }, [abierto, onCerrar]);
  if (!abierto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div role="dialog" aria-modal="true" className={cx("aparecer flex max-h-[92dvh] w-full flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl", ancho)}>
        <header className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-3.5">
          <h2 className="text-base font-semibold text-slate-900">{titulo}</h2>
          <button onClick={onCerrar} aria-label="Cerrar" className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100">
            <X className="size-5" />
          </button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {pie && <footer className="flex flex-wrap justify-end gap-2 border-t border-slate-100 bg-slate-50 px-5 py-3 sm:rounded-b-2xl">{pie}</footer>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- tabla

export type Columna<T = any> = {
  clave: string;
  titulo: string;
  render?: (fila: T) => React.ReactNode;
  alinear?: "derecha" | "centro";
  ocultarMovil?: boolean;
  clase?: string;
};

export function Tabla<T extends Record<string, any>>({ columnas, filas, onFila, claveFila = "id", vacio = "Sin registros." }: { columnas: Columna<T>[]; filas: T[]; onFila?: (fila: T) => void; claveFila?: string; vacio?: string }) {
  if (!filas.length) return <Vacio titulo={vacio} />;
  return (
    <div className="overflow-x-auto">
      <table className="tabla w-full border-collapse">
        <thead>
          <tr>
            {columnas.map((c) => (
              <th key={c.clave} className={cx(c.alinear === "derecha" && "!text-right", c.alinear === "centro" && "!text-center", c.ocultarMovil && "hidden md:table-cell")}>
                {c.titulo}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((f, i) => (
            <tr key={f[claveFila] ?? i} onClick={onFila ? () => onFila(f) : undefined} className={onFila ? "cursor-pointer" : undefined}>
              {columnas.map((c) => (
                <td key={c.clave} className={cx(c.alinear === "derecha" && "cifra text-right", c.alinear === "centro" && "text-center", c.ocultarMovil && "hidden md:table-cell", c.clase)}>
                  {c.render ? c.render(f) : (f[c.clave] ?? <span className="text-slate-400">—</span>)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Paginacion({ pagina, tam, total, onCambio }: { pagina: number; tam: number; total: number; onCambio: (p: number) => void }) {
  const paginas = Math.max(1, Math.ceil(total / tam));
  if (total <= tam) return <p className="px-4 py-2 text-xs text-slate-500">{total} registro(s)</p>;
  return (
    <div className="flex items-center justify-between px-4 py-2 text-xs text-slate-500">
      <span>
        {(pagina - 1) * tam + 1}–{Math.min(pagina * tam, total)} de {total}
      </span>
      <div className="flex items-center gap-1">
        <Boton variante="secundario" tam="sm" disabled={pagina <= 1} onClick={() => onCambio(pagina - 1)} aria-label="Anterior">
          <ChevronLeft className="size-4" />
        </Boton>
        <span className="px-2">
          {pagina} / {paginas}
        </span>
        <Boton variante="secundario" tam="sm" disabled={pagina >= paginas} onClick={() => onCambio(pagina + 1)} aria-label="Siguiente">
          <ChevronRight className="size-4" />
        </Boton>
      </div>
    </div>
  );
}

export function Pestanas({ opciones, valor, onCambio }: { opciones: { valor: string; texto: string; contador?: number }[]; valor: string; onCambio: (v: string) => void }) {
  return (
    <div className="no-imprimir mb-4 flex gap-1 overflow-x-auto border-b border-slate-200">
      {opciones.map((o) => (
        <button
          key={o.valor}
          onClick={() => onCambio(o.valor)}
          className={cx("-mb-px border-b-2 px-3 py-2 text-sm font-medium whitespace-nowrap transition", valor === o.valor ? "border-marca-600 text-marca-700" : "border-transparent text-slate-500 hover:text-slate-800")}
        >
          {o.texto}
          {o.contador !== undefined && <span className="ml-1.5 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">{o.contador}</span>}
        </button>
      ))}
    </div>
  );
}

export function Dato({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">{etiqueta}</dt>
      <dd className="mt-0.5 truncate text-sm text-slate-900">{children ?? "—"}</dd>
    </div>
  );
}

// ---------------------------------------------------------------- notificaciones

type Notificacion = { id: number; tipo: "exito" | "error" | "info"; texto: string };
const ContextoAvisos = createContext<(tipo: Notificacion["tipo"], texto: string) => void>(() => {});

export function ProveedorAvisos({ children }: { children: React.ReactNode }) {
  const [lista, setLista] = useState<Notificacion[]>([]);
  const siguiente = useRef(1);
  const avisar = useCallback((tipo: Notificacion["tipo"], texto: string) => {
    const id = siguiente.current++;
    setLista((l) => [...l.slice(-3), { id, tipo, texto }]);
    setTimeout(() => setLista((l) => l.filter((n) => n.id !== id)), tipo === "error" ? 7000 : 3500);
  }, []);
  return (
    <ContextoAvisos.Provider value={avisar}>
      {children}
      <div className="no-imprimir pointer-events-none fixed inset-x-0 top-3 z-[60] flex flex-col items-center gap-2 px-3" aria-live="polite">
        {lista.map((n) => (
          <div
            key={n.id}
            className={cx(
              "aparecer pointer-events-auto flex max-w-md items-start gap-2 rounded-xl px-4 py-3 text-sm font-medium text-white shadow-lg",
              n.tipo === "exito" ? "bg-emerald-600" : n.tipo === "error" ? "bg-rose-600" : "bg-slate-800",
            )}
          >
            {n.tipo === "exito" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" /> : n.tipo === "error" ? <XCircle className="mt-0.5 size-4 shrink-0" /> : <Info className="mt-0.5 size-4 shrink-0" />}
            {n.texto}
          </div>
        ))}
      </div>
    </ContextoAvisos.Provider>
  );
}

export const useAviso = () => useContext(ContextoAvisos);

/** Ejecuta una accion mostrando el resultado; devuelve true si termino bien. */
export function useAccion() {
  const avisar = useAviso();
  const [ocupado, setOcupado] = useState(false);
  const ejecutar = useCallback(
    async (accion: () => Promise<unknown>, exito?: string): Promise<boolean> => {
      setOcupado(true);
      try {
        await accion();
        if (exito) avisar("exito", exito);
        return true;
      } catch (e: any) {
        avisar("error", e?.message ?? "Ocurrio un error.");
        return false;
      } finally {
        setOcupado(false);
      }
    },
    [avisar],
  );
  return { ejecutar, ocupado };
}
