"use client";

import { PackagePlus, Settings2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";
import { SelectorExistencia } from "./Selectores";
import { Aviso, Boton, Campo, Entrada, useAviso } from "./ui";

/**
 * Lo que hay en una ubicacion (o en un rack completo): productos, lotes, cantidad, vencimiento, valor y capacidad libre.
 * Si la ubicacion admite stock y el usuario puede trasladar, permite guardar existencias en ella.
 */
export function ContenidoUbicacion({ datos, onCambio }: { datos: any; onCambio?: () => void }) {
  const { puede } = useSesion();
  const avisar = useAviso();
  const u = datos.ubicacion;
  const puedeGuardar = !!onCambio && puede("traslados:crear") && u.almacenable && u.activo;
  const [abierto, setAbierto] = useState(false);
  const [existencia, setExistencia] = useState<any>(null);
  const [cantidad, setCantidad] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  // Sugerencias: lo que esta en la bodega sin ubicacion asignada (recien ingresado).
  const sinUbicar = useDatos(abierto ? "/existencias" : null, { bodega_id: u.bodega_id, sin_ubicacion: true, con_stock: true, tam: 8 });

  const elegir = (e: any) => {
    setExistencia(e);
    setCantidad(e ? String(e.cantidad_fisica).replace(".", ",") : "");
    setError(null);
  };

  async function guardar() {
    const q = Number(cantidad.replace(",", "."));
    if (!existencia || !(q > 0)) return;
    setOcupado(true);
    setError(null);
    try {
      // Un traslado deja el movimiento registrado. Si la cantidad es parcial nace una existencia nueva con su propio QR.
      await api.post("/documentos", {
        clase: "TRASLADO",
        bodega_id: existencia.bodega_id,
        bodega_destino_id: u.bodega_id,
        observaciones: `Guardado en ${u.codigo_completo} desde el plano`,
        confirmar: true,
        detalles: [{ existencia_id: existencia.id, cantidad: q, ubicacion_destino_id: u.id }],
      });
      avisar("exito", `${existencia.producto}: ${num(q)} ${existencia.unidad} guardado en ${u.codigo_completo}`);
      setAbierto(false);
      elegir(null);
      onCambio?.();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  const q = Number(cantidad.replace(",", "."));
  const libre = datos.capacidad_disponible;
  const porEnvases = datos.capacidad_bultos != null;
  const [capacidades, setCapacidades] = useState<{ bultos: string; cantidad: string } | null>(null);
  const puedeConfigurar = !!onCambio && puede("bodegas:administrar") && u.almacenable;
  const guardarCapacidad = async () => {
    try {
      await api.put(`/ubicaciones/${u.id}`, {
        capacidad_bultos: capacidades!.bultos === "" ? null : Number(capacidades!.bultos),
        capacidad: capacidades!.cantidad === "" ? null : Number(capacidades!.cantidad.replace(",", ".")),
      });
      setCapacidades(null);
      avisar("exito", "Capacidad actualizada");
      onCambio?.();
    } catch (e: any) {
      avisar("error", e.message);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">Existencias</p>
          <p className="cifra text-lg font-semibold">{datos.existencias.length}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">Valor</p>
          <p className="cifra text-lg font-semibold">{datos.valor != null ? `$${num(datos.valor, 0)}` : "—"}</p>
        </div>
        <div className="rounded-lg bg-slate-50 p-2">
          <p className="text-[11px] text-slate-500 uppercase">{porEnvases ? "Envases" : "Capacidad libre"}</p>
          <p className={`cifra text-lg font-semibold ${porEnvases && datos.bultos_disponibles <= 0 ? "text-rose-600" : ""}`}>{porEnvases ? `${datos.bultos} / ${datos.capacidad_bultos}` : num(libre)}</p>
        </div>
      </div>
      {porEnvases && (
        <p className="text-xs text-slate-600">
          {datos.bultos_disponibles > 0 ? `Caben ${datos.bultos_disponibles} envase(s) más.` : datos.bultos_disponibles === 0 ? "Ubicación completa." : `Excedida en ${-datos.bultos_disponibles} envase(s).`}
        </p>
      )}

      {puedeConfigurar && !capacidades && !abierto && (
        <button onClick={() => setCapacidades({ bultos: datos.capacidad_bultos != null ? String(datos.capacidad_bultos) : "", cantidad: u.capacidad != null ? String(u.capacidad) : "" })} className="flex items-center gap-1.5 text-xs font-medium text-marca-700 hover:underline">
          <Settings2 className="size-3.5" /> {porEnvases || u.capacidad != null ? "Cambiar capacidad máxima" : "Definir capacidad máxima"}
        </button>
      )}
      {capacidades && (
        <div className="space-y-2 rounded-xl border border-slate-300 bg-slate-50 p-3">
          <p className="text-sm font-semibold text-slate-900">Capacidad máxima de {u.codigo_completo}</p>
          <Campo etiqueta="Máximo de envases (tambores, bidones, pallets)" ayuda="Vacío = sin límite. Cuenta envases, sin importar su contenido.">
            <Entrada type="number" min={0} value={capacidades.bultos} onChange={(e) => setCapacidades({ ...capacidades, bultos: e.target.value })} autoFocus />
          </Campo>
          <Campo etiqueta="Máximo en cantidad (opcional)" ayuda="Suma de lo almacenado en su unidad principal (L, kg, un).">
            <Entrada inputMode="decimal" value={capacidades.cantidad} onChange={(e) => setCapacidades({ ...capacidades, cantidad: e.target.value })} />
          </Campo>
          <div className="flex gap-2">
            <Boton variante="secundario" className="flex-1" onClick={() => setCapacidades(null)}>Cancelar</Boton>
            <Boton className="flex-1" onClick={guardarCapacidad}>Guardar</Boton>
          </div>
        </div>
      )}

      {puedeGuardar && !abierto && (
        <Boton className="w-full" icono={<PackagePlus className="size-4" />} onClick={() => setAbierto(true)}>
          Guardar producto aquí
        </Boton>
      )}
      {!!onCambio && !u.almacenable && <p className="rounded-lg bg-slate-50 p-2 text-xs text-slate-600">Este elemento agrupa posiciones. Para guardar productos haga clic en una posición.</p>}

      {abierto && (
        <div className="space-y-3 rounded-xl border-2 border-marca-500 bg-marca-50/50 p-3">
          <p className="text-sm font-semibold text-slate-900">Guardar en {u.codigo_completo}</p>
          {error && <Aviso tipo="error">{error}</Aviso>}
          <SelectorExistencia valor={existencia} onCambio={elegir} />
          {!existencia && (sinUbicar.datos?.items ?? []).length > 0 && (
            <div>
              <p className="mb-1 text-[11px] font-semibold text-slate-500 uppercase">Sin ubicación en esta bodega</p>
              <ul className="space-y-1">
                {sinUbicar.datos.items.map((e: any) => (
                  <li key={e.id}>
                    <button onClick={() => elegir(e)} className="block w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-left text-sm hover:border-marca-500">
                      <b>{e.producto}</b> · {num(e.cantidad_fisica)} {e.unidad}
                      <span className="block text-xs text-slate-500">{e.codigo_publico} · lote {e.lote ?? "—"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {existencia && (
            <>
              <p className="text-xs text-slate-600">
                Ahora en: <b>{existencia.ubicacion ?? `${existencia.bodega} (sin ubicación)`}</b>
              </p>
              <Campo etiqueta={`Cantidad a guardar (${existencia.unidad})`} ayuda={q > 0 && q < existencia.cantidad_fisica ? "Cantidad parcial: se crea una existencia nueva con su propio QR (mismo lote, costo y fecha de ingreso)." : `Tiene ${num(existencia.cantidad_fisica)} ${existencia.unidad}.`} error={q > existencia.cantidad_fisica ? "Supera la cantidad de la existencia." : libre != null && q > libre ? null : null}>
                <Entrada inputMode="decimal" value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
              </Campo>
              {libre != null && q > libre && <Aviso tipo="alerta">Supera la capacidad libre de la ubicación ({num(libre)}). Puede guardarse igual.</Aviso>}
              {porEnvases && (existencia.envases ?? 1) > datos.bultos_disponibles && (
                <Aviso tipo="alerta">
                  Esta existencia ocupa {existencia.envases ?? 1} envase(s) y solo {Math.max(0, datos.bultos_disponibles)} caben (máximo {datos.capacidad_bultos}). Puede guardarse igual.
                </Aviso>
              )}
            </>
          )}
          <div className="flex gap-2">
            <Boton variante="secundario" className="flex-1" onClick={() => { setAbierto(false); elegir(null); }}>
              Cancelar
            </Boton>
            <Boton className="flex-1" cargando={ocupado} disabled={!existencia || !(q > 0) || q > existencia.cantidad_fisica} onClick={guardar}>
              Guardar
            </Boton>
          </div>
        </div>
      )}

      {datos.existencias.length === 0 && !abierto && <p className="py-3 text-center text-sm text-slate-500">Ubicación vacía.</p>}
      <ul className="space-y-1.5">
        {datos.existencias.map((e: any) => (
          <li key={e.id}>
            <a href={`/existencia/?id=${e.id}`} className="block rounded-lg border border-slate-200 p-2.5 text-sm hover:border-marca-500">
              <span className="flex justify-between gap-2">
                <b className="truncate">{e.producto}</b>
                <span className="cifra shrink-0">
                  {num(e.cantidad)} {e.unidad}
                </span>
              </span>
              <span className="mt-0.5 block text-xs text-slate-500">
                {e.codigo_publico} · Lote {e.lote ?? "—"} · Ingreso {new Date(e.fecha_ingreso).toLocaleDateString("es-CL")}
                {e.fecha_vencimiento && ` · Vence ${new Date(e.fecha_vencimiento + "T12:00:00").toLocaleDateString("es-CL")}`}
                {e.ubicacion && ` · ${e.ubicacion}`}
              </span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
