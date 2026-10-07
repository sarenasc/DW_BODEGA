"use client";

import { Box, Plus, Rows3 } from "lucide-react";
import { useState } from "react";
import { Aviso, Boton, Campo, Cargando, Encabezado, EnlaceBoton, Entrada, Estado, Insignia, Interruptor, Modal, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { ContenidoUbicacion } from "@/components/ContenidoUbicacion";
import { api } from "@/lib/api";
import { num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

const TIPOS = ["ZONA", "SECTOR", "PASILLO", "RACK", "ESTANTE", "NIVEL", "POSICION", "PISO", "UBICACION"];

export default function Ubicaciones() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const editable = puede("bodegas:administrar");
  const [q, setQ] = useState("");
  const [inactivas, setInactivas] = useState(false);
  const bodega = useDatos(id ? `/bodegas/${id}` : null);
  const { datos, recargar } = useDatos(id ? "/ubicaciones" : null, { bodega_id: id, q, activo: inactivas ? undefined : true });
  const [nueva, setNueva] = useState<any>(null);
  const [rack, setRack] = useState<any>(null);
  const [contenido, setContenido] = useState<any>(null);
  const { ejecutar, ocupado } = useAccion();

  if (!bodega.datos) return <Cargando />;
  const b = bodega.datos;
  const padres = (datos ?? []).filter((u: any) => !u.almacenable || u.tipo !== "POSICION").map((u: any) => ({ valor: u.id, texto: u.codigo_completo }));

  return (
    <>
      <Encabezado titulo={`Ubicaciones · ${b.nombre}`} descripcion="Estructura lógica de la bodega. Solo las ubicaciones almacenables reciben stock." volver="/bodegas/">
        <EnlaceBoton href={`/bodegas/plano/?id=${b.id}`} icono={<Box className="size-4" />}>
          Plano 2D / 3D
        </EnlaceBoton>
        {editable && (
          <>
            <Boton variante="secundario" icono={<Rows3 className="size-4" />} onClick={() => setRack({ codigo: "", niveles: 3, posiciones: 4, prefijo_nivel: "N", prefijo_posicion: "P", padre_id: "", capacidad_posicion: "" })}>
              Generar rack
            </Boton>
            <Boton icono={<Plus className="size-4" />} onClick={() => setNueva({ codigo: "", tipo: "UBICACION", padre_id: "", nombre: "", capacidad: "", almacenable: true })}>
              Nueva ubicación
            </Boton>
          </>
        )}
      </Encabezado>
      <Tarjeta sinRelleno>
        <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 p-3">
          <Entrada value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por código…" className="max-w-sm" />
          <Interruptor valor={inactivas} onCambio={setInactivas} etiqueta="Incluir inactivas" />
          <span className="ml-auto text-xs text-slate-500">{datos?.length ?? 0} ubicaciones</span>
        </div>
        {!datos ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos}
            vacio="Esta bodega aún no tiene ubicaciones. Genere un rack o cree una ubicación."
            onFila={(u) => api.get(`/ubicaciones/${u.id}/contenido`).then(setContenido)}
            columnas={[
              { clave: "codigo_completo", titulo: "Código", render: (u) => <span className="cifra font-medium" style={{ paddingLeft: u.nivel * 14 }}>{u.codigo_completo}</span> },
              { clave: "tipo", titulo: "Tipo", render: (u) => <Insignia tono={u.tipo === "POSICION" ? "verde" : "gris"}>{u.tipo}</Insignia> },
              { clave: "nombre", titulo: "Nombre", ocultarMovil: true },
              { clave: "capacidad", titulo: "Capacidad", alinear: "derecha", ocultarMovil: true, render: (u) => num(u.capacidad) },
              { clave: "almacenable", titulo: "Almacena", render: (u) => (u.almacenable ? "Sí" : "No") },
              { clave: "activo", titulo: "Estado", render: (u) => <Estado valor={u.activo ? "ACTIVO" : "ANULADO"} /> },
              ...(editable
                ? [{
                    clave: "x",
                    titulo: "",
                    alinear: "derecha" as const,
                    render: (u: any) => (
                      <span onClick={(e) => e.stopPropagation()}>
                        <Boton tam="sm" variante="fantasma" onClick={() => ejecutar(async () => { await api.put(`/ubicaciones/${u.id}`, { activo: !u.activo }); recargar(); })}>
                          {u.activo ? "Desactivar" : "Activar"}
                        </Boton>
                      </span>
                    ),
                  }]
                : []),
            ]}
          />
        )}
      </Tarjeta>

      <Modal abierto={!!nueva} titulo="Nueva ubicación" onCerrar={() => setNueva(null)} ancho="max-w-lg"
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { await api.post("/ubicaciones", { ...nueva, bodega_id: b.id, padre_id: nueva.padre_id ? Number(nueva.padre_id) : null, capacidad: nueva.capacidad ? Number(nueva.capacidad) : null }); setNueva(null); recargar(); }, "Ubicación creada")}>Crear</Boton>}>
        {nueva && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Dentro de" className="sm:col-span-2" ayuda="Vacío = directamente en la bodega.">
              <Selector vacio={`${b.codigo} (raíz)`} value={nueva.padre_id} onChange={(e) => setNueva({ ...nueva, padre_id: e.target.value })} opciones={padres} />
            </Campo>
            <Campo etiqueta="Código" requerido ayuda="Sin guiones. Se antepone el código del padre.">
              <Entrada value={nueva.codigo} onChange={(e) => setNueva({ ...nueva, codigo: e.target.value.toUpperCase() })} />
            </Campo>
            <Campo etiqueta="Tipo">
              <Selector value={nueva.tipo} onChange={(e) => setNueva({ ...nueva, tipo: e.target.value })} opciones={TIPOS.map((t) => ({ valor: t, texto: t }))} />
            </Campo>
            <Campo etiqueta="Nombre">
              <Entrada value={nueva.nombre} onChange={(e) => setNueva({ ...nueva, nombre: e.target.value })} />
            </Campo>
            <Campo etiqueta="Capacidad">
              <Entrada inputMode="decimal" value={nueva.capacidad} onChange={(e) => setNueva({ ...nueva, capacidad: e.target.value })} />
            </Campo>
            <Interruptor valor={nueva.almacenable} onCambio={(v) => setNueva({ ...nueva, almacenable: v })} etiqueta="Admite stock" />
          </div>
        )}
      </Modal>

      <Modal abierto={!!rack} titulo="Generar rack" onCerrar={() => setRack(null)} ancho="max-w-lg"
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { await api.post(`/bodegas/${b.id}/racks`, { ...rack, niveles: Number(rack.niveles), posiciones: Number(rack.posiciones), padre_id: rack.padre_id ? Number(rack.padre_id) : null, capacidad_posicion: rack.capacidad_posicion ? Number(rack.capacidad_posicion) : null }); setRack(null); recargar(); }, "Rack generado")}>Generar</Boton>}>
        {rack && (
          <div className="grid gap-3 sm:grid-cols-2">
            <Campo etiqueta="Código del rack" requerido>
              <Entrada value={rack.codigo} placeholder="R02" onChange={(e) => setRack({ ...rack, codigo: e.target.value.toUpperCase() })} />
            </Campo>
            <Campo etiqueta="Dentro de">
              <Selector vacio={`${b.codigo} (raíz)`} value={rack.padre_id} onChange={(e) => setRack({ ...rack, padre_id: e.target.value })} opciones={padres} />
            </Campo>
            <Campo etiqueta="Niveles">
              <Entrada type="number" min={1} max={20} value={rack.niveles} onChange={(e) => setRack({ ...rack, niveles: e.target.value })} />
            </Campo>
            <Campo etiqueta="Posiciones por nivel">
              <Entrada type="number" min={1} max={60} value={rack.posiciones} onChange={(e) => setRack({ ...rack, posiciones: e.target.value })} />
            </Campo>
            <Campo etiqueta="Capacidad por posición">
              <Entrada inputMode="decimal" value={rack.capacidad_posicion} onChange={(e) => setRack({ ...rack, capacidad_posicion: e.target.value })} />
            </Campo>
            <Aviso className="sm:col-span-2">
              Se crearán {1 + Number(rack.niveles || 0) * (1 + Number(rack.posiciones || 0))} ubicaciones, por ejemplo{" "}
              <b>
                {b.codigo}-{rack.codigo || "R02"}-{rack.prefijo_nivel}01-{rack.prefijo_posicion}01
              </b>
              .
            </Aviso>
          </div>
        )}
      </Modal>

      <Modal abierto={!!contenido} titulo={contenido?.ubicacion.codigo_completo} onCerrar={() => setContenido(null)}>
        {contenido && <ContenidoUbicacion datos={contenido} />}
      </Modal>
    </>
  );
}
