"use client";

import { AlertTriangle, Bell, Boxes, CalendarClock, Clock, HandCoins, PackageMinus, RefreshCw, Scale, TrendingDown, Wallet } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { BarrasLista, Columnas, SerieDiaria } from "@/components/Graficos";
import { Aviso, Boton, Cargando, Encabezado, Entrada, Indicador, Insignia, Selector, Tabla, Tarjeta } from "@/components/ui";
import { clp, clpCorto, fecha, fechaHora, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Dashboard() {
  const { puede } = useSesion();
  const costos = puede("costos:ver");
  const [f, setF] = useState<Record<string, string>>({});
  const cat = useDatos("/catalogos");
  const val = useDatos(puede("procesos:ver") ? "/procesos/valores" : null);
  const { datos: d, cargando, error, recargar } = useDatos("/dashboard", f);
  const fijar = (k: string, v: string) => setF((a) => ({ ...a, [k]: v }));
  const opciones = (lista: any[] | undefined) => (lista ?? []).map((x: any) => ({ valor: x.id, texto: x.nombre }));
  const texto = (lista: string[] | undefined) => (lista ?? []).map((x) => ({ valor: x, texto: x }));

  return (
    <>
      <Encabezado titulo="Dashboard" descripcion={d ? `Consumos y costos del ${fecha(d.periodo.desde)} al ${fecha(d.periodo.hasta)} · inventario a la fecha` : undefined}>
        <Boton variante="secundario" icono={<RefreshCw className="size-4" />} onClick={recargar}>
          Actualizar
        </Boton>
      </Encabezado>

      <div className="no-imprimir mb-4 grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-white p-3 sm:grid-cols-4 xl:grid-cols-8">
        <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => fijar("desde", e.target.value)} />
        <Entrada type="date" aria-label="Hasta" value={f.hasta ?? ""} onChange={(e) => fijar("hasta", e.target.value)} />
        <Selector aria-label="Bodega" vacio="Todas las bodegas" value={f.bodega_id ?? ""} onChange={(e) => fijar("bodega_id", e.target.value)} opciones={opciones(cat.datos?.bodegas)} />
        <Selector aria-label="Familia" vacio="Todas las familias" value={f.familia_id ?? ""} onChange={(e) => setF((a) => ({ ...a, familia_id: e.target.value, subfamilia_id: "" }))} opciones={opciones(cat.datos?.familias)} />
        <Selector aria-label="Subfamilia" vacio="Todas las subfamilias" value={f.subfamilia_id ?? ""} onChange={(e) => fijar("subfamilia_id", e.target.value)} opciones={opciones(cat.datos?.subfamilias?.filter((s: any) => !f.familia_id || String(s.familia_id) === f.familia_id))} />
        <Selector aria-label="Temporada" vacio="Todas las temporadas" value={f.temporada_id ?? ""} onChange={(e) => fijar("temporada_id", e.target.value)} opciones={(cat.datos?.temporadas ?? []).map((t: any) => ({ valor: t.id, texto: t.codigo }))} />
        <Selector aria-label="Especie" vacio="Todas las especies" value={f.especie ?? ""} onChange={(e) => fijar("especie", e.target.value)} opciones={texto(val.datos?.especies)} />
        <Selector aria-label="Productor" vacio="Todos los productores" value={f.productor ?? ""} onChange={(e) => fijar("productor", e.target.value)} opciones={texto(val.datos?.productores)} />
      </div>

      {error && <Aviso tipo="error">{error}</Aviso>}
      {!d && cargando && <Cargando />}
      {d && (
        <div className={cargando ? "opacity-60 transition" : "transition"}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Indicador titulo="Valor total inventario" valor={costos ? clpCorto(d.valor_total_inventario) : "—"} detalle={`${d.stock_total.existencias} existencias · ${d.stock_total.productos} productos`} icono={<Wallet className="size-4" />} href="/stock/" />
            <Indicador titulo="Consumo del día" valor={costos ? clp(d.consumo_del_dia.costo) : `${d.consumo_del_dia.movimientos} mov.`} detalle={costos ? `${d.consumo_del_dia.movimientos} movimientos · semana ${clpCorto(d.consumo_semanal.costo)}` : "movimientos hoy"} icono={<PackageMinus className="size-4" />} href="/movimientos/" />
            <Indicador
              titulo="Costo por kilo"
              valor={costos && d.costo_por_kilo?.costo_por_kilo != null ? clp(d.costo_por_kilo.costo_por_kilo, 2) : "—"}
              detalle={costos && d.costo_por_kilo ? `${num(d.costo_por_kilo.kilos, 0)} kg · kilos ${d.costo_por_kilo.estado_kilos.toLowerCase()}s` : "requiere permiso de costos"}
              icono={<Scale className="size-4" />}
              href="/costos/"
            />
            <Indicador titulo="Alertas abiertas" valor={d.alertas?.abiertas ?? "—"} tono={d.alertas?.criticas ? "peligro" : d.alertas?.abiertas ? "alerta" : "ok"} detalle={d.alertas ? `${d.alertas.nuevas} nuevas · ${d.alertas.criticas} críticas` : undefined} icono={<Bell className="size-4" />} href="/alertas/" />
            <Indicador titulo="Stock bajo mínimo" valor={d.stock_bajo_minimo.cantidad} tono={d.stock_bajo_minimo.cantidad ? "alerta" : "ok"} detalle="productos" icono={<TrendingDown className="size-4" />} href="/stock/?bajo=1" />
            <Indicador titulo="Próximos a vencer" valor={d.proximos_a_vencer.cantidad} tono={d.proximos_a_vencer.cantidad ? "alerta" : "ok"} detalle={costos ? `lotes · ${clpCorto(d.proximos_a_vencer.valor_inventario)}` : "lotes en 30 días"} icono={<CalendarClock className="size-4" />} href="/lotes/?vence=30" />
            <Indicador titulo="Vencidos" valor={d.vencidos.cantidad} tono={d.vencidos.cantidad ? "peligro" : "ok"} detalle={costos ? `lotes con stock · ${clpCorto(d.vencidos.valor_inventario)}` : "lotes con stock"} icono={<AlertTriangle className="size-4" />} href="/lotes/?estado=VENCIDO" />
            <Indicador titulo={`Stock antiguo (+${d.stock_antiguo.dias} días)`} valor={d.stock_antiguo.existencias} tono={d.stock_antiguo.existencias ? "alerta" : "ok"} detalle={costos ? `existencias · ${clpCorto(d.stock_antiguo.valor_inventario)}` : "existencias"} icono={<Clock className="size-4" />} href="/reportes/?r=antiguedad" />
          </div>

          {d.alertas && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm">
              <span className="font-semibold text-slate-800">Alertas:</span>
              {[
                ["Stock bajo", d.alertas.stock_bajo],
                ["Próximos a vencer", d.alertas.proximos_a_vencer],
                ["Vencidos", d.alertas.vencidos],
                ["Fuera de FIFO", d.alertas.fuera_de_fifo],
                ["Reservas vencidas", d.alertas.reservas_vencidas],
                ["Procesos sin sincronizar", d.alertas.procesos_sin_sincronizar],
              ].map(([t, n]) => (
                <Insignia key={t as string} tono={n ? "ambar" : "gris"}>
                  {t}: {n}
                </Insignia>
              ))}
              <Link href="/alertas/" className="ml-auto text-sm font-medium text-marca-700 hover:underline">
                Ver todas las alertas →
              </Link>
            </div>
          )}

          <div className="mt-3 grid gap-3 xl:grid-cols-3">
            {costos && (
              <Tarjeta titulo="Consumo diario valorizado" className="xl:col-span-2">
                <SerieDiaria datos={d.consumo_periodo.serie} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Productos más consumidos">
                <BarrasLista datos={d.productos_mas_consumidos.map((x: any) => ({ nombre: x.nombre, valor: x.costo }))} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Costo por especie" accion={<Link href="/costos/" className="text-xs font-medium text-marca-700 hover:underline">Analizar</Link>}>
                <BarrasLista datos={d.costo_por_especie.map((x: any) => ({ nombre: x.clave, valor: x.costo, detalle: x.costo_por_kilo != null ? `${clp(x.costo_por_kilo, 2)}/kg` : undefined }))} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Costo por proceso">
                <BarrasLista datos={d.costo_por_proceso.map((x: any) => ({ nombre: x.clave, valor: x.costo, detalle: x.costo_por_kilo != null ? `${clp(x.costo_por_kilo, 2)}/kg` : undefined }))} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Valor por bodega">
                <BarrasLista datos={d.valor_por_bodega.map((x: any) => ({ nombre: x.nombre, valor: x.valor }))} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Valor por familia">
                <BarrasLista datos={d.valor_por_familia.map((x: any) => ({ nombre: x.nombre, valor: x.valor }))} />
              </Tarjeta>
            )}
            {costos && (
              <Tarjeta titulo="Valor por subfamilia">
                <BarrasLista datos={d.valor_por_subfamilia.map((x: any) => ({ nombre: x.nombre, valor: x.valor }))} />
              </Tarjeta>
            )}
            <Tarjeta titulo="Antigüedad del inventario (días desde el ingreso)">
              <Columnas formato={costos ? "moneda" : "numero"} datos={d.antiguedad.rangos.map((r: any) => ({ nombre: r.rango, valor: costos ? r.valor_inventario : r.existencias, detalle: `${r.existencias} existencias` }))} />
              <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
                <div>
                  Edad promedio: <b className="text-slate-900">{num(d.antiguedad.edad_promedio_dias, 0)} días</b>
                </div>
                <div>
                  Fuera de FIFO: <b className="text-slate-900">{d.consumos_fuera_de_fifo}</b> en el período
                </div>
                {d.antiguedad.lote_mas_antiguo && (
                  <div className="col-span-2">
                    Más antiguo:{" "}
                    <Link className="font-medium text-marca-700 hover:underline" href={`/existencia/?id=${d.antiguedad.lote_mas_antiguo.existencia_id}`}>
                      {d.antiguedad.lote_mas_antiguo.producto} · {d.antiguedad.lote_mas_antiguo.lote ?? d.antiguedad.lote_mas_antiguo.codigo_publico}
                    </Link>{" "}
                    ({d.antiguedad.lote_mas_antiguo.dias} días)
                  </div>
                )}
              </dl>
            </Tarjeta>
            <Tarjeta titulo="Stock bajo mínimo" sinRelleno>
              <Tabla
                claveFila="producto_id"
                vacio="Ningún producto bajo su mínimo."
                filas={d.stock_bajo_minimo.productos}
                columnas={[
                  { clave: "producto", titulo: "Producto", render: (x) => <Link className="font-medium hover:underline" href={`/productos/detalle/?id=${x.producto_id}`}>{x.producto}</Link> },
                  { clave: "stock", titulo: "Stock", alinear: "derecha", render: (x) => `${num(x.stock)} ${x.unidad}` },
                  { clave: "minimo", titulo: "Mínimo", alinear: "derecha", render: (x) => num(x.minimo) },
                  { clave: "nivel", titulo: "Nivel", render: (x) => <Insignia tono={x.nivel === "BAJO" ? "ambar" : "rojo"}>{x.nivel}</Insignia> },
                ]}
              />
            </Tarjeta>
            <Tarjeta titulo="Próximos a vencer" sinRelleno>
              <Tabla
                claveFila="lote_id"
                vacio="Sin lotes por vencer en 30 días."
                filas={d.proximos_a_vencer.lotes}
                columnas={[
                  { clave: "lote", titulo: "Lote", render: (x) => <Link className="font-medium hover:underline" href={`/lotes/detalle/?id=${x.lote_id}`}>{x.lote}</Link> },
                  { clave: "producto", titulo: "Producto", ocultarMovil: true },
                  { clave: "fecha_vencimiento", titulo: "Vence", render: (x) => fecha(x.fecha_vencimiento) },
                  { clave: "dias", titulo: "Días", alinear: "derecha" },
                ]}
              />
            </Tarjeta>
          </div>

          <Tarjeta titulo="Últimos movimientos" className="mt-3" sinRelleno accion={<Link href="/movimientos/" className="text-xs font-medium text-marca-700 hover:underline">Ver todos</Link>}>
            <Tabla
              filas={d.ultimos_movimientos}
              columnas={[
                { clave: "fecha", titulo: "Fecha", render: (m) => fechaHora(m.fecha) },
                { clave: "tipo", titulo: "Tipo", render: (m) => <Insignia tono={m.cantidad < 0 ? "azul" : "verde"}>{m.tipo}</Insignia> },
                { clave: "producto", titulo: "Producto" },
                { clave: "lote", titulo: "Lote", ocultarMovil: true },
                { clave: "cantidad", titulo: "Cantidad", alinear: "derecha", render: (m) => `${num(m.cantidad)} ${m.unidad}` },
                ...(costos ? [{ clave: "costo_total", titulo: "Costo", alinear: "derecha" as const, ocultarMovil: true, render: (m: any) => clp(m.costo_total) }] : []),
                { clave: "proceso", titulo: "Proceso", ocultarMovil: true },
                { clave: "usuario", titulo: "Usuario", ocultarMovil: true },
              ]}
            />
          </Tarjeta>
          <p className="mt-3 flex items-center gap-1.5 text-xs text-slate-500">
            <Boxes className="size-3.5" /> Stock reservado: {num(d.stock_total.reservado)} (unidades base) · <HandCoins className="size-3.5" /> Los costos corresponden al costo real de cada existencia consumida.
          </p>
        </div>
      )}
    </>
  );
}
