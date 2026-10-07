"use client";

// Integracion con la base productiva: conexion de solo lectura, fuente (vista o consulta) y mapeo visual de columnas.

import { ArrowRight, Database, Eye, Plus, Plug, Save, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, Cargando, Encabezado, Entrada, Estado, Insignia, Interruptor, Modal, Pestanas, Selector, Tabla, Tarjeta, useAccion, useAviso } from "@/components/ui";
import { api } from "@/lib/api";
import { etiqueta, fechaHora } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

type Mapeo = { k: number; columna_externa: string; campo_interno: string; transformacion: string; factor: string; politica_actualizacion: string };
let sig = 1;

export default function Integraciones() {
  const avisar = useAviso();
  const op = useDatos("/integraciones/opciones");
  const conexiones = useDatos<any[]>("/integraciones/conexiones");
  const fuentes = useDatos<any[]>("/integraciones/fuentes");
  const ejecuciones = useDatos("/integraciones/ejecuciones", { tam: 30 });
  const [tab, setTab] = useState("fuentes");
  const [con, setCon] = useState<Record<string, any> | null>(null);
  const [fuente, setFuente] = useState<Record<string, any> | null>(null);
  const [mapeos, setMapeos] = useState<Mapeo[]>([]);
  const [columnas, setColumnas] = useState<string[]>([]);
  const [previa, setPrevia] = useState<any>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  const { ejecutar, ocupado } = useAccion();

  const abrirFuente = (f: any | null) => {
    setFallo(null);
    setPrevia(null);
    setColumnas([]);
    setFuente(f ? { ...f } : { nombre: "", tipo: "VISTA", origen: "", columna_id: "", columna_fecha: "", intervalo_minutos: 0, guardar_no_mapeadas: true, activa: true, conexion_id: conexiones.datos?.[0]?.id ?? "" });
    setMapeos((f?.mapeos ?? []).map((m: any) => ({ k: sig++, columna_externa: m.columna_externa, campo_interno: m.campo_interno, transformacion: m.transformacion ?? "", factor: m.factor ?? "", politica_actualizacion: m.politica_actualizacion })));
    if (f) api.get(`/integraciones/fuentes/${f.id}/columnas`).then((r) => setColumnas(r.columnas)).catch(() => {});
  };
  useEffect(() => {
    if (fuentes.datos?.length && !fuente) abrirFuente(fuentes.datos[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fuentes.datos]);

  async function guardarFuente(): Promise<any | null> {
    setFallo(null);
    try {
      const cuerpo = {
        conexion_id: Number(fuente!.conexion_id), nombre: fuente!.nombre, tipo: fuente!.tipo, origen: fuente!.origen, columna_id: fuente!.columna_id,
        columna_fecha: fuente!.columna_fecha || null, intervalo_minutos: Number(fuente!.intervalo_minutos) || 0, guardar_no_mapeadas: !!fuente!.guardar_no_mapeadas, activa: !!fuente!.activa,
        mapeos: mapeos.filter((m) => m.columna_externa && m.campo_interno).map((m) => ({ columna_externa: m.columna_externa, campo_interno: m.campo_interno, transformacion: m.transformacion || null, factor: m.factor !== "" ? Number(m.factor) : null, politica_actualizacion: m.politica_actualizacion })),
      };
      const r = fuente!.id ? await api.put(`/integraciones/fuentes/${fuente!.id}`, cuerpo) : await api.post("/integraciones/fuentes", cuerpo);
      fuentes.recargar();
      setFuente({ ...r });
      avisar("exito", "Fuente guardada");
      return r;
    } catch (e: any) {
      setFallo(e.message);
      return null;
    }
  }
  const probarFuente = async () => {
    const r = await guardarFuente();
    if (!r) return;
    try {
      const [cols, vp] = await Promise.all([api.get(`/integraciones/fuentes/${r.id}/columnas`), api.get(`/integraciones/fuentes/${r.id}/vista-previa`)]);
      setColumnas(cols.columnas);
      setPrevia(vp);
    } catch (e: any) {
      setFallo(e.message);
    }
  };
  const mapear = (k: number, cambios: Partial<Mapeo>) => setMapeos((ms) => ms.map((m) => (m.k === k ? { ...m, ...cambios } : m)));
  const usados = new Set(mapeos.map((m) => m.columna_externa.toLowerCase()));

  if (!op.datos || !conexiones.datos) return <Cargando />;
  const campos = op.datos.campos_proceso as string[];

  return (
    <>
      <Encabezado titulo="Integraciones" descripcion="La base productiva es solo una fuente de sincronización: se lee, se copia a la base local y la operación continúa sin depender de ella." />
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "fuentes", texto: "Fuentes y mapeo" }, { valor: "conexiones", texto: "Conexiones", contador: conexiones.datos.length }, { valor: "historial", texto: "Historial de sincronización" }]} />

      {tab === "conexiones" && (
        <Tarjeta titulo="Conexiones a bases productivas" sinRelleno accion={<Boton tam="sm" icono={<Plus className="size-4" />} onClick={() => setCon({ motor: "sqlserver", nombre: "", servidor: "", puerto: "", base_datos: "", usuario: "", clave: "" })}>Nueva conexión</Boton>}>
          <Tabla
            filas={conexiones.datos}
            vacio="Aún no hay conexiones."
            columnas={[
              { clave: "nombre", titulo: "Nombre", render: (c) => <span className="font-medium text-slate-900">{c.nombre}</span> },
              { clave: "motor", titulo: "Motor", render: (c) => <Insignia tono="azul">{c.motor}</Insignia> },
              { clave: "servidor", titulo: "Servidor", render: (c) => (c.servidor ? `${c.servidor}${c.puerto ? `:${c.puerto}` : ""}` : "—") },
              { clave: "base_datos", titulo: "Base" },
              { clave: "usuario", titulo: "Usuario" },
              { clave: "tiene_clave", titulo: "Clave", render: (c) => (c.tiene_clave ? "•••••• (cifrada)" : "—") },
              { clave: "activa", titulo: "Estado", render: (c) => <Estado valor={c.activa ? "ACTIVA" : "ANULADA"} /> },
              { clave: "x", titulo: "", alinear: "derecha", render: (c) => (
                <span className="flex justify-end gap-1">
                  <Boton tam="sm" variante="secundario" icono={<Plug className="size-3.5" />} onClick={() => api.post(`/integraciones/conexiones/${c.id}/probar`).then((r) => avisar(r.ok ? "exito" : "error", r.mensaje))}>Probar</Boton>
                  <Boton tam="sm" variante="fantasma" onClick={() => setCon({ ...c, clave: "" })}>Editar</Boton>
                </span>
              ) },
            ]}
          />
        </Tarjeta>
      )}

      {tab === "fuentes" && (
        <div className="grid gap-3 lg:grid-cols-[260px_1fr]">
          <Tarjeta titulo="Fuentes" sinRelleno className="self-start" accion={<Boton tam="sm" variante="secundario" onClick={() => abrirFuente(null)} aria-label="Nueva fuente"><Plus className="size-4" /></Boton>}>
            {(fuentes.datos ?? []).length === 0 && <p className="p-4 text-sm text-slate-500">Cree primero una conexión y luego una fuente.</p>}
            {(fuentes.datos ?? []).map((f) => (
              <button key={f.id} onClick={() => abrirFuente(f)} className={`block w-full border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 ${fuente?.id === f.id ? "bg-marca-50" : ""}`}>
                <span className="flex items-center justify-between gap-2"><b className="truncate text-sm">{f.nombre}</b><Insignia tono={f.activa ? "verde" : "gris"}>{f.activa ? "Activa" : "Inactiva"}</Insignia></span>
                <span className="block text-xs text-slate-500">{f.conexion} · {f.mapeos?.length ?? 0} campos mapeados</span>
              </button>
            ))}
          </Tarjeta>
          {fuente && (
            <div className="space-y-3">
              {fallo && <Aviso tipo="error">{fallo}</Aviso>}
              <Tarjeta titulo="Origen de los procesos">
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  <Campo etiqueta="Nombre" requerido><Entrada value={fuente.nombre} onChange={(e) => setFuente({ ...fuente, nombre: e.target.value })} /></Campo>
                  <Campo etiqueta="Conexión" requerido><Selector value={fuente.conexion_id} onChange={(e) => setFuente({ ...fuente, conexion_id: e.target.value })} opciones={conexiones.datos.map((c) => ({ valor: c.id, texto: c.nombre }))} /></Campo>
                  <Campo etiqueta="Tipo"><Selector value={fuente.tipo} onChange={(e) => setFuente({ ...fuente, tipo: e.target.value })} opciones={[{ valor: "VISTA", texto: "Vista o tabla" }, { valor: "CONSULTA", texto: "Consulta SQL (SELECT)" }]} /></Campo>
                  <Campo etiqueta="Sincronización automática (min)" ayuda="0 = solo manual."><Entrada type="number" min={0} value={fuente.intervalo_minutos ?? 0} onChange={(e) => setFuente({ ...fuente, intervalo_minutos: e.target.value })} /></Campo>
                  <Campo etiqueta={fuente.tipo === "VISTA" ? "Nombre de la vista" : "Consulta SQL"} requerido className="sm:col-span-2 lg:col-span-4" ayuda="Solo se admite una sentencia SELECT. El usuario de la conexión debe ser de solo lectura.">
                    {fuente.tipo === "VISTA" ? <Entrada value={fuente.origen} placeholder="dbo.vw_procesos" onChange={(e) => setFuente({ ...fuente, origen: e.target.value })} /> : <textarea className="campo font-mono text-xs" rows={4} value={fuente.origen} placeholder="SELECT id_proceso, fecha, peso_neto FROM procesos WHERE …" onChange={(e) => setFuente({ ...fuente, origen: e.target.value })} />}
                  </Campo>
                  <Campo etiqueta="Columna identificadora del proceso" requerido><Entrada value={fuente.columna_id} list="columnas-origen" onChange={(e) => setFuente({ ...fuente, columna_id: e.target.value })} /></Campo>
                  <Campo etiqueta="Columna de fecha (para listar)"><Entrada value={fuente.columna_fecha ?? ""} list="columnas-origen" onChange={(e) => setFuente({ ...fuente, columna_fecha: e.target.value })} /></Campo>
                  <div className="flex items-end gap-4 sm:col-span-2">
                    <Interruptor valor={!!fuente.guardar_no_mapeadas} onCambio={(v) => setFuente({ ...fuente, guardar_no_mapeadas: v })} etiqueta="Guardar también columnas no mapeadas" />
                    <Interruptor valor={!!fuente.activa} onCambio={(v) => setFuente({ ...fuente, activa: v })} etiqueta="Activa" />
                  </div>
                </div>
                <datalist id="columnas-origen">{columnas.map((c) => <option key={c} value={c} />)}</datalist>
              </Tarjeta>

              <Tarjeta titulo="Mapeo de campos: fuente externa → campo interno" accion={<Boton tam="sm" variante="secundario" icono={<Plus className="size-4" />} onClick={() => setMapeos((m) => [...m, { k: sig++, columna_externa: "", campo_interno: "", transformacion: "", factor: "", politica_actualizacion: "SIEMPRE" }])}>Agregar campo</Boton>}>
                {columnas.length > 0 && (
                  <div className="mb-3 flex flex-wrap gap-1.5">
                    <span className="text-xs text-slate-500">Columnas del origen:</span>
                    {columnas.map((c) => (
                      <button key={c} disabled={usados.has(c.toLowerCase())} onClick={() => setMapeos((m) => [...m, { k: sig++, columna_externa: c, campo_interno: campos.includes(c.toLowerCase()) ? c.toLowerCase() : "", transformacion: "", factor: "", politica_actualizacion: "SIEMPRE" }])} className="rounded-md border border-slate-300 bg-white px-2 py-0.5 font-mono text-xs text-slate-700 hover:border-marca-500 disabled:border-transparent disabled:bg-emerald-50 disabled:text-emerald-700">
                        {c}
                      </button>
                    ))}
                  </div>
                )}
                {mapeos.length === 0 && <p className="text-sm text-slate-500">Guarde y pruebe la fuente para ver sus columnas; luego asigne cada una a un campo interno. Nada se asume de la base productiva.</p>}
                <div className="space-y-2">
                  {mapeos.map((m) => (
                    <div key={m.k} className="grid grid-cols-2 items-center gap-2 rounded-lg bg-slate-50 p-2 md:grid-cols-[1fr_auto_1fr_150px_90px_170px_auto]">
                      <Entrada className="font-mono !text-xs" placeholder="columna_externa" list="columnas-origen" value={m.columna_externa} onChange={(e) => mapear(m.k, { columna_externa: e.target.value })} />
                      <ArrowRight className="hidden size-4 text-slate-400 md:block" />
                      <Entrada placeholder="campo interno o extra.clave" list="campos-internos" value={m.campo_interno} onChange={(e) => mapear(m.k, { campo_interno: e.target.value })} />
                      <Selector aria-label="Transformación" vacio="Sin transformar" value={m.transformacion} onChange={(e) => mapear(m.k, { transformacion: e.target.value })} opciones={op.datos.transformaciones.map((t: string) => ({ valor: t, texto: etiqueta(t) }))} />
                      <Entrada aria-label="Factor" placeholder="× factor" inputMode="decimal" value={m.factor} onChange={(e) => mapear(m.k, { factor: e.target.value })} />
                      <Selector aria-label="Política de actualización" value={m.politica_actualizacion} onChange={(e) => mapear(m.k, { politica_actualizacion: e.target.value })} opciones={[{ valor: "SIEMPRE", texto: "Actualizar siempre" }, { valor: "SOLO_IMPORTAR", texto: "Solo al importar" }, { valor: "MANUAL", texto: "Manual (no pisar)" }]} />
                      <button aria-label="Quitar" onClick={() => setMapeos((ms) => ms.filter((x) => x.k !== m.k))} className="justify-self-end rounded p-1.5 text-rose-600 hover:bg-rose-50"><Trash2 className="size-4" /></button>
                    </div>
                  ))}
                </div>
                <datalist id="campos-internos">{campos.map((c) => <option key={c} value={c} />)}</datalist>
                <p className="mt-2 text-xs text-slate-500">Campos internos: {campos.slice(0, 12).join(", ")}… Use <code>extra.nombre</code> para campos adicionales.</p>
              </Tarjeta>

              <div className="flex flex-wrap justify-end gap-2">
                {fuente.id && <Boton variante="fantasma" icono={<Trash2 className="size-4 text-rose-600" />} onClick={() => confirm("¿Eliminar la fuente? Si tiene procesos importados solo se desactivará.") && ejecutar(async () => { await api.del(`/integraciones/fuentes/${fuente.id}`); setFuente(null); fuentes.recargar(); }, "Fuente eliminada")}>Eliminar</Boton>}
                <Boton variante="secundario" icono={<Eye className="size-4" />} onClick={probarFuente}>Guardar y probar</Boton>
                <Boton icono={<Save className="size-4" />} cargando={ocupado} onClick={guardarFuente}>Guardar</Boton>
              </div>

              {previa && (
                <Tarjeta titulo="Vista previa: filas del origen ya transformadas" sinRelleno>
                  <div className="overflow-x-auto">
                    <table className="tabla w-full">
                      <thead><tr><th>#</th>{Object.keys(previa.filas[0]?.mapeado ?? {}).map((k) => <th key={k}>{k}</th>)}<th>Adicionales</th></tr></thead>
                      <tbody>
                        {previa.filas.map((f: any, i: number) => (
                          <tr key={i}>
                            <td>{i + 1}</td>
                            {f.error ? <td colSpan={99} className="text-rose-700">{f.error}</td> : Object.keys(previa.filas[0].mapeado).map((k) => <td key={k} className="whitespace-nowrap">{String(f.mapeado[k] ?? "—")}</td>)}
                            {!f.error && <td className="text-xs text-slate-500">{Object.keys(f.adicionales).length} campo(s)</td>}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {previa.filas.length === 0 && <p className="p-4 text-sm text-slate-500">El origen no devolvió filas.</p>}
                </Tarjeta>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "historial" && (
        <Tarjeta sinRelleno>
          <Tabla
            filas={ejecuciones.datos?.items ?? []}
            vacio="Sin sincronizaciones registradas."
            columnas={[
              { clave: "inicio", titulo: "Fecha", render: (e) => fechaHora(e.inicio) },
              { clave: "accion", titulo: "Acción", render: (e) => etiqueta(e.accion) },
              { clave: "proceso_id", titulo: "Proceso", render: (e) => (e.proceso_id ? <a className="text-marca-700 hover:underline" href={`/procesos/detalle/?id=${e.proceso_id}`}>#{e.proceso_id}</a> : "—") },
              { clave: "cambios", titulo: "Cambios", alinear: "derecha" },
              { clave: "estado", titulo: "Resultado", render: (e) => <Estado valor={e.estado} /> },
              { clave: "error", titulo: "Detalle", render: (e) => <span className="block max-w-md truncate text-rose-700" title={e.error ?? ""}>{e.error ?? ""}</span> },
              { clave: "usuario", titulo: "Usuario", render: (e) => e.usuario ?? "Sistema" },
            ]}
          />
        </Tarjeta>
      )}

      <Modal abierto={!!con} titulo={con?.id ? "Editar conexión" : "Nueva conexión"} onCerrar={() => setCon(null)}
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { const cuerpo = { nombre: con!.nombre, motor: con!.motor, servidor: con!.servidor || null, puerto: con!.puerto ? Number(con!.puerto) : null, base_datos: con!.base_datos || null, usuario: con!.usuario || null, ...(con!.clave ? { clave: con!.clave } : {}), activa: con!.activa ?? true }; if (con!.id) await api.put(`/integraciones/conexiones/${con!.id}`, cuerpo); else await api.post("/integraciones/conexiones", cuerpo); setCon(null); conexiones.recargar(); }, "Conexión guardada")}>Guardar</Boton>}>
        {con && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Aviso className="sm:col-span-2" tipo="alerta"><Database className="mr-1 inline size-4" />Use un usuario de base de datos con permisos de <b>solo lectura</b>. La contraseña se guarda cifrada y nunca se muestra.</Aviso>
            <Campo etiqueta="Nombre" requerido><Entrada value={con.nombre} onChange={(e) => setCon({ ...con, nombre: e.target.value })} /></Campo>
            <Campo etiqueta="Motor"><Selector value={con.motor} onChange={(e) => setCon({ ...con, motor: e.target.value })} opciones={[{ valor: "sqlserver", texto: "SQL Server" }, { valor: "postgresql", texto: "PostgreSQL" }, { valor: "mysql", texto: "MySQL" }, { valor: "demo", texto: "Demo (SQLite local)" }]} /></Campo>
            <Campo etiqueta="Servidor"><Entrada value={con.servidor ?? ""} onChange={(e) => setCon({ ...con, servidor: e.target.value })} /></Campo>
            <Campo etiqueta="Puerto"><Entrada inputMode="numeric" value={con.puerto ?? ""} onChange={(e) => setCon({ ...con, puerto: e.target.value.replace(/\D/g, "") })} /></Campo>
            <Campo etiqueta="Base de datos"><Entrada value={con.base_datos ?? ""} onChange={(e) => setCon({ ...con, base_datos: e.target.value })} /></Campo>
            <Campo etiqueta="Usuario"><Entrada value={con.usuario ?? ""} autoComplete="off" onChange={(e) => setCon({ ...con, usuario: e.target.value })} /></Campo>
            <Campo etiqueta="Contraseña" ayuda={con.id ? "Vacío = conservar la actual." : undefined} className="sm:col-span-2"><Entrada type="password" autoComplete="new-password" value={con.clave ?? ""} onChange={(e) => setCon({ ...con, clave: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
    </>
  );
}
