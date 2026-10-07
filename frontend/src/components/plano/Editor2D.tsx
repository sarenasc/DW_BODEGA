"use client";

// Editor en planta: grilla en metros, arrastrar para mover con ajuste magnetico. Es el editor principal;
// la vista 3D es para navegar y consultar.

import { useRef, useState } from "react";
import { celdasRack, COLOR_TIPO, colorOcupacion, type Elemento, huella, type Modo, type Ocupacion, type UbicacionPlano } from "./tipos";

const AJUSTE = 0.25; // metros

type Props = {
  largo: number;
  ancho: number;
  elementos: Elemento[];
  seleccion: string | null;
  onSeleccion: (clave: string | null) => void;
  onMover?: (clave: string, x: number, y: number, fin: boolean) => void;
  editable: boolean;
  ubicaciones: UbicacionPlano[];
  ocupacion: Map<number, Ocupacion>;
  modo: Modo;
  maxValor: number;
};

export function Editor2D({ largo, ancho, elementos, seleccion, onSeleccion, onMover, editable, ubicaciones, ocupacion, modo, maxValor }: Props) {
  const svg = useRef<SVGSVGElement>(null);
  const [arrastre, setArrastre] = useState<{ clave: string; dx: number; dy: number } | null>(null);
  const margen = 1;

  const aMetros = (e: React.PointerEvent) => {
    const r = svg.current!.getBoundingClientRect();
    const escala = (largo + margen * 2) / r.width;
    return { x: (e.clientX - r.left) * escala - margen, y: (e.clientY - r.top) * escala - margen };
  };
  const ajustar = (v: number, max: number) => Math.max(0, Math.min(max, Math.round(v / AJUSTE) * AJUSTE));

  function mover(e: React.PointerEvent, fin: boolean) {
    if (!arrastre || !onMover) return;
    const el = elementos.find((x) => x.clave === arrastre.clave);
    if (!el) return;
    const { w, d } = huella(el);
    const p = aMetros(e);
    onMover(arrastre.clave, ajustar(p.x - arrastre.dx, largo - w), ajustar(p.y - arrastre.dy, ancho - d), fin);
  }

  const lineas = [];
  for (let x = 0; x <= largo; x++) lineas.push(<line key={`x${x}`} x1={x} y1={0} x2={x} y2={ancho} stroke={x % 5 === 0 ? "#cbd5e1" : "#e9eef4"} strokeWidth={x % 5 === 0 ? 0.04 : 0.02} />);
  for (let y = 0; y <= ancho; y++) lineas.push(<line key={`y${y}`} x1={0} y1={y} x2={largo} y2={y} stroke={y % 5 === 0 ? "#cbd5e1" : "#e9eef4"} strokeWidth={y % 5 === 0 ? 0.04 : 0.02} />);
  // Las areas se dibujan debajo de racks y obstaculos.
  const orden = [...elementos].sort((a, b) => Number(a.tipo === "RACK" || a.tipo === "OBSTACULO") - Number(b.tipo === "RACK" || b.tipo === "OBSTACULO"));

  return (
    <svg
      ref={svg}
      viewBox={`${-margen} ${-margen} ${largo + margen * 2} ${ancho + margen * 2}`}
      className="w-full touch-none rounded-lg bg-white select-none"
      style={{ aspectRatio: `${largo + 2} / ${ancho + 2}`, maxHeight: "70vh" }}
      onPointerMove={(e) => mover(e, false)}
      onPointerUp={(e) => {
        mover(e, true);
        setArrastre(null);
      }}
      onPointerDown={(e) => e.target === svg.current && onSeleccion(null)}
      role="img"
      aria-label="Plano de la bodega"
    >
      <rect x={0} y={0} width={largo} height={ancho} fill="#f8fafc" stroke="#334155" strokeWidth={0.12} onPointerDown={() => onSeleccion(null)} />
      {lineas}
      {[0, 5, 10, 15, 20, 25, 30, 40, 50].filter((v) => v <= largo).map((v) => (
        <text key={v} x={v} y={-0.3} fontSize={0.45} textAnchor="middle" fill="#94a3b8">
          {v} m
        </text>
      ))}
      {orden.map((el) => {
        const { w, d } = huella(el);
        const activo = seleccion === el.clave;
        const color = el.color ?? COLOR_TIPO[el.tipo];
        const esArea = el.tipo === "ZONA" || el.tipo === "PISO" || el.tipo === "PASILLO";
        const celdas = el.tipo === "RACK" ? celdasRack(el, ubicaciones) : [];
        const posiciones = el.parametros?.posiciones ?? 1;
        const horizontal = el.rotacion % 180 === 0;
        const areaOc = esArea && el.ubicacion_id ? ocupacion.get(el.ubicacion_id) : undefined;
        return (
          <g
            key={el.clave}
            transform={`translate(${el.x} ${el.y})`}
            style={{ cursor: editable ? "move" : "pointer" }}
            onPointerDown={(e) => {
              e.stopPropagation();
              onSeleccion(el.clave);
              if (!editable) return;
              (e.target as Element).setPointerCapture?.(e.pointerId);
              const p = aMetros(e);
              setArrastre({ clave: el.clave, dx: p.x - el.x, dy: p.y - el.y });
            }}
          >
            <rect width={w} height={d} rx={0.08} fill={esArea ? color : "#fff"} fillOpacity={esArea ? (areaOc ? 0.45 : 0.22) : 1} stroke={activo ? "#059669" : color} strokeWidth={activo ? 0.14 : 0.06} strokeDasharray={el.tipo === "PASILLO" ? "0.3 0.2" : undefined} />
            {el.tipo === "OBSTACULO" && <rect width={w} height={d} fill={color} />}
            {el.tipo === "RACK" &&
              Array.from({ length: posiciones }, (_, p) => {
                // En planta se ve la posicion mas ocupada de la columna (cualquier nivel).
                const columna = celdas.filter((c) => c.posicion === p).map((c) => (c.ubicacion ? ocupacion.get(c.ubicacion.id) : undefined));
                const con = columna.find((o) => o && o.existencias > 0);
                const paso = (horizontal ? w : d) / posiciones;
                const rx = horizontal ? p * paso + 0.06 : 0.06;
                const ry = horizontal ? 0.06 : p * paso + 0.06;
                return <rect key={p} x={rx} y={ry} width={(horizontal ? paso : w) - 0.12} height={(horizontal ? d : paso) - 0.12} rx={0.05} fill={colorOcupacion(con, modo, maxValor)} />;
              })}
            <text x={w / 2} y={el.tipo === "RACK" ? -0.18 : d / 2 + 0.15} fontSize={Math.min(0.55, Math.max(0.32, w / 9))} textAnchor="middle" fill="#0f172a" fontWeight={600} pointerEvents="none">
              {el.nombre}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
