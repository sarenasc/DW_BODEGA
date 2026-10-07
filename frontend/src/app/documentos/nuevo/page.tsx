"use client";

import { Plus, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { SelectorExistencia, SelectorProceso, SelectorProducto } from "@/components/Selectores";
import { Aviso, Boton, Campo, Cargando, Encabezado, Entrada, Insignia, Selector, Tarjeta } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, etiqueta, hoyISO, num } from "@/lib/formato";
import { useDatos, useParametro } from "@/lib/sesion";

type Linea = { k: number; producto: any; existencia: any; info: any; unidades: { id: number; codigo: string; factor: number | null }[]; [campo: string]: any };
const TITULOS: Record<string, string> = { INGRESO: "Nuevo ingreso", SALIDA: "Nueva salida", TRASLADO: "Nuevo traslado", AJUSTE: "Nuevo ajuste de inventario" };
let siguiente = 1;
const nueva = (): Linea => ({ k: siguiente++, producto: null, existencia: null, info: null, unidades: [], cantidad: "", precio_unitario: "", unidad_id: "" });

export default function NuevoDocumento() {
  const clase = (useParametro("clase") ?? "INGRESO").toUpperCase();
  const editar = useParametro("id");
  const router = useRouter();
  const cat = useDatos("/catalogos");
  const [cab, setCab] = useState<Record<string, any>>({ tipo_documento: "FACTURA", fecha_documento: hoyISO() });
  const [lineas, setLineas] = useState<Linea[]>([nueva()]);
  const [proceso, setProceso] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const ubic = useDatos(cab.bodega_id ? "/ubicaciones" : null, { bodega_id: cab.bodega_id, almacenable: true });
  const ubicDestino = useDatos(clase === "TRASLADO" && (cab.bodega_destino_id || cab.bodega_id) ? "/ubicaciones" : null, { bodega_id: cab.bodega_destino_id || cab.bodega_id, almacenable: true });
  const esIngreso = clase === "INGRESO";

  useEffect(() => {
    if (!cat.datos) return;
    setCab((c) => ({
      ...c,
      bodega_id: c.bodega_id ?? cat.datos.bodegas[0]?.id ?? "",
      motivo_id: c.motivo_id ?? cat.datos.motivos.find((m: any) => m.clase === (esIngreso ? "INGRESO" : "SALIDA") && m.codigo === (esIngreso ? "COMPRA" : "CONSUMO_INTERNO"))?.id ?? "",
    }));
  }, [cat.datos, esIngreso]);

  // Edicion de un borrador existente.
  useEffect(() => {
    if (!editar) return;
    api.get(`/documentos/${editar}`).then(async (d) => {
      setCab({ ...d, fecha: undefined });
      const cargadas: Linea[] = [];
      for (const x of d.detalles) {
        const l: Linea = { ...nueva(), ...x, cantidad: String(x.cantidad), precio_unitario: x.precio_unitario ?? "", campos_lote: x.campos_lote ?? {} };
        if (x.existencia_id) l.existencia = await api.get(`/existencias/${x.existencia_id}`);
        Object.assign(l, await datosProducto(await api.get(`/productos/${x.producto_id}`)), { unidad_id: x.unidad_id });
        cargadas.push(l);
      }
      setLineas(cargadas.length ? cargadas : [nueva()]);
    });
  }, [editar]);

  async function datosProducto(p: any) {
    const [info, det] = await Promise.all([api.get(`/productos/${p.id}/politica-ingreso`), api.get(`/productos/${p.id}/detalle`)]);
    const codigo = (id: number) => cat.datos?.unidades.find((u: any) => u.id === id)?.codigo ?? String(id);
    const unidades = [{ id: info.unidad_base_id, codigo: info.unidad_base, factor: 1 }, ...det.conversiones.filter((c: any) => c.unidad_destino_id === info.unidad_base_id).map((c: any) => ({ id: c.unidad_origen_id, codigo: codigo(c.unidad_origen_id), factor: Number(c.factor) }))];
    return { producto: p, info, unidades, unidad_id: info.unidad_compra_id };
  }
  const cambiar = (k: number, cambios: Record<string, any>) => setLineas((ls) => ls.map((l) => (l.k === k ? { ...l, ...cambios } : l)));
  async function elegirProducto(k: number, p: any) {
    if (!p) return cambiar(k, { producto: null, info: null, unidades: [] });
    const d = await datosProducto(p);
    const factor = d.unidades.find((u) => u.id === d.unidad_id)?.factor ?? 1;
    cambiar(k, { ...d, precio_unitario: d.info.costo_referencial != null ? String(Math.round(d.info.costo_referencial * factor * 100) / 100) : "" });
  }

  const total = lineas.reduce((s, l) => s + (Number(l.cantidad) || 0) * (Number(l.precio_unitario) || 0), 0);

  async function guardar(confirmar: boolean) {
    setError(null);
    setOcupado(true);
    try {
      const detalles = lineas
        .filter((l) => (esIngreso ? l.producto : l.existencia))
        .map((l) => ({
          producto_id: l.producto?.id ?? null,
          existencia_id: l.existencia?.id ?? null,
          cantidad: Number(String(l.cantidad).replace(",", ".")),
          unidad_id: l.unidad_id ? Number(l.unidad_id) : null,
          precio_unitario: l.precio_unitario !== "" ? Number(l.precio_unitario) : null,
          lote_manual: l.lote_manual || null,
          campos_lote: l.campos_lote && Object.keys(l.campos_lote).length ? l.campos_lote : null,
          referencia_externa: l.referencia_externa || null,
          fecha_fabricacion: l.fecha_fabricacion || null,
          fecha_vencimiento: l.fecha_vencimiento || null,
          ubicacion_id: l.ubicacion_id ? Number(l.ubicacion_id) : null,
          ubicacion_destino_id: l.ubicacion_destino_id ? Number(l.ubicacion_destino_id) : null,
          bultos: l.bultos ? Number(l.bultos) : null,
          observaciones: l.observaciones || null,
        }));
      if (!detalles.length) throw new Error("Agregue al menos una línea.");
      const cuerpo = {
        clase,
        motivo_id: clase === "INGRESO" || clase === "SALIDA" ? Number(cab.motivo_id) || null : null,
        tipo_documento: cab.tipo_documento || null,
        numero_documento: cab.numero_documento || null,
        fecha_documento: cab.fecha_documento || null,
        proveedor_id: cab.proveedor_id ? Number(cab.proveedor_id) : null,
        bodega_id: Number(cab.bodega_id),
        bodega_destino_id: cab.bodega_destino_id ? Number(cab.bodega_destino_id) : null,
        proceso_id: proceso?.id ?? cab.proceso_id ?? null,
        observaciones: cab.observaciones || null,
        detalles,
        confirmar,
      };
      const r = editar ? await api.put(`/documentos/${editar}`, cuerpo) : await api.post("/documentos", cuerpo);
      router.push(`/documentos/detalle/?id=${r.id}`);
    } catch (e: any) {
      setError(e.message);
      setOcupado(false);
    }
  }

  if (!cat.datos) return <Cargando />;
  const motivos = cat.datos.motivos.filter((m: any) => m.clase === (esIngreso ? "INGRESO" : "SALIDA"));
  const motivo = motivos.find((m: any) => String(m.id) === String(cab.motivo_id));
  const bodegas = cat.datos.bodegas.map((b: any) => ({ valor: b.id, texto: b.nombre }));
  const opUbic = (l: any[] | null) => (l ?? []).map((u: any) => ({ valor: u.id, texto: u.codigo_completo }));

  return (
    <>
      <Encabezado titulo={editar ? `Editar ${cab.numero ?? "borrador"}` : (TITULOS[clase] ?? "Nuevo documento")} descripcion={esIngreso ? "Cada ingreso guarda cantidad, valor unitario y total. Al confirmar se generan el lote interno, las existencias y sus QR." : "El documento queda en borrador hasta confirmarlo; al confirmar genera movimientos inmutables."} volver="/documentos/" />
      {error && <Aviso tipo="error" className="mb-3">{error}</Aviso>}
      <Tarjeta titulo="Documento" className="mb-3">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Campo etiqueta={clase === "TRASLADO" ? "Bodega de origen" : "Bodega"} requerido>
            <Selector value={cab.bodega_id ?? ""} onChange={(e) => setCab({ ...cab, bodega_id: e.target.value })} opciones={bodegas} disabled={!!editar} />
          </Campo>
          {clase === "TRASLADO" && (
            <Campo etiqueta="Bodega de destino">
              <Selector vacio="Misma bodega (cambio de ubicación)" value={cab.bodega_destino_id ?? ""} onChange={(e) => setCab({ ...cab, bodega_destino_id: e.target.value })} opciones={bodegas} />
            </Campo>
          )}
          {(esIngreso || clase === "SALIDA") && (
            <Campo etiqueta={esIngreso ? "Tipo de ingreso" : "Tipo de salida"} requerido>
              <Selector value={cab.motivo_id ?? ""} onChange={(e) => setCab({ ...cab, motivo_id: e.target.value })} opciones={motivos.map((m: any) => ({ valor: m.id, texto: m.nombre }))} />
            </Campo>
          )}
          {(esIngreso || clase === "SALIDA") && (
            <>
              <Campo etiqueta="Tipo de documento">
                <Selector vacio="—" value={cab.tipo_documento ?? ""} onChange={(e) => setCab({ ...cab, tipo_documento: e.target.value })} opciones={cat.datos.enumeraciones.tipos_documento.map((t: string) => ({ valor: t, texto: etiqueta(t) }))} />
              </Campo>
              <Campo etiqueta="Número de documento" requerido={motivo?.requiere_documento}>
                <Entrada value={cab.numero_documento ?? ""} onChange={(e) => setCab({ ...cab, numero_documento: e.target.value })} />
              </Campo>
              <Campo etiqueta="Fecha del documento">
                <Entrada type="date" max={hoyISO()} value={cab.fecha_documento ?? ""} onChange={(e) => setCab({ ...cab, fecha_documento: e.target.value })} />
              </Campo>
            </>
          )}
          {esIngreso && (
            <Campo etiqueta="Proveedor">
              <Selector vacio="—" value={cab.proveedor_id ?? ""} onChange={(e) => setCab({ ...cab, proveedor_id: e.target.value })} opciones={cat.datos.proveedores.map((p: any) => ({ valor: p.id, texto: p.nombre }))} />
            </Campo>
          )}
          {clase === "SALIDA" && (
            <Campo etiqueta="Proceso" requerido={motivo?.requiere_proceso} className="sm:col-span-2">
              <SelectorProceso valor={proceso} onCambio={setProceso} />
            </Campo>
          )}
          <Campo etiqueta={clase === "AJUSTE" ? "Motivo del ajuste" : "Observaciones"} requerido={clase === "AJUSTE"} className="sm:col-span-2">
            <Entrada value={cab.observaciones ?? ""} onChange={(e) => setCab({ ...cab, observaciones: e.target.value })} />
          </Campo>
        </div>
      </Tarjeta>

      <div className="space-y-3">
        {lineas.map((l, i) => {
          const pol = l.info?.politica;
          const factor = l.unidades.find((u) => String(u.id) === String(l.unidad_id))?.factor ?? null;
          const cant = Number(String(l.cantidad).replace(",", ".")) || 0;
          const precio = Number(l.precio_unitario) || 0;
          const base = factor ? cant * factor : null;
          const muestraBultos = pol && (pol.granularidad === "UNIDAD_LOGISTICA" || (pol.granularidad === "POR_ENVASE" && factor === 1));
          const qrs = !pol ? 0 : pol.granularidad === "POR_ENVASE" ? (Number(l.bultos) || (factor !== 1 && Number.isInteger(cant) ? cant : 1)) : pol.granularidad === "UNIDAD_LOGISTICA" ? Number(l.bultos) || 1 : 1;
          return (
            <Tarjeta key={l.k} titulo={`Línea ${i + 1}`} accion={lineas.length > 1 && <button aria-label="Quitar línea" onClick={() => setLineas((ls) => ls.filter((x) => x.k !== l.k))} className="rounded p-1 text-rose-600 hover:bg-rose-50"><Trash2 className="size-4" /></button>}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Campo etiqueta={esIngreso ? "Producto" : "Existencia"} requerido className="sm:col-span-2">
                  {esIngreso ? <SelectorProducto valor={l.producto} onCambio={(p) => elegirProducto(l.k, p)} /> : <SelectorExistencia valor={l.existencia} bodegaId={cab.bodega_id} onCambio={(e) => cambiar(l.k, { existencia: e, producto: e ? { id: e.producto_id } : null, unidades: e ? [{ id: e.unidad_id, codigo: e.unidad, factor: 1 }] : [], unidad_id: e?.unidad_id ?? "" })} />}
                </Campo>
                <Campo etiqueta={clase === "AJUSTE" ? "Diferencia (+ / −)" : "Cantidad"} requerido ayuda={clase === "AJUSTE" ? "Negativa para rebajar, positiva para aumentar." : l.existencia ? `Stock: ${num(l.existencia.cantidad_fisica)} ${l.existencia.unidad}` : undefined}>
                  <Entrada inputMode="decimal" value={l.cantidad} onChange={(e) => cambiar(l.k, { cantidad: e.target.value })} />
                </Campo>
                <Campo etiqueta="Unidad">
                  <Selector value={l.unidad_id ?? ""} onChange={(e) => cambiar(l.k, { unidad_id: e.target.value })} opciones={l.unidades.map((u) => ({ valor: u.id, texto: u.codigo }))} disabled={!l.unidades.length} />
                </Campo>
                {esIngreso && l.info && (
                  <>
                    <Campo etiqueta={`Valor unitario (por ${l.unidades.find((u) => String(u.id) === String(l.unidad_id))?.codigo ?? "unidad"})`} requerido>
                      <Entrada inputMode="decimal" value={l.precio_unitario} onChange={(e) => cambiar(l.k, { precio_unitario: e.target.value })} />
                    </Campo>
                    <Campo etiqueta="Ubicación" requerido={pol.requiere_ubicacion}>
                      <Selector vacio="Sin ubicación (asignar después)" value={l.ubicacion_id ?? ""} onChange={(e) => cambiar(l.k, { ubicacion_id: e.target.value })} opciones={opUbic(ubic.datos)} />
                    </Campo>
                    {pol.usa_lote && l.info.lote.requiere_codigo && (
                      <Campo etiqueta="Lote interno" requerido ayuda="Este producto no tiene plantilla automática.">
                        <Entrada value={l.lote_manual ?? ""} onChange={(e) => cambiar(l.k, { lote_manual: e.target.value.toUpperCase() })} />
                      </Campo>
                    )}
                    {pol.usa_lote && l.info.lote.modo === "SEMIAUTOMATICO" && (
                      <Campo etiqueta="Lote interno (opcional)" ayuda="Vacío = generar con la plantilla.">
                        <Entrada value={l.lote_manual ?? ""} onChange={(e) => cambiar(l.k, { lote_manual: e.target.value.toUpperCase() })} />
                      </Campo>
                    )}
                    {l.info.lote.campos_manuales.map((c: any) => {
                      const clave = c.clave ?? c.etiqueta ?? "manual";
                      return (
                        <Campo key={clave} etiqueta={`Lote: ${c.etiqueta ?? clave}`} requerido={c.obligatorio ?? true}>
                          <Entrada value={l.campos_lote?.[clave] ?? ""} onChange={(e) => cambiar(l.k, { campos_lote: { ...l.campos_lote, [clave]: e.target.value } })} />
                        </Campo>
                      );
                    })}
                    {pol.usa_vencimiento && (
                      <>
                        <Campo etiqueta="Fecha de fabricación" ayuda={pol.vida_util_meses ? `Vida útil: ${pol.vida_util_meses} meses.` : undefined}>
                          <Entrada type="date" value={l.fecha_fabricacion ?? ""} onChange={(e) => cambiar(l.k, { fecha_fabricacion: e.target.value })} />
                        </Campo>
                        <Campo etiqueta="Fecha de vencimiento" requerido={!pol.vida_util_meses}>
                          <Entrada type="date" value={l.fecha_vencimiento ?? ""} onChange={(e) => cambiar(l.k, { fecha_vencimiento: e.target.value })} />
                        </Campo>
                      </>
                    )}
                    {muestraBultos && (
                      <Campo etiqueta={pol.granularidad === "UNIDAD_LOGISTICA" ? "Unidades logísticas (pallets)" : "Cantidad de envases"} ayuda="Se genera un QR por cada uno.">
                        <Entrada type="number" min={1} max={500} value={l.bultos ?? ""} onChange={(e) => cambiar(l.k, { bultos: e.target.value })} />
                      </Campo>
                    )}
                    <Campo etiqueta="Referencia externa (opcional)" ayuda="Dato documental; no reemplaza al lote interno.">
                      <Entrada value={l.referencia_externa ?? ""} onChange={(e) => cambiar(l.k, { referencia_externa: e.target.value })} />
                    </Campo>
                  </>
                )}
                {clase === "TRASLADO" && (
                  <Campo etiqueta="Ubicación de destino" className="sm:col-span-2">
                    <Selector vacio="Sin ubicación" value={l.ubicacion_destino_id ?? ""} onChange={(e) => cambiar(l.k, { ubicacion_destino_id: e.target.value })} opciones={opUbic(ubicDestino.datos)} />
                  </Campo>
                )}
              </div>
              {esIngreso && l.info && cant > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {base !== null && <span className="cifra">= <b>{num(base)} {l.info.unidad_base}</b></span>}
                  {base !== null && precio > 0 && <span className="cifra">· costo <b>{clp(precio / (factor ?? 1), 2)}</b> por {l.info.unidad_base}</span>}
                  {precio > 0 && <span className="cifra">· valor ingreso <b>{clp(cant * precio)}</b></span>}
                  <span className="ml-auto flex flex-wrap gap-1.5">
                    <Insignia tono="azul">{qrs} existencia{qrs === 1 ? "" : "s"} / QR</Insignia>
                    {pol.usa_lote ? <Insignia tono="verde">{l.info.lote.plantilla ? `Lote: ${l.info.lote.plantilla}` : "Lote manual"}</Insignia> : <Insignia>Sin lote</Insignia>}
                    <Insignia tono="violeta">{pol.estrategia_salida.replace("_", "+")}</Insignia>
                  </span>
                </div>
              )}
            </Tarjeta>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <Boton variante="secundario" icono={<Plus className="size-4" />} onClick={() => setLineas((ls) => [...ls, nueva()])}>
          Agregar línea
        </Boton>
        <div className="flex flex-wrap items-center gap-3">
          {esIngreso && <span className="text-sm text-slate-600">Total: <b className="cifra text-lg text-slate-900">{clp(total)}</b></span>}
          <Boton variante="secundario" cargando={ocupado} onClick={() => guardar(false)}>
            Guardar borrador
          </Boton>
          <Boton cargando={ocupado} onClick={() => guardar(true)}>
            Confirmar {esIngreso ? "ingreso" : clase.toLowerCase()}
          </Boton>
        </div>
      </div>
    </>
  );
}
