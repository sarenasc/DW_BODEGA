"use client";

// Vista 3D de consulta: navegar la bodega y ver ocupacion, antiguedad, vencimiento o valor por posicion.

import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { useMemo, useState } from "react";
import { celdasRack, COLOR_TIPO, colorOcupacion, type Elemento, huella, type Modo, type Ocupacion, type UbicacionPlano, VACIO } from "./tipos";

type Props = {
  largo: number;
  ancho: number;
  alto: number;
  elementos: Elemento[];
  ubicaciones: UbicacionPlano[];
  ocupacion: Map<number, Ocupacion>;
  modo: Modo;
  maxValor: number;
  seleccion: number | null;
  onUbicacion: (id: number) => void;
};

function Rack({ el, ubicaciones, ocupacion, modo, maxValor, seleccion, onUbicacion }: { el: Elemento } & Omit<Props, "largo" | "ancho" | "alto" | "elementos">) {
  const [sobre, setSobre] = useState<number | null>(null);
  const celdas = useMemo(() => celdasRack(el, ubicaciones), [el, ubicaciones]);
  const niveles = el.parametros?.niveles ?? 1;
  const posiciones = el.parametros?.posiciones ?? 1;
  const paso = el.ancho / posiciones;
  const altoNivel = el.alto / niveles;
  const { w, d } = huella(el);
  const tocar = (e: ThreeEvent<MouseEvent>, id: number | undefined) => {
    e.stopPropagation();
    if (id) onUbicacion(id);
  };
  return (
    // El grupo se ubica en el centro de la huella y gira sobre su eje vertical.
    <group position={[el.x + w / 2, 0, el.y + d / 2]} rotation={[0, el.rotacion % 180 === 0 ? 0 : -Math.PI / 2, 0]}>
      {/* Postes y largueros */}
      {Array.from({ length: posiciones + 1 }, (_, i) =>
        [-1, 1].map((lado) => (
          <mesh key={`${i}${lado}`} position={[-el.ancho / 2 + i * paso, el.alto / 2, (lado * el.fondo) / 2]}>
            <boxGeometry args={[0.07, el.alto, 0.07]} />
            <meshStandardMaterial color="#1e3a5f" />
          </mesh>
        )),
      )}
      {Array.from({ length: niveles + 1 }, (_, n) => (
        <mesh key={n} position={[0, n * altoNivel + 0.03, 0]}>
          <boxGeometry args={[el.ancho, 0.05, el.fondo]} />
          <meshStandardMaterial color="#f97316" />
        </mesh>
      ))}
      {celdas.map((c) => {
        const o = c.ubicacion ? ocupacion.get(c.ubicacion.id) : undefined;
        const lleno = !!o && o.existencias > 0;
        const activa = c.ubicacion?.id === seleccion || c.ubicacion?.id === sobre;
        // La caja crece con la ocupacion; una posicion vacia se dibuja como una losa tenue para poder seleccionarla.
        const h = lleno ? altoNivel * (0.35 + 0.5 * Math.min(1, o.ocupacion ?? 0.7)) : 0.04;
        return (
          <mesh
            key={`${c.nivel}-${c.posicion}`}
            position={[-el.ancho / 2 + (c.posicion + 0.5) * paso, c.nivel * altoNivel + 0.07 + h / 2, 0]}
            onClick={(e) => tocar(e, c.ubicacion?.id)}
            onPointerOver={(e) => {
              e.stopPropagation();
              setSobre(c.ubicacion?.id ?? null);
            }}
            onPointerOut={() => setSobre(null)}
          >
            <boxGeometry args={[paso * 0.82, h, el.fondo * 0.82]} />
            <meshStandardMaterial color={activa ? "#10b981" : lleno ? colorOcupacion(o, modo, maxValor) : VACIO} transparent={!lleno} opacity={lleno ? 1 : 0.55} />
            {activa && c.ubicacion && (
              <Html center distanceFactor={12} position={[0, h / 2 + 0.35, 0]} style={{ pointerEvents: "none" }}>
                <div className="rounded-md bg-slate-900/90 px-2 py-1 text-[11px] font-semibold whitespace-nowrap text-white shadow">{c.ubicacion.codigo_completo}</div>
              </Html>
            )}
          </mesh>
        );
      })}
      <Html center position={[0, el.alto + 0.5, 0]} distanceFactor={16} style={{ pointerEvents: "none" }}>
        <div className="rounded bg-white/90 px-1.5 py-0.5 text-xs font-bold text-slate-800 shadow-sm">{el.nombre}</div>
      </Html>
    </group>
  );
}

