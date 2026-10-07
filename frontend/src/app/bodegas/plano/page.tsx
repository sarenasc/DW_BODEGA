"use client";

import { Copy, ListTree, Redo2, RotateCw, Save, Trash2, Undo2 } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ContenidoUbicacion } from "@/components/ContenidoUbicacion";
import { Editor2D } from "@/components/plano/Editor2D";
import { COLOR_TIPO, type Elemento, LEYENDAS, type Modo, NOMBRE_TIPO, type Ocupacion } from "@/components/plano/tipos";
import { Aviso, Boton, Campo, Cargando, cx, Encabezado, EnlaceBoton, Entrada, Pestanas, Selector, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

const Visor3D = dynamic(() => import("@/components/plano/Visor3D"), { ssr: false, loading: () => <Cargando texto="Preparando vista 3D…" /> });

const PALETA: { tipo: Elemento["tipo"]; base: Partial<Elemento> }[] = [
  { tipo: "RACK", base: { ancho: 6, fondo: 1.2, alto: 4.5, parametros: { niveles: 3, posiciones: 5 } } },
  { tipo: "ZONA", base: { ancho: 4, fondo: 4, alto: 0.08 } },
  { tipo: "PISO", base: { ancho: 4, fondo: 3, alto: 0.08 } },
  { tipo: "PASILLO", base: { ancho: 8, fondo: 1.5, alto: 0.05 } },
  { tipo: "OBSTACULO", base: { ancho: 0.5, fondo: 0.5, alto: 5 } },
];
const MODOS: { valor: Modo; texto: string }[] = [
  { valor: "ocupacion", texto: "Ocupación" },
  { valor: "antiguedad", texto: "Antigüedad" },
  { valor: "vencimiento", texto: "Vencimiento" },
  { valor: "valor", texto: "Valorización" },
];

export default function Plano() {
  const id = useParametro("id");
  const inicial = useParametro("ubicacion");
  const { puede } = useSesion();
  const editable = puede("bodegas:administrar");
  const plano = useDatos(id ? `/bodegas/${id}/plano` : null);
  const oc = useDatos<Ocupacion[]>(id && puede("inventario:ver") ? `/bodegas/${id}/ocupacion` : null);
  const [vista, setVista] = useState("3d");
  const [modo, setModo] = useState<Modo>("ocupacion");
  const [elementos, setElementos] = useState<Elemento[]>([]);
  const [dim, setDim] = useState({ largo: 20, ancho: 12, alto: 6 });
  const [historial, setHistorial] = useState<Elemento[][]>([]);
  const [futuro, setFuturo] = useState<Elemento[][]>([]);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [sucio, setSucio] = useState(false);
  const [contenido, setContenido] = useState<any>(null);
  const { ejecutar, ocupado } = useAccion();
  const previoArrastre = useRef<Elemento[] | null>(null);

  const cargar = useCallback((p: any) => {
    setElementos(p.elementos.map((e: any) => ({ ...e, clave: `e${e.id}`, x: Number(e.x), y: Number(e.y), ancho: Number(e.ancho), fondo: Number(e.fondo), alto: Number(e.alto) })));
    setDim({ largo: Number(p.bodega.largo ?? 20), ancho: Number(p.bodega.ancho ?? 12), alto: Number(p.bodega.alto ?? 6) });
    setHistorial([]);
    setFuturo([]);
    setSucio(false);
  }, []);
  useEffect(() => {
    if (plano.datos) cargar(plano.datos);
  }, [plano.datos, cargar]);

  const ocupacion = useMemo(() => new Map((oc.datos ?? []).map((o) => [o.ubicacion_id, o])), [oc.datos]);
  const maxValor = useMemo(() => Math.max(0, ...(oc.datos ?? []).map((o) => o.valor ?? 0)), [oc.datos]);
  const ubicaciones = plano.datos?.ubicaciones ?? [];
  const sel = elementos.find((e) => e.clave === seleccion) ?? null;

  const verUbicacion = useCallback((uid: number) => {
    api.get(`/ubicaciones/${uid}/contenido`).then(setContenido).catch(() => {});
  }, []);
  useEffect(() => {
    if (inicial) verUbicacion(Number(inicial));
  }, [inicial, verUbicacion]);

  /** Aplica un cambio guardando el estado previo para deshacer. */
  const cambiar = (f: (lista: Elemento[]) => Elemento[], registrar = true) => {
    setElementos((actual) => {
      if (registrar) {
        setHistorial((h) => [...h.slice(-40), actual]);
        setFuturo([]);
      }
      return f(actual);
    });
    setSucio(true);
  };
  const editar = (cambios: Partial<Elemento>) => sel && cambiar((l) => l.map((e) => (e.clave === sel.clave ? { ...e, ...cambios } : e)));
  const deshacer = () => {
    const previo = historial.at(-1);
    if (!previo) return;
    setFuturo((f) => [elementos, ...f]);
    setHistorial((h) => h.slice(0, -1));
    setElementos(previo);
  };
  const rehacer = () => {
    const [sig, ...resto] = futuro;
    if (!sig) return;
    setHistorial((h) => [...h, elementos]);
    setFuturo(resto);
    setElementos(sig);
  };
  const nombreLibre = (tipo: Elemento["tipo"]) => {
    const prefijo = { RACK: "R", ZONA: "ZONA", PISO: "PISO", PASILLO: "Pasillo ", OBSTACULO: "Pilar " }[tipo];
    for (let n = 1; n < 200; n++) {
      const nombre = tipo === "RACK" ? `${prefijo}${String(n).padStart(2, "0")}` : `${prefijo}${n}`;
      if (!elementos.some((e) => e.nombre === nombre)) return nombre;
    }
    return `${prefijo}${Date.now()}`;
  };
  const agregar = (tipo: Elemento["tipo"], base: Partial<Elemento>) => {
    const clave = `n${Date.now()}`;
    cambiar((l) => [...l, { clave, tipo, nombre: nombreLibre(tipo), x: 1, y: 1, ancho: 1, fondo: 1, alto: 1, rotacion: 0, color: null, parametros: null, ubicacion_id: null, ...base }]);
    setSeleccion(clave);
    setVista("2d");
  };
  const duplicar = () => {
    if (!sel) return;
    const clave = `n${Date.now()}`;
    // La copia es un elemento nuevo: generara sus propias ubicaciones al publicar.
    cambiar((l) => [...l, { ...sel, id: undefined, clave, ubicacion_id: null, nombre: nombreLibre(sel.tipo), x: Math.min(dim.largo - 1, sel.x + 1), y: Math.min(dim.ancho - 1, sel.y + 1.5) }]);
    setSeleccion(clave);
  };

  const guardar = () =>
    ejecutar(async () => {
      const r = await api.put(`/bodegas/${id}/plano`, {
        ...dim,
        elementos: elementos.map(({ clave: _c, ...e }) => ({ ...e, nombre: (e.tipo === "PASILLO" || e.tipo === "OBSTACULO" ? e.nombre.trim() : e.nombre.trim().toUpperCase().replace(/[^A-Z0-9_]/g, "")) || "ELEMENTO" })),
      });
      plano.setDatos(r);
      oc.recargar();
    }, "Plano publicado");

  if (plano.error) return <Aviso tipo="error">{plano.error}</Aviso>;
  if (!plano.datos) return <Cargando />;

  return (
    <>
      <Encabezado titulo={`Plano · ${plano.datos.bodega.nombre}`} descripcion="Se edita en planta (2D) y se consulta en 3D. Cada posición corresponde a una ubicación lógica." volver="/bodegas/">
        <EnlaceBoton href={`/bodegas/ubicaciones/?id=${id}`} icono={<ListTree className="size-4" />}>
          Ubicaciones
        </EnlaceBoton>
        {editable && (
          <Boton icono={<Save className="size-4" />} onClick={guardar} cargando={ocupado} disabled={!sucio}>
            Publicar plano
          </Boton>
        )}
      </Encabezado>
      {sucio && <Aviso tipo="alerta" className="mb-3">Hay cambios sin publicar. Los racks nuevos generarán sus ubicaciones al publicar.</Aviso>}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Pestanas valor={vista} onCambio={setVista} opciones={[{ valor: "3d", texto: "Vista 3D" }, { valor: "2d", texto: editable ? "Editor en planta (2D)" : "Planta (2D)" }]} />
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <span className="text-xs text-slate-500">Colorear por</span>
          <Selector aria-label="Modo de color" className="!h-9 !w-40" value={modo} onChange={(e) => setModo(e.target.value as Modo)} opciones={MODOS} />
        </div>
      </div>

      <div className="grid gap-3 xl:grid-cols-[1fr_320px]">
        <Tarjeta sinRelleno className="overflow-hidden">
          {vista === "2d" && editable && (
            <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 p-2">
              <span className="px-1 text-xs font-medium text-slate-500">Agregar:</span>
              {PALETA.map((p) => (
                <Boton key={p.tipo} tam="sm" variante="secundario" onClick={() => agregar(p.tipo, p.base)}>
                  <span className="size-2.5 rounded-sm" style={{ background: COLOR_TIPO[p.tipo] }} /> {NOMBRE_TIPO[p.tipo]}
                </Boton>
              ))}
              <span className="mx-1 h-5 w-px bg-slate-200" />
              <Boton tam="sm" variante="fantasma" disabled={!historial.length} onClick={deshacer} aria-label="Deshacer"><Undo2 className="size-4" /></Boton>
              <Boton tam="sm" variante="fantasma" disabled={!futuro.length} onClick={rehacer} aria-label="Rehacer"><Redo2 className="size-4" /></Boton>
              <Boton tam="sm" variante="fantasma" disabled={!sel} onClick={() => editar({ rotacion: ((sel?.rotacion ?? 0) + 90) % 180 })} icono={<RotateCw className="size-4" />}>Rotar</Boton>
              <Boton tam="sm" variante="fantasma" disabled={!sel} onClick={duplicar} icono={<Copy className="size-4" />}>Duplicar</Boton>
              <Boton tam="sm" variante="fantasma" disabled={!sel} onClick={() => { cambiar((l) => l.filter((e) => e.clave !== seleccion)); setSeleccion(null); }} icono={<Trash2 className="size-4 text-rose-600" />}>Eliminar</Boton>
            </div>
          )}
          <div className="p-2">
            {vista === "2d" ? (
              <Editor2D
                {...dim}
                elementos={elementos}
                seleccion={seleccion}
                editable={editable}
                ubicaciones={ubicaciones}
                ocupacion={ocupacion}
                modo={modo}
                maxValor={maxValor}
                onSeleccion={(c) => {
                  setSeleccion(c);
                  const el = elementos.find((e) => e.clave === c);
                  if (!editable && el?.ubicacion_id) verUbicacion(el.ubicacion_id);
                }}
                onMover={(clave, x, y, fin) => {
                  const el = elementos.find((e) => e.clave === clave);
                  if (!el || (el.x === x && el.y === y && !fin)) return;
                  if (el.x === x && el.y === y && !previoArrastre.current) return;
                  // Un arrastre completo es un solo paso de deshacer: se guarda el estado previo al primer movimiento.
                  if (!previoArrastre.current) previoArrastre.current = elementos;
                  if (fin) {
                    const previo = previoArrastre.current;
                    previoArrastre.current = null;
                    if (previo.find((e) => e.clave === clave)?.x !== x || previo.find((e) => e.clave === clave)?.y !== y) {
                      setHistorial((h) => [...h.slice(-40), previo]);
                      setFuturo([]);
                    }
                  }
                  cambiar((l) => l.map((e) => (e.clave === clave ? { ...e, x, y } : e)), false);
                }}
              />
            ) : (
              <Visor3D {...dim} elementos={elementos} ubicaciones={ubicaciones} ocupacion={ocupacion} modo={modo} maxValor={maxValor} seleccion={contenido?.ubicacion.id ?? null} onUbicacion={verUbicacion} />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-100 px-3 py-2 text-xs text-slate-600">
            {LEYENDAS[modo].map(([color, texto]) => (
              <span key={texto} className="inline-flex items-center gap-1.5">
                <span className="size-3 rounded-sm border border-slate-300" style={{ background: color }} /> {texto}
              </span>
            ))}
            <span className="ml-auto text-slate-400">{vista === "3d" ? "Arrastre para girar · rueda para acercar · clic en una posición para ver su contenido" : editable ? "Arrastre para mover · ajuste cada 0,25 m" : "Clic en un elemento para ver su contenido"}</span>
          </div>
        </Tarjeta>

        <div className="space-y-3">
          {vista === "2d" && editable && (
            <Tarjeta titulo={sel ? `${NOMBRE_TIPO[sel.tipo]} seleccionado` : "Bodega"}>
              {!sel ? (
                <div className="grid grid-cols-3 gap-2">
                  {(["largo", "ancho", "alto"] as const).map((k) => (
                    <Campo key={k} etiqueta={`${k[0].toUpperCase()}${k.slice(1)} (m)`}>
                      <Entrada type="number" min={1} step={0.5} value={dim[k]} onChange={(e) => { setDim({ ...dim, [k]: Number(e.target.value) || 1 }); setSucio(true); }} />
                    </Campo>
                  ))}
                  <p className="col-span-3 text-xs text-slate-500">Seleccione un elemento del plano para editar sus dimensiones, o agregue uno desde la barra superior.</p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-2">
                  <Campo etiqueta={sel.tipo === "RACK" ? "Código" : "Nombre"} className="col-span-2" ayuda={sel.ubicacion_id ? "Ya tiene ubicaciones: el código lógico no cambia al renombrar." : sel.tipo === "RACK" || sel.tipo === "ZONA" || sel.tipo === "PISO" ? "Será el código de la ubicación." : undefined}>
                    <Entrada value={sel.nombre} onChange={(e) => editar({ nombre: e.target.value })} />
                  </Campo>
                  {(["x", "y", "ancho", "fondo", "alto"] as const).map((k) => (
                    <Campo key={k} etiqueta={{ x: "X (m)", y: "Y (m)", ancho: "Largo (m)", fondo: "Fondo (m)", alto: "Alto (m)" }[k]}>
                      <Entrada type="number" step={0.25} min={k === "x" || k === "y" ? 0 : 0.05} value={sel[k]} onChange={(e) => editar({ [k]: Number(e.target.value) })} />
                    </Campo>
                  ))}
                  <Campo etiqueta="Rotación">
                    <Selector value={sel.rotacion} onChange={(e) => editar({ rotacion: Number(e.target.value) })} opciones={[{ valor: 0, texto: "0°" }, { valor: 90, texto: "90°" }]} />
                  </Campo>
                  {sel.tipo === "RACK" && (
                    <>
                      <Campo etiqueta="Niveles">
                        <Entrada type="number" min={1} max={20} disabled={!!sel.ubicacion_id} value={sel.parametros?.niveles ?? 1} onChange={(e) => editar({ parametros: { ...sel.parametros, niveles: Math.max(1, Number(e.target.value)) } })} />
                      </Campo>
                      <Campo etiqueta="Posiciones">
                        <Entrada type="number" min={1} max={60} disabled={!!sel.ubicacion_id} value={sel.parametros?.posiciones ?? 1} onChange={(e) => editar({ parametros: { ...sel.parametros, posiciones: Math.max(1, Number(e.target.value)) } })} />
                      </Campo>
                      <p className="col-span-2 text-xs text-slate-500">
                        {sel.ubicacion_id
                          ? "Rack ya publicado: niveles y posiciones quedan fijos. Para otra configuración, duplique o cree un rack nuevo."
                          : `Al publicar se crearán ${1 + (sel.parametros?.niveles ?? 1) * (1 + (sel.parametros?.posiciones ?? 1))} ubicaciones (${plano.datos.bodega.codigo}-${sel.nombre}-N01-P01…).`}
                      </p>
                    </>
                  )}
                  {sel.tipo !== "RACK" && (
                    <Campo etiqueta="Color" className="col-span-2">
                      <input type="color" className={cx("campo !p-1")} value={sel.color ?? COLOR_TIPO[sel.tipo]} onChange={(e) => editar({ color: e.target.value })} />
                    </Campo>
                  )}
                </div>
              )}
            </Tarjeta>
          )}
          <Tarjeta titulo={contenido ? contenido.ubicacion.codigo_completo : "Contenido de la ubicación"}>
            {contenido ? <ContenidoUbicacion datos={contenido} /> : <p className="text-sm text-slate-500">Haga clic en una posición, rack o área para ver productos, lotes, cantidad, vencimiento, valor y capacidad disponible.</p>}
          </Tarjeta>
        </div>
      </div>
    </>
  );
}
