// Formato de numeros y fechas para Chile. Las fechas llegan en UTC (sufijo Z) y se muestran en hora local.

const LOCAL = "es-CL";

export function num(v: number | string | null | undefined, decimales = 2): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(LOCAL, { minimumFractionDigits: 0, maximumFractionDigits: decimales });
}

export function clp(v: number | string | null | undefined, decimales = 0): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `$${n.toLocaleString(LOCAL, { minimumFractionDigits: 0, maximumFractionDigits: decimales })}`;
}

/** Monto abreviado para tarjetas: $1,2 M, $350 mil. */
export function clpCorto(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1_000_000) return `$${(v / 1_000_000).toLocaleString(LOCAL, { maximumFractionDigits: 1 })} M`;
  if (a >= 10_000) return `$${Math.round(v / 1000).toLocaleString(LOCAL)} mil`;
  return clp(v);
}

function aFecha(v: string | null | undefined): Date | null {
  if (!v) return null;
  // Una fecha sin hora (YYYY-MM-DD) se interpreta como dia local, no como medianoche UTC.
  const d = /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T12:00:00`) : new Date(v);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fecha(v: string | null | undefined): string {
  const d = aFecha(v);
  return d ? d.toLocaleDateString(LOCAL, { day: "2-digit", month: "2-digit", year: "numeric" }) : "—";
}

export function fechaHora(v: string | null | undefined): string {
  const d = aFecha(v);
  return d ? `${fecha(v)} ${d.toLocaleTimeString(LOCAL, { hour: "2-digit", minute: "2-digit" })}` : "—";
}

export function hora(v: string | null | undefined): string {
  const d = aFecha(v);
  return d ? d.toLocaleTimeString(LOCAL, { hour: "2-digit", minute: "2-digit" }) : "—";
}

export function diasDesde(v: string | null | undefined): number | null {
  const d = aFecha(v);
  return d ? Math.floor((Date.now() - d.getTime()) / 86_400_000) : null;
}

export function hoyISO(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/** Texto legible para codigos en mayusculas: STOCK_BAJO -> Stock bajo. */
export function etiqueta(codigo: string | null | undefined): string {
  if (!codigo) return "—";
  const t = codigo.replace(/_/g, " ").toLowerCase();
  return t.charAt(0).toUpperCase() + t.slice(1);
}
