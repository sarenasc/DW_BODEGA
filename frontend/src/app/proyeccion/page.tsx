"use client";

// Proyeccion de insumos: con el historial por especie, calcula la receta que falta por aplicar a los kilos pendientes.

import { Calculator, Printer } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Aviso, Boton, Cargando, cx, Encabezado, Entrada, Indicador, Insignia, Interruptor, Pestanas, Selector, Tabla, Tarjeta } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Proyeccion() {
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const cat = useDatos("/catalogos");
  const [f, setF] = useState<Record<string, any>>({ solo_cerrados: true });
  const historial = useDatos<any[]>("/proyeccion/historial", f);
  const [kilos, setKilos] = useState<Record<string, string>>({});
  const [bodega, setBodega] = useState("");
  const [resultado, setResultado] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [vista, setVista] = useState("productos");
  const pendientes = Object.entries(kilos).map(([especie, v]) => ({ especie, kilos: Number(String(v).replace(/\./g, "").replace(",", ".")) })).filter((p) => p.kilos > 0);

  async function calcular() {
    setOcupado(true);
    setError(null);
    try {
      setResultado(await api.post("/proyeccion", { pendientes, ...f, desde: f.desde || null, hasta: f.hasta || null, temporada_id: f.temporada_id ? Number(f.temporada_id) : null, familia_id: f.familia_id ? Number(f.familia_id) : null, bodega_id: bodega ? Number(bodega) : null }));
    } catch (e: any) {
      setError(e.message);
      setResultado(null);
    } finally {
      setOcupado(false);
    }
  }
  const cambiarFiltro = (cambios: Record<string, any>) => {
    setF({ ...f, ...cambios });
    setResultado(null);
  };
  const r = resultado;

  return (
    <>
      <Encabezado titulo="Proyección de insumos" descripcion="Según el historial de consumo por especie, calcula la receta que falta por vaciar para los kilos que quedan por procesar, y la compara con el stock disponible.">
        {r && <Boton variante="secundario" icono={<Printer className="size-4" />} onClick={() => window.print()}>Imprimir</Boton>}
      </Encabezado>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <Tarjeta titulo="1. Kilos que faltan por procesar" className="self-start">
          <div className="no-imprimir mb-3 grid grid-cols-2 gap-2">
            <Entrada type="date" aria-label="Historial desde" title="Historial desde" value={f.desde ?? ""} onChange={(e) => cambiarFiltro({ desde: e.target.value })} />
            <Entrada type="date" aria-label="Historial hasta" title="Historial hasta" value={f.hasta ?? ""} onChange={(e) => cambiarFiltro({ hasta: e.target.value })} />
            <Selector aria-label="Temporada" vacio="Todas las temporadas" value={f.temporada_id ?? ""} onChange={(e) => cambiarFiltro({ temporada_id: e.target.value })} opciones={(cat.datos?.temporadas ?? []).map((t: any) => ({ valor: t.id, texto: t.codigo }))} />
            <Selector aria-label="Familia" vacio="Todas las familias" value={f.familia_id ?? ""} onChange={(e) => cambiarFiltro({ familia_id: e.target.value })} opciones={(cat.datos?.familias ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }))} />
            <Selector aria-label="Bodega para el stock" vacio="Stock de todas las bodegas" value={bodega} onChange={(e) => { setBodega(e.target.value); setResultado(null); }} opciones={(cat.datos?.bodegas ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }))} />
            <Interruptor valor={!!f.solo_cerrados} onCambio={(v) => cambiarFiltro({ solo_cerrados: v })} etiqueta="Solo procesos cerrados" />
          </div>
          {!historial.datos ? (
            <Cargando />
          ) : historial.datos.length === 0 ? (
            <Aviso tipo="alerta">No hay procesos con kilos y consumos en el período. Amplíe las fechas o incluya los procesos abiertos.</Aviso>
          ) : (
            <table className="tabla w-full">
              <thead>
                <tr>
                  <th>Especie</th>
                  <th className="!text-right">Historial</th>
                  {costos && <th className="!text-right">Gasto / kg</th>}
                  <th className="!text-right">Kilos pendientes</th>
                </tr>
              </thead>
              <tbody>
                {historial.datos.map((h) => (
                  <tr key={h.especie}>
                    <td className="font-medium text-slate-900">{h.especie}</td>
                    <td className="cifra text-right text-xs text-slate-600">
                      {num(h.kilos, 0)} kg
                      <span className="block text-slate-400">{h.procesos} proceso(s) · {h.productos} producto(s)</span>
                    </td>
                    {costos && <td className="cifra text-right">{clp(h.costo_por_kilo, 2)}</td>}
                    <td className="w-36">
                      <Entrada inputMode="decimal" placeholder="0" aria-label={`Kilos pendientes de ${h.especie}`} className="text-right" value={kilos[h.especie] ?? ""} onChange={(e) => { setKilos({ ...kilos, [h.especie]: e.target.value }); setResultado(null); }} onKeyDown={(e) => e.key === "Enter" && pendientes.length > 0 && calcular()} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <Boton className="no-imprimir mt-4 w-full" tam="lg" icono={<Calculator className="size-5" />} cargando={ocupado} disabled={!pendientes.length} onClick={calcular}>
            Calcular receta pendiente
          </Boton>
          <p className="mt-2 text-xs text-slate-500">
            Consumo por kilo = cantidad de producto consumida en los procesos de la especie ÷ kilos de todos esos procesos (base de costeo configurada). El aseo de línea y otras rebajas sin proceso no entran en el cálculo.
          </p>
        </Tarjeta>

        <div className="space-y-3">
          {error && <Aviso tipo="error">{error}</Aviso>}
          {!r && !error && <Aviso>Ingrese los kilos que faltan por procesar en cada especie y pulse <b>Calcular</b>.</Aviso>}
          {r && (
            <>
              {r.sin_historial.length > 0 && <Aviso tipo="alerta">Sin historial para: {r.sin_historial.join(", ")}. No se incluyen en el cálculo.</Aviso>}
              <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
                <Indicador titulo="Kilos pendientes" valor={`${num(r.resumen.kilos_pendientes, 0)} kg`} />
                <Indicador titulo="Productos necesarios" valor={r.resumen.productos} />
                <Indicador titulo="Con faltante" valor={r.resumen.con_faltante} tono={r.resumen.con_faltante ? "peligro" : "ok"} detalle={r.resumen.con_faltante ? "No alcanza el stock" : "El stock alcanza"} />
                <Indicador titulo="Costo estimado" valor={costos ? clp(r.resumen.costo_estimado) : "—"} detalle={costos && r.resumen.costo_por_kilo != null ? `${clp(r.resumen.costo_por_kilo, 2)} por kg (costo histórico)` : undefined} />
              </div>
              <div>
                <Pestanas valor={vista} onCambio={setVista} opciones={[{ valor: "productos", texto: "2. Receta total y stock" }, { valor: "detalle", texto: "Detalle por especie", contador: r.detalle.length }]} />
                <Tarjeta sinRelleno>
                  {vista === "productos" ? (
                    <Tabla
                      claveFila="producto_id"
                      filas={r.productos}
                      columnas={[
                        { clave: "producto", titulo: "Producto", render: (x) => <><Link href={`/productos/detalle/?id=${x.producto_id}`} className="font-medium text-slate-900 hover:underline">{x.producto}</Link><span className="block text-xs text-slate-500">{x.producto_codigo} · {x.subfamilia}</span></> },
                        { clave: "cantidad_requerida", titulo: "Receta necesaria", alinear: "derecha", render: (x) => <b>{num(x.cantidad_requerida)} {x.unidad}</b> },
                        { clave: "stock_disponible", titulo: "Disponible", alinear: "derecha", render: (x) => <>{num(x.stock_disponible)}{x.stock_reservado > 0 && <span className="block text-xs text-amber-700">{num(x.stock_reservado)} reservado</span>}</> },
                        { clave: "cobertura", titulo: "Cobertura", render: (x) => (
                          <div className="w-28" title={`${num(x.cobertura * 100, 0)} % de lo necesario`}>
                            <div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className={cx("h-full rounded-full", x.alcanza ? "bg-emerald-500" : x.cobertura >= 0.5 ? "bg-amber-500" : "bg-rose-500")} style={{ width: `${Math.max(3, x.cobertura * 100)}%` }} /></div>
                            <span className="cifra text-xs text-slate-500">{num(x.cobertura * 100, 0)} %</span>
                          </div>
                        ) },
                        { clave: "faltante", titulo: "Falta comprar", alinear: "derecha", render: (x) => (x.alcanza ? <Insignia tono="verde">Alcanza</Insignia> : <b className="text-rose-700">{num(x.faltante)} {x.unidad}</b>) },
                        ...(costos ? [{ clave: "costo_estimado", titulo: "Costo estimado", alinear: "derecha" as const, ocultarMovil: true, render: (x: any) => clp(x.costo_estimado) }] : []),
                      ]}
                    />
                  ) : (
                    <Tabla
                      claveFila="_k"
                      filas={r.detalle.map((x: any, i: number) => ({ ...x, _k: i }))}
                      columnas={[
                        { clave: "especie", titulo: "Especie", render: (x) => <span className="font-medium">{x.especie}</span> },
                        { clave: "producto", titulo: "Producto" },
                        { clave: "por_1000_kg", titulo: "Consumo histórico", alinear: "derecha", render: (x) => `${num(x.por_1000_kg, 3)} ${x.unidad} / 1.000 kg` },
                        { clave: "kilos_pendientes", titulo: "Kilos pendientes", alinear: "derecha", render: (x) => num(x.kilos_pendientes, 0) },
                        { clave: "cantidad", titulo: "Receta", alinear: "derecha", render: (x) => <b>{num(x.cantidad)} {x.unidad}</b> },
                        ...(costos ? [{ clave: "costo_estimado", titulo: "Costo estimado", alinear: "derecha" as const, render: (x: any) => clp(x.costo_estimado) }] : []),
                      ]}
                    />
                  )}
                </Tarjeta>
              </div>
              <p className="text-xs text-slate-500">
                Base del cálculo: {r.base.map((b: any) => `${b.especie} (${b.procesos} procesos, ${num(b.kilos_historicos, 0)} kg)`).join(" · ")}. Es una estimación a partir del promedio histórico; el consumo real se registra al escanear.
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
