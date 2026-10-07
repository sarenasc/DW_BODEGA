"use client";

import { DownloadCloud, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, Cargando, Encabezado, Entrada, Estado, Insignia, Modal, Paginacion, Pestanas, Selector, Tabla, Tarjeta, useAccion, useAviso } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, fecha, hoyISO, num } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Procesos() {
  const router = useRouter();
  const { puede } = useSesion();
  const avisar = useAviso();
  const costos = puede("costos:ver");
  const [estado, setEstado] = useState("ABIERTO");
  const [f, setF] = useState<Record<string, any>>({});
  const [pagina, setPagina] = useState(1);
  const val = useDatos("/procesos/valores");
  const { datos, cargando, recargar } = useDatos("/procesos", { ...f, estado: estado === "TODOS" ? undefined : estado, pagina, tam: 50 });
  const fuentes = useDatos<any[]>(puede("procesos:abrir") ? "/integraciones/fuentes" : null);
  const [nuevo, setNuevo] = useState<Record<string, any> | null>(null);
  const [importar, setImportar] = useState<{ fuente: string; lista: any[] | null; marcados: Set<string>; error?: string } | null>(null);
  const { ejecutar, ocupado } = useAccion();
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave, estado]);
  const activas = (fuentes.datos ?? []).filter((x) => x.activa);

  const cargarDisponibles = (fuente: string) => {
    setImportar({ fuente, lista: null, marcados: new Set() });
    api.get(`/integraciones/fuentes/${fuente}/disponibles`).then((lista) => setImportar({ fuente, lista, marcados: new Set() })).catch((e) => setImportar({ fuente, lista: [], marcados: new Set(), error: e.message }));
  };
  const hacerImportacion = () =>
    ejecutar(async () => {
      const r = await api.post(`/integraciones/fuentes/${importar!.fuente}/importar`, { ids: [...importar!.marcados], abrir: true });
      setImportar(null);
      recargar();
      avisar(r.omitidos.length ? "info" : "exito", `${r.importados.length} proceso(s) importado(s) y abierto(s)${r.omitidos.length ? `; ${r.omitidos.length} omitido(s)` : ""}.`);
      if (r.importados.length === 1) router.push(`/procesos/detalle/?id=${r.importados[0].id}`);
    });

  return (
    <>
      <Encabezado titulo="Procesos productivos" descripcion="Copia local de los procesos de producción. Los consumos se asocian al proceso y determinan su costo y su costo por kilo.">
        {puede("procesos:abrir") && activas.length > 0 && <Boton variante="secundario" icono={<DownloadCloud className="size-4" />} onClick={() => cargarDisponibles(String(activas[0].id))}>Importar desde producción</Boton>}
        {puede("procesos:abrir") && <Boton icono={<Plus className="size-4" />} onClick={() => setNuevo({ fecha: hoyISO() })}>Proceso manual</Boton>}
      </Encabezado>
      <Pestanas valor={estado} onCambio={setEstado} opciones={[["ABIERTO", "Abiertos"], ["BORRADOR", "Borradores"], ["CERRADO", "Cerrados"], ["ANULADO", "Anulados"], ["TODOS", "Todos"]].map(([valor, texto]) => ({ valor, texto }))} />
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-5">
          <Entrada placeholder="Código, productor, lote…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2" />
          <Selector vacio="Todas las especies" value={f.especie ?? ""} onChange={(e) => setF({ ...f, especie: e.target.value })} opciones={(val.datos?.especies ?? []).map((x: string) => ({ valor: x, texto: x }))} />
          <Selector vacio="Todos los productores" value={f.productor ?? ""} onChange={(e) => setF({ ...f, productor: e.target.value })} opciones={(val.datos?.productores ?? []).map((x: string) => ({ valor: x, texto: x }))} />
          <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            vacio="No hay procesos en este estado."
            onFila={(p) => router.push(`/procesos/detalle/?id=${p.id}`)}
            columnas={[
              { clave: "codigo", titulo: "Proceso", render: (p) => <><span className="cifra font-semibold text-slate-900">{p.codigo}</span><span className="block text-xs text-slate-500">{p.tiene_fuente ? "Desde producción" : (p.tipo ?? "Manual")}</span></> },
              { clave: "fecha", titulo: "Fecha", render: (p) => fecha(p.fecha) },
              { clave: "especie", titulo: "Especie / variedad", render: (p) => [p.especie, p.variedad].filter(Boolean).join(" · ") || "—" },
              { clave: "productor", titulo: "Productor", ocultarMovil: true },
              { clave: "kilos_base", titulo: "Kilos (base)", alinear: "derecha", render: (p) => <>{num(p.kilos_base, 0)} <Insignia tono={p.estado_kilos === "DEFINITIVO" ? "verde" : "ambar"}>{p.estado_kilos === "DEFINITIVO" ? "Def." : "Prov."}</Insignia></> },
              ...(costos ? [{ clave: "costo_total", titulo: "Costo", alinear: "derecha" as const, ocultarMovil: true, render: (p: any) => clp(p.costo_total) }, { clave: "costo_por_kilo", titulo: "Costo/kg", alinear: "derecha" as const, render: (p: any) => clp(p.costo_por_kilo, 2) }] : []),
              { clave: "estado", titulo: "Estado", render: (p) => <Estado valor={p.estado} /> },
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>

      <Modal abierto={!!nuevo} titulo="Proceso manual" onCerrar={() => setNuevo(null)} pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { const p = await api.post("/procesos", Object.fromEntries(Object.entries(nuevo!).filter(([, v]) => v !== "").map(([k, v]) => [k, k.startsWith("kilos") ? Number(v) : v]))); router.push(`/procesos/detalle/?id=${p.id}`); }, "Proceso creado")}>Crear</Boton>}>
        {nuevo && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Aviso className="sm:col-span-2">Para procesos sin origen en producción (por ejemplo una sanitización). El código se genera solo si lo deja vacío.</Aviso>
            {[["codigo", "Código"], ["tipo", "Tipo"], ["especie", "Especie"], ["variedad", "Variedad"], ["productor", "Productor"], ["kilos_procesados", "Kilos procesados"]].map(([k, t]) => (
              <Campo key={k} etiqueta={t}><Entrada inputMode={k.startsWith("kilos") ? "decimal" : undefined} value={nuevo[k] ?? ""} onChange={(e) => setNuevo({ ...nuevo, [k]: e.target.value })} /></Campo>
            ))}
            <Campo etiqueta="Fecha"><Entrada type="date" value={nuevo.fecha ?? ""} onChange={(e) => setNuevo({ ...nuevo, fecha: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>

      <Modal abierto={!!importar} titulo="Importar procesos desde producción" onCerrar={() => setImportar(null)} ancho="max-w-3xl" pie={<Boton cargando={ocupado} disabled={!importar?.marcados.size} onClick={hacerImportacion}>Importar y abrir ({importar?.marcados.size ?? 0})</Boton>}>
        {importar && (
          <div className="space-y-3">
            {activas.length > 1 && <Campo etiqueta="Fuente"><Selector value={importar.fuente} onChange={(e) => cargarDisponibles(e.target.value)} opciones={activas.map((x) => ({ valor: x.id, texto: x.nombre }))} /></Campo>}
            {importar.error && <Aviso tipo="error" titulo="No fue posible leer la base productiva">{importar.error}</Aviso>}
            {!importar.lista ? (
              <Cargando texto="Consultando producción…" />
            ) : (
              <Tabla
                claveFila="id_externo"
                vacio="No hay procesos en el origen."
                filas={importar.lista}
                columnas={[
                  { clave: "sel", titulo: "", render: (x) => (x.importado ? <Insignia tono="gris">Importado</Insignia> : <input type="checkbox" className="size-4 accent-emerald-600" aria-label={`Seleccionar ${x.id_externo}`} checked={importar.marcados.has(x.id_externo)} onChange={() => setImportar((i) => { const m = new Set(i!.marcados); if (m.has(x.id_externo)) m.delete(x.id_externo); else m.add(x.id_externo); return { ...i!, marcados: m }; })} />) },
                  { clave: "codigo", titulo: "Proceso", render: (x) => <b>{x.datos.codigo ?? x.id_externo}</b> },
                  { clave: "fecha", titulo: "Fecha", render: (x) => fecha(x.datos.fecha) },
                  { clave: "especie", titulo: "Especie", render: (x) => [x.datos.especie, x.datos.variedad].filter(Boolean).join(" · ") },
                  { clave: "productor", titulo: "Productor", ocultarMovil: true, render: (x) => x.datos.productor },
                  { clave: "kilos", titulo: "Kilos proc.", alinear: "derecha", render: (x) => num(x.datos.kilos_procesados, 0) },
                  { clave: "estado", titulo: "Estado origen", ocultarMovil: true, render: (x) => x.datos.estado_externo },
                ]}
              />
            )}
            <p className="text-xs text-slate-500">La información se copia a la base local. Desde ahí la operación no depende de la conexión con producción.</p>
          </div>
        )}
      </Modal>
    </>
  );
}
