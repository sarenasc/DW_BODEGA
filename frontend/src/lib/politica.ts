import type { CampoCrud } from "@/components/Crud";

const op = (lista: string[][]) => lista.map(([valor, texto]) => ({ valor, texto }));

export const GRANULARIDADES = op([
  ["POR_ENVASE", "Por unidad / envase (un QR por envase)"],
  ["POR_LOTE", "Por lote (una existencia por lote)"],
  ["CONSOLIDADA", "Cantidad consolidada (una existencia por ingreso)"],
  ["UNIDAD_LOGISTICA", "Unidad logística (pallet con su QR)"],
]);
export const ESTRATEGIAS = op([
  ["FIFO", "FIFO: primero el ingreso más antiguo"],
  ["FEFO", "FEFO: primero el vencimiento más próximo"],
  ["FEFO_FIFO", "FEFO + FIFO: vencimiento y luego ingreso"],
  ["SIN_RECOMENDACION", "Sin recomendación"],
]);
export const POLITICAS_FIFO = op([
  ["ADVERTIR", "Solo advertir"],
  ["BLOQUEAR", "Bloquear"],
  ["JUSTIFICAR", "Permitir con justificación"],
  ["PERMISO", "Permitir solo con permiso especial"],
]);

/** Configuracion heredable familia -> subfamilia -> producto. Vacio significa "heredar". */
export function camposPolitica(plantillas: { id: number; nombre: string }[]): CampoCrud[] {
  const s = "Configuración de inventario (vacío = heredar)";
  return [
    { clave: "usa_lote", etiqueta: "¿Utiliza lote?", tipo: "heredable", seccion: s },
    { clave: "plantilla_lote_id", etiqueta: "Plantilla de lote", tipo: "select", opciones: plantillas.map((p) => ({ valor: p.id, texto: p.nombre })), seccion: s },
    { clave: "usa_vencimiento", etiqueta: "¿Utiliza vencimiento?", tipo: "heredable", seccion: s },
    { clave: "vida_util_meses", etiqueta: "Vida útil (meses)", tipo: "numero", seccion: s },
    { clave: "prioridad_vencimiento", etiqueta: "Prioridad del vencimiento", tipo: "select", opciones: op([["MANUAL", "Fecha manual"], ["CALCULADA", "Fecha calculada"]]), seccion: s },
    { clave: "vida_util_abierto_dias", etiqueta: "Vida útil tras apertura (días)", tipo: "numero", seccion: s },
    { clave: "usa_serie", etiqueta: "¿Utiliza serie?", tipo: "heredable", seccion: s },
    { clave: "requiere_qr", etiqueta: "¿Requiere QR?", tipo: "heredable", seccion: s },
    { clave: "requiere_ubicacion", etiqueta: "¿Requiere ubicación?", tipo: "heredable", seccion: s },
    { clave: "permite_sublotes", etiqueta: "¿Permite sublotes?", tipo: "heredable", seccion: s },
    { clave: "granularidad", etiqueta: "Granularidad de inventario", tipo: "select", opciones: GRANULARIDADES, seccion: s, ancho: 2 },
    { clave: "estrategia_salida", etiqueta: "Estrategia de salida", tipo: "select", opciones: ESTRATEGIAS, seccion: s },
    { clave: "politica_fifo", etiqueta: "Política ante desviación", tipo: "select", opciones: POLITICAS_FIFO, seccion: s },
  ];
}

export const NOMBRE_POLITICA: Record<string, string> = {
  usa_lote: "Utiliza lote",
  usa_vencimiento: "Utiliza vencimiento",
  usa_serie: "Utiliza serie",
  requiere_qr: "Requiere QR",
  requiere_ubicacion: "Requiere ubicación",
  granularidad: "Granularidad",
  estrategia_salida: "Estrategia de salida",
  politica_fifo: "Política ante desviación",
  vida_util_meses: "Vida útil (meses)",
  prioridad_vencimiento: "Prioridad vencimiento",
  vida_util_abierto_dias: "Vida útil abierto (días)",
  plantilla_lote_id: "Plantilla de lote",
  permite_sublotes: "Permite sublotes",
};
