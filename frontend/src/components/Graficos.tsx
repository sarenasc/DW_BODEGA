"use client";

// Graficos del sistema. Una sola serie por grafico y un solo tono para magnitudes: la identidad la da la etiqueta, no el color.

import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { clp, clpCorto, fecha, num } from "@/lib/formato";
import { Vacio } from "./ui";

const TONO = "#0f766e";

type Barra = { nombre: string; valor: number; detalle?: string; href?: string };

/** Barras horizontales con etiqueta y valor directos. Adecuado para rankings y composiciones cortas. */
export function BarrasLista({ datos, formato = "moneda", maximo = 8, vacio = "Sin datos en el período." }: { datos: Barra[]; formato?: "moneda" | "numero" | "moneda4"; maximo?: number; vacio?: string }) {
  const filas = datos.filter((d) => d.valor > 0).slice(0, maximo);
  if (!filas.length) return <Vacio titulo={vacio} />;
  const tope = Math.max(...filas.map((d) => d.valor));
  const texto = (v: number) => (formato === "moneda" ? clp(v) : formato === "moneda4" ? clp(v, 2) : num(v));
  return (
    <ul className="space-y-2.5">
      {filas.map((d) => (
        <li key={d.nombre} title={`${d.nombre}: ${texto(d.valor)}${d.detalle ? ` · ${d.detalle}` : ""}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
            <span className="truncate text-slate-700">{d.nombre}</span>
            <span className="cifra shrink-0 font-medium text-slate-900">
              {texto(d.valor)}
              {d.detalle && <span className="ml-1.5 text-xs font-normal text-slate-500">{d.detalle}</span>}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full" style={{ width: `${Math.max(2, (d.valor / tope) * 100)}%`, background: TONO }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Evolucion diaria de un monto, con cursor y valor al pasar el puntero. */
export function SerieDiaria({ datos, alto = 220 }: { datos: { fecha: string; costo: number }[]; alto?: number }) {
  if (!datos.length || datos.every((d) => !d.costo)) return <Vacio titulo="Sin consumos en el período." />;
  return (
    <div style={{ height: alto }} role="img" aria-label="Costo de consumo por día">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={datos} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="relleno-serie" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={TONO} stopOpacity={0.22} />
              <stop offset="100%" stopColor={TONO} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e2e8f0" strokeDasharray="2 4" vertical={false} />
          <XAxis dataKey="fecha" tickFormatter={(v) => fecha(v).slice(0, 5)} tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={{ stroke: "#cbd5e1" }} minTickGap={28} />
          <YAxis tickFormatter={(v) => clpCorto(v)} tick={{ fontSize: 11, fill: "#64748b" }} tickLine={false} axisLine={false} width={64} />
          <Tooltip
            cursor={{ stroke: "#94a3b8", strokeDasharray: "3 3" }}
            formatter={(v) => [clp(Number(v)), "Costo de consumo"]}
            labelFormatter={(v) => fecha(String(v))}
            contentStyle={{ borderRadius: 10, border: "1px solid #e2e8f0", fontSize: 12, boxShadow: "0 8px 24px rgba(15,23,42,.12)" }}
          />
          <Area type="monotone" dataKey="costo" stroke={TONO} strokeWidth={2} fill="url(#relleno-serie)" dot={false} activeDot={{ r: 4, stroke: "#fff", strokeWidth: 2 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Distribucion por rangos (antiguedad): columnas con el valor rotulado. */
export function Columnas({ datos, formato = "moneda" }: { datos: { nombre: string; valor: number; detalle?: string }[]; formato?: "moneda" | "numero" }) {
  const tope = Math.max(1, ...datos.map((d) => d.valor));
  return (
    <div className="flex h-44 items-end gap-2">
      {datos.map((d) => (
        <div key={d.nombre} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1" title={`${d.nombre}: ${formato === "moneda" ? clp(d.valor) : num(d.valor)}${d.detalle ? ` · ${d.detalle}` : ""}`}>
          <span className="cifra truncate text-[11px] font-medium text-slate-700">{formato === "moneda" ? clpCorto(d.valor) : num(d.valor)}</span>
          <div className="w-full max-w-14 rounded-t-[4px]" style={{ height: `${Math.max(d.valor ? 3 : 0, (d.valor / tope) * 78)}%`, background: TONO }} />
          <span className="truncate text-[11px] text-slate-500">{d.nombre}</span>
        </div>
      ))}
    </div>
  );
}
