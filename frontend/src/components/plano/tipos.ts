export type Elemento = {
  id?: number;
  clave: string; // identificador local estable (los elementos nuevos aun no tienen id)
  tipo: "RACK" | "ZONA" | "PISO" | "PASILLO" | "OBSTACULO";
  nombre: string;
  x: number;
  y: number;
  ancho: number;
  fondo: number;
  alto: number;
  rotacion: number;
  color: string | null;
  parametros: { niveles?: number; posiciones?: number } | null;
  ubicacion_id: number | null;
};

export type UbicacionPlano = { id: number; padre_id: number | null; tipo: string; codigo: string; orden: number; codigo_completo: string; almacenable: boolean; capacidad: number | null };
export type Ocupacion = { ubicacion_id: number; existencias: number; bultos?: number; cantidad: number; valor: number | null; dias_antiguedad: number | null; dias_para_vencer: number | null; ocupacion: number | null };
export type Modo = "ocupacion" | "antiguedad" | "vencimiento" | "valor";

export const COLOR_TIPO: Record<Elemento["tipo"], string> = { RACK: "#475569", ZONA: "#f59e0b", PISO: "#38bdf8", PASILLO: "#cbd5e1", OBSTACULO: "#64748b" };
export const NOMBRE_TIPO: Record<Elemento["tipo"], string> = { RACK: "Rack", ZONA: "Zona", PISO: "Área de piso", PASILLO: "Pasillo", OBSTACULO: "Obstáculo" };

/** Tamano en planta considerando la rotacion (0 o 90 grados). */
export function huella(e: Elemento): { w: number; d: number } {
  return e.rotacion % 180 === 0 ? { w: e.ancho, d: e.fondo } : { w: e.fondo, d: e.ancho };
}

export const VACIO = "#e2e8f0";

/** Color de una posicion segun el modo de visualizacion. Devuelve tambien la leyenda del tramo. */
export function colorOcupacion(o: Ocupacion | undefined, modo: Modo, maxValor: number): string {
  if (!o || o.existencias === 0) return VACIO;
  if (modo === "ocupacion") {
    const f = o.ocupacion ?? 0.6;
    return f >= 0.9 ? "#0f766e" : f >= 0.5 ? "#14b8a6" : "#5eead4";
  }
  if (modo === "antiguedad") {
    const d = o.dias_antiguedad ?? 0;
    return d > 90 ? "#b91c1c" : d > 60 ? "#f97316" : d > 30 ? "#facc15" : "#22c55e";
  }
  if (modo === "vencimiento") {
    const d = o.dias_para_vencer;
    if (d === null) return "#94a3b8";
    return d < 0 ? "#b91c1c" : d <= 30 ? "#f97316" : d <= 90 ? "#facc15" : "#22c55e";
  }
  const f = maxValor > 0 && o.valor ? o.valor / maxValor : 0;
  return f > 0.66 ? "#1e3a8a" : f > 0.33 ? "#3b82f6" : "#93c5fd";
}

export const LEYENDAS: Record<Modo, [string, string][]> = {
  ocupacion: [[VACIO, "Vacía"], ["#5eead4", "Baja"], ["#14b8a6", "Media"], ["#0f766e", "Alta"]],
  antiguedad: [[VACIO, "Vacía"], ["#22c55e", "0–30 días"], ["#facc15", "31–60"], ["#f97316", "61–90"], ["#b91c1c", "Más de 90"]],
  vencimiento: [[VACIO, "Vacía"], ["#94a3b8", "Sin vencimiento"], ["#22c55e", "Más de 90 días"], ["#facc15", "31–90"], ["#f97316", "≤ 30"], ["#b91c1c", "Vencido"]],
  valor: [[VACIO, "Vacía"], ["#93c5fd", "Bajo"], ["#3b82f6", "Medio"], ["#1e3a8a", "Alto"]],
};

/** Celdas (nivel, posicion) de un rack con la ubicacion logica que corresponde a cada una. */
export function celdasRack(e: Elemento, ubicaciones: UbicacionPlano[]): { nivel: number; posicion: number; ubicacion: UbicacionPlano | null }[] {
  const niveles = e.parametros?.niveles ?? 1;
  const posiciones = e.parametros?.posiciones ?? 1;
  const hijos = (id: number) => ubicaciones.filter((u) => u.padre_id === id).sort((a, b) => a.orden - b.orden || a.codigo.localeCompare(b.codigo));
  const filas = e.ubicacion_id ? hijos(e.ubicacion_id) : [];
  const celdas = [];
  for (let n = 0; n < niveles; n++) {
    const pos = filas[n] ? hijos(filas[n].id) : [];
    for (let p = 0; p < posiciones; p++) celdas.push({ nivel: n, posicion: p, ubicacion: pos[p] ?? null });
  }
  return celdas;
}