function Area({ el, ocupacion, modo, maxValor, onUbicacion, seleccion }: { el: Elemento; ocupacion: Map<number, Ocupacion>; modo: Modo; maxValor: number; onUbicacion: (id: number) => void; seleccion: number | null }) {
  const { w, d } = huella(el);
  const o = el.ubicacion_id ? ocupacion.get(el.ubicacion_id) : undefined;
  const color = el.color ?? COLOR_TIPO[el.tipo];
  if (el.tipo === "OBSTACULO")
    return (
      <mesh position={[el.x + w / 2, el.alto / 2, el.y + d / 2]}>
        <boxGeometry args={[w, el.alto, d]} />
        <meshStandardMaterial color={color} />
      </mesh>
    );
  // Bultos sobre el piso: una pila por cada existencia (hasta llenar el area).
  const columnas = Math.max(1, Math.floor(w / 1.3));
  const filas = Math.max(1, Math.floor(d / 1.3));
  const pilas = Math.min(o?.existencias ?? 0, columnas * filas);
  return (
    <group position={[el.x, 0, el.y]}>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[w / 2, 0.02, d / 2]} onClick={(e) => { e.stopPropagation(); if (el.ubicacion_id) onUbicacion(el.ubicacion_id); }}>
        <planeGeometry args={[w, d]} />
        <meshStandardMaterial color={color} transparent opacity={el.ubicacion_id === seleccion ? 0.75 : el.tipo === "PASILLO" ? 0.25 : 0.4} />
      </mesh>
      {Array.from({ length: pilas }, (_, i) => (
        <mesh key={i} position={[((i % columnas) + 0.5) * (w / columnas), 0.5, (Math.floor(i / columnas) + 0.5) * (d / filas)]} onClick={(e) => { e.stopPropagation(); if (el.ubicacion_id) onUbicacion(el.ubicacion_id); }}>
          <cylinderGeometry args={[0.38, 0.38, 0.95, 20]} />
          <meshStandardMaterial color={colorOcupacion(o, modo, maxValor)} />
        </mesh>
      ))}
      {el.tipo !== "PASILLO" && (
        <Html center position={[w / 2, 1.6, d / 2]} distanceFactor={16} style={{ pointerEvents: "none" }}>
          <div className="rounded bg-white/90 px-1.5 py-0.5 text-xs font-bold text-slate-800 shadow-sm">{el.nombre}</div>
        </Html>
      )}
    </group>
  );
}

export default function Visor3D(p: Props) {
  const { largo, ancho, alto } = p;
  const centro: [number, number, number] = [largo / 2, 0, ancho / 2];
  const distancia = Math.max(largo, ancho);
  return (
    <div className="h-[70vh] min-h-96 w-full overflow-hidden rounded-lg bg-gradient-to-b from-slate-200 to-slate-100">
      <Canvas camera={{ position: [largo / 2 - distancia * 0.55, distancia * 0.7, ancho / 2 + distancia * 0.95], fov: 45, near: 0.1, far: 500 }} shadows={false} dpr={[1, 2]}>
        <ambientLight intensity={0.85} />
        <directionalLight position={[largo, 30, ancho]} intensity={1.1} />
        <directionalLight position={[-10, 20, -10]} intensity={0.4} />
        {/* Piso y muros */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[largo / 2, 0, ancho / 2]}>
          <planeGeometry args={[largo, ancho]} />
          <meshStandardMaterial color="#e2e8f0" />
        </mesh>
        <gridHelper args={[Math.max(largo, ancho) * 2, Math.max(largo, ancho) * 2, "#cbd5e1", "#e8edf3"]} position={[largo / 2, 0.005, ancho / 2]} />
        {[
          [largo / 2, 0, largo, 0.12],
          [0, ancho / 2, 0.12, ancho],
        ].map(([x, z, w, d], i) => (
          <mesh key={i} position={[x, alto / 2, z]}>
            <boxGeometry args={[w, alto, d]} />
            <meshStandardMaterial color="#94a3b8" transparent opacity={0.22} />
          </mesh>
        ))}
        {p.elementos.map((el) =>
          el.tipo === "RACK" ? (
            <Rack key={el.clave} el={el} ubicaciones={p.ubicaciones} ocupacion={p.ocupacion} modo={p.modo} maxValor={p.maxValor} seleccion={p.seleccion} onUbicacion={p.onUbicacion} />
          ) : (
            <Area key={el.clave} el={el} ocupacion={p.ocupacion} modo={p.modo} maxValor={p.maxValor} seleccion={p.seleccion} onUbicacion={p.onUbicacion} />
          ),
        )}
        <OrbitControls target={centro} maxPolarAngle={Math.PI / 2.05} minDistance={3} maxDistance={distancia * 3} enableDamping />
      </Canvas>
    </div>
  );
}
