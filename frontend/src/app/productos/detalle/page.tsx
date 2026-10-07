"use client";

import { GitBranch, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Adjuntos } from "@/components/Adjuntos";
import { Aviso, Boton, Campo, Cargando, Dato, Encabezado, EnlaceBoton, Entrada, Estado, Insignia, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, etiqueta, fecha, num } from "@/lib/formato";
import { NOMBRE_POLITICA } from "@/lib/politica";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function DetalleProducto() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const { datos: p, error, recargar } = useDatos(id ? `/productos/${id}/detalle` : null);
  const cat = useDatos("/catalogos");
  const stock = useDatos(id && puede("inventario:ver") ? "/stock" : null, { producto_id: id, agrupar: "lote" });
  const plantillas = useDatos(puede("lotes:ver") ? "/plantillas-lotes" : null);
  const [conv, setConv] = useState({ unidad_origen_id: "", factor: "" });
  const { ejecutar, ocupado } = useAccion();
  const editable = puede("catalogo:administrar");

  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!p) return <Cargando />;
  const unidades: any[] = cat.datos?.unidades ?? [];
  const cod = (uid: number) => unidades.find((u) => u.id === uid)?.codigo ?? uid;
  const pol = p.politica;
  const valorPolitica = (k: string) => {
    const v = pol[k];
    if (v === null || v === undefined) return "—";
    if (typeof v === "boolean") return v ? "Sí" : "No";
    if (k === "plantilla_lote_id") return plantillas.datos?.find((x: any) => x.id === v)?.nombre ?? `#${v}`;
    return typeof v === "string" ? etiqueta(v) : String(v);
  };

  const agregar = () =>
    ejecutar(async () => {
      await api.post("/conversiones", { producto_id: p.id, unidad_origen_id: Number(conv.unidad_origen_id), unidad_destino_id: p.unidad_base_id, factor: Number(conv.factor) });
      setConv({ unidad_origen_id: "", factor: "" });
      recargar();
    }, "Conversión agregada");

  return (
    <>
      <Encabezado titulo={p.nombre} descripcion={`${p.codigo} · ${p.familia} › ${p.subfamilia}`} volver="/productos/">
        <Estado valor={p.activo ? "ACTIVO" : "ANULADO"} />
        {puede("trazabilidad:ver") && (
          <EnlaceBoton href={`/trazabilidad/?producto=${p.id}`} icono={<GitBranch className="size-4" />}>
            Trazabilidad
          </EnlaceBoton>
        )}
      </Encabezado>
      <div className="grid gap-3 lg:grid-cols-3">
        <Tarjeta titulo="Ficha" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Dato etiqueta="Código interno">{p.codigo}</Dato>
            <Dato etiqueta="Código externo">{p.codigo_externo}</Dato>
            <Dato etiqueta="Marca">{p.marca}</Dato>
            <Dato etiqueta="Categoría">{p.categoria}</Dato>
            <Dato etiqueta="Unidad principal">{p.unidad_base}</Dato>
            <Dato etiqueta="Unidad de compra">{p.unidad_compra ?? p.unidad_base}</Dato>
            <Dato etiqueta="Unidad de consumo">{p.unidad_consumo ?? p.unidad_base}</Dato>
            <Dato etiqueta="Código de barras">{p.codigo_barras}</Dato>
            <Dato etiqueta="Stock mínimo">{num(p.stock_minimo)}</Dato>
            <Dato etiqueta="Stock crítico">{num(p.stock_critico)}</Dato>
            <Dato etiqueta="Punto reposición">{num(p.punto_reposicion)}</Dato>
            <Dato etiqueta="Stock máximo">{num(p.stock_maximo)}</Dato>
            {puede("costos:ver") && <Dato etiqueta="Costo referencial">{clp(p.costo_referencial, 2)} / {p.unidad_base}</Dato>}
          </dl>
          {p.descripcion && <p className="mt-4 border-t border-slate-100 pt-3 text-sm text-slate-600">{p.descripcion}</p>}
        </Tarjeta>
        <Tarjeta titulo="Conversión de unidades">
          <ul className="space-y-1.5">
            {p.conversiones.length === 0 && <li className="text-sm text-slate-500">Sin conversiones propias: se compra y consume en {p.unidad_base}.</li>}
            {p.conversiones.map((c: any) => (
              <li key={c.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2 text-sm">
                <span className="cifra">
                  1 {cod(c.unidad_origen_id)} = <b>{num(c.factor, 6)}</b> {cod(c.unidad_destino_id)}
                </span>
                {editable && (
                  <span className="flex items-center gap-1">
                    {p.unidad_compra_id !== c.unidad_origen_id && (
                      <Boton tam="sm" variante="fantasma" onClick={() => ejecutar(async () => { await api.put(`/productos/${p.id}`, { unidad_compra_id: c.unidad_origen_id }); recargar(); }, "Unidad de compra actualizada")}>
                        Usar para compra
                      </Boton>
                    )}
                    {p.unidad_compra_id === c.unidad_origen_id && <Insignia tono="verde">Compra</Insignia>}
                    <button aria-label="Eliminar conversión" onClick={() => ejecutar(async () => { await api.del(`/conversiones/${c.id}`); recargar(); })} className="rounded p-1 text-rose-600 hover:bg-rose-50">
                      <Trash2 className="size-4" />
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
          {editable && (
            <div className="mt-3 grid grid-cols-[1fr_1fr_auto] items-end gap-2 border-t border-slate-100 pt-3">
              <Campo etiqueta="1 unidad de">
                <Selector vacio="Unidad…" value={conv.unidad_origen_id} onChange={(e) => setConv({ ...conv, unidad_origen_id: e.target.value })} opciones={unidades.filter((u) => u.id !== p.unidad_base_id).map((u) => ({ valor: u.id, texto: u.codigo }))} />
              </Campo>
              <Campo etiqueta={`= cuántos ${p.unidad_base}`}>
                <Entrada inputMode="decimal" value={conv.factor} onChange={(e) => setConv({ ...conv, factor: e.target.value })} />
              </Campo>
              <Boton onClick={agregar} cargando={ocupado} disabled={!conv.unidad_origen_id || !(Number(conv.factor) > 0)} aria-label="Agregar conversión">
                <Plus className="size-4" />
              </Boton>
            </div>
          )}
        </Tarjeta>
        <Tarjeta titulo="Configuración efectiva (con herencia)" className="lg:col-span-2" sinRelleno>
          <Tabla
            claveFila="k"
            filas={Object.keys(NOMBRE_POLITICA).map((k) => ({ k, origen: pol.origen[k] }))}
            columnas={[
              { clave: "k", titulo: "Parámetro", render: (f) => NOMBRE_POLITICA[f.k] },
              { clave: "v", titulo: "Valor", render: (f) => <span className="font-medium">{valorPolitica(f.k)}</span> },
              { clave: "origen", titulo: "Definido en", render: (f) => <Insignia tono={f.origen === "PRODUCTO" ? "verde" : f.origen === "GLOBAL" ? "gris" : "azul"}>{etiqueta(f.origen)}</Insignia> },
            ]}
          />
        </Tarjeta>
        <Adjuntos entidad="producto" id={p.id} titulo="Ficha técnica y hoja de seguridad" />
        {stock.datos && (
          <Tarjeta titulo="Stock por lote" className="lg:col-span-3" sinRelleno>
            <Tabla
              claveFila="lote_id"
              vacio="Sin stock."
              filas={stock.datos.map((s: any, i: number) => ({ ...s, lote_id: `${s.lote_id}-${s.bodega_id}-${i}`, lid: s.lote_id }))}
              columnas={[
                { clave: "lote", titulo: "Lote", render: (s) => (s.lid ? <Link className="font-medium hover:underline" href={`/lotes/detalle/?id=${s.lid}`}>{s.lote}</Link> : "Sin lote") },
                { clave: "bodega", titulo: "Bodega" },
                { clave: "lote_estado", titulo: "Estado", render: (s) => <Estado valor={s.lote_estado} /> },
                { clave: "fecha_vencimiento", titulo: "Vence", render: (s) => fecha(s.fecha_vencimiento) },
                { clave: "stock_fisico", titulo: "Físico", alinear: "derecha", render: (s) => num(s.stock_fisico) },
                { clave: "stock_reservado", titulo: "Reservado", alinear: "derecha", render: (s) => num(s.stock_reservado) },
                { clave: "stock_disponible", titulo: "Disponible", alinear: "derecha", render: (s) => <b>{num(s.stock_disponible)} {s.unidad}</b> },
                ...(puede("costos:ver") ? [{ clave: "valor_inventario", titulo: "Valor", alinear: "derecha" as const, render: (s: any) => clp(s.valor_inventario) }] : []),
              ]}
            />
          </Tarjeta>
        )}
      </div>
    </>
  );
}
