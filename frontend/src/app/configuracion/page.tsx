"use client";

import { useEffect, useState } from "react";
import { activoCol, Crud } from "@/components/Crud";
import { Boton, Campo, Cargando, Encabezado, Entrada, Pestanas, Selector, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { fecha } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

const SECCIONES = [
  ["general", "Empresa y parámetros"], ["temporadas", "Temporadas"], ["motivos", "Tipos de ingreso y salida"], ["tipos-movimiento", "Tipos de movimiento"],
  ["tipos-bodega", "Tipos de bodega"], ["etiquetas", "Etiquetas QR"],
];
// Parametros con una lista cerrada de valores.
const OPCIONES: Record<string, [string, string][]> = {
  "fifo.ambito": [["BODEGA", "Por bodega"], ["EMPRESA", "Toda la empresa"]],
  "costeo.base_kilos": [["kilos_procesados", "Kilos procesados"], ["kilos_recepcionados", "Kilos recepcionados"], ["kilos_producidos", "Kilos producidos"], ["kilos_despachados", "Kilos despachados"]],
};

export default function Configuracion() {
  const [tab, setTab] = useState("general");
  const empresa = useDatos("/empresa");
  const params = useDatos<any[]>("/configuraciones");
  const tipos = useDatos("/tipos-movimiento", { tam: 100 });
  const [emp, setEmp] = useState<Record<string, any>>({});
  const [valores, setValores] = useState<Record<string, string>>({});
  const { ejecutar, ocupado } = useAccion();
  useEffect(() => { if (empresa.datos) setEmp(empresa.datos); }, [empresa.datos]);
  useEffect(() => { if (params.datos) setValores(Object.fromEntries(params.datos.map((p) => [p.clave, typeof p.valor === "object" ? JSON.stringify(p.valor) : String(p.valor ?? "")]))); }, [params.datos]);

  const guardarParametro = (p: any) =>
    ejecutar(async () => {
      const texto = valores[p.clave];
      let valor: any = texto;
      if (typeof p.valor === "boolean") valor = texto === "true";
      else if (typeof p.valor === "number") valor = Number(texto);
      else if (typeof p.valor === "object" && p.valor !== null) valor = JSON.parse(texto);
      await api.put(`/configuraciones/${p.clave}`, { valor });
      params.recargar();
    }, "Parámetro actualizado");

  return (
    <>
      <Encabezado titulo="Configuración" descripcion="Familias, productos, unidades, bodegas, plantillas de lote, integraciones, usuarios y alertas tienen su propia sección en el menú." />
      <Pestanas valor={tab} onCambio={setTab} opciones={SECCIONES.map(([valor, texto]) => ({ valor, texto }))} />

      {tab === "general" && (!empresa.datos || !params.datos ? <Cargando /> : (
        <div className="grid gap-3 lg:grid-cols-2">
          <Tarjeta titulo="Empresa">
            <div className="grid gap-3 sm:grid-cols-2">
              <Campo etiqueta="Nombre" className="sm:col-span-2"><Entrada value={emp.nombre ?? ""} onChange={(e) => setEmp({ ...emp, nombre: e.target.value })} /></Campo>
              <Campo etiqueta="Código"><Entrada value={emp.codigo ?? ""} disabled /></Campo>
              <Campo etiqueta="RUT"><Entrada value={emp.rut ?? ""} onChange={(e) => setEmp({ ...emp, rut: e.target.value })} /></Campo>
              <Campo etiqueta="Moneda"><Entrada value={emp.moneda ?? ""} onChange={(e) => setEmp({ ...emp, moneda: e.target.value.toUpperCase() })} /></Campo>
              <Campo etiqueta="Zona horaria"><Entrada value={emp.zona_horaria ?? ""} onChange={(e) => setEmp({ ...emp, zona_horaria: e.target.value })} /></Campo>
            </div>
            <Boton className="mt-4" cargando={ocupado} onClick={() => ejecutar(async () => { await api.put("/empresa", { nombre: emp.nombre, rut: emp.rut, moneda: emp.moneda, zona_horaria: emp.zona_horaria }); empresa.recargar(); }, "Empresa actualizada")}>Guardar empresa</Boton>
          </Tarjeta>
          <Tarjeta titulo="Parámetros generales">
            <div className="space-y-3">
              {params.datos.map((p) => {
                const cambiado = valores[p.clave] !== (typeof p.valor === "object" ? JSON.stringify(p.valor) : String(p.valor ?? ""));
                return (
                  <div key={p.clave} className="grid items-end gap-2 sm:grid-cols-[1fr_180px_auto]">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{p.descripcion ?? p.clave}</p>
                      <p className="font-mono text-[11px] text-slate-400">{p.clave}</p>
                    </div>
                    {typeof p.valor === "boolean" ? (
                      <Selector value={valores[p.clave] ?? ""} onChange={(e) => setValores({ ...valores, [p.clave]: e.target.value })} opciones={[{ valor: "true", texto: "Sí" }, { valor: "false", texto: "No" }]} />
                    ) : OPCIONES[p.clave] ? (
                      <Selector value={valores[p.clave] ?? ""} onChange={(e) => setValores({ ...valores, [p.clave]: e.target.value })} opciones={OPCIONES[p.clave].map(([valor, texto]) => ({ valor, texto }))} />
                    ) : (
                      <Entrada value={valores[p.clave] ?? ""} onChange={(e) => setValores({ ...valores, [p.clave]: e.target.value })} />
                    )}
                    <Boton tam="sm" variante={cambiado ? "primario" : "secundario"} disabled={!cambiado} onClick={() => guardarParametro(p)}>Guardar</Boton>
                  </div>
                );
              })}
            </div>
          </Tarjeta>
        </div>
      ))}

      {tab === "temporadas" && (
        <Crud key="t" sinEncabezado titulo="Temporadas" singular="temporada" ruta="/temporadas" permiso="configuracion:editar"
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "fecha_inicio", titulo: "Inicio", render: (t) => fecha(t.fecha_inicio) }, { clave: "fecha_termino", titulo: "Término", render: (t) => fecha(t.fecha_termino) }, { clave: "actual", titulo: "Actual", render: (t) => (t.actual ? "Sí" : "") }, activoCol]}
          campos={[{ clave: "codigo", etiqueta: "Código", requerido: true, ayuda: "Ej.: 2026-2027" }, { clave: "nombre", etiqueta: "Nombre", requerido: true }, { clave: "fecha_inicio", etiqueta: "Inicio", tipo: "fecha", requerido: true }, { clave: "fecha_termino", etiqueta: "Término", tipo: "fecha", requerido: true }, { clave: "actual", etiqueta: "Temporada actual", tipo: "booleano" }, { clave: "activo", etiqueta: "Activa", tipo: "booleano", porDefecto: true }]} />
      )}
      {tab === "motivos" && (
        <Crud key="m" sinEncabezado titulo="Motivos" singular="tipo de ingreso / salida" ruta="/motivos-movimiento" permiso="configuracion:editar"
          columnas={[{ clave: "clase", titulo: "Clase" }, { clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "tipo_movimiento", titulo: "Genera movimiento" }, { clave: "requiere_proceso", titulo: "Exige proceso", render: (m) => (m.requiere_proceso ? "Sí" : "") }, { clave: "requiere_documento", titulo: "Exige documento", render: (m) => (m.requiere_documento ? "Sí" : "") }, activoCol]}
          campos={[
            { clave: "clase", etiqueta: "Clase", tipo: "select", requerido: true, opciones: [{ valor: "INGRESO", texto: "Ingreso" }, { valor: "SALIDA", texto: "Salida" }] },
            { clave: "codigo", etiqueta: "Código", requerido: true },
            { clave: "nombre", etiqueta: "Nombre", requerido: true },
            { clave: "tipo_movimiento_id", etiqueta: "Tipo de movimiento que genera", tipo: "select", requerido: true, opciones: (tipos.datos?.items ?? []).map((t: any) => ({ valor: t.id as number, texto: t.nombre })) },
            { clave: "requiere_proceso", etiqueta: "Exige proceso", tipo: "booleano" },
            { clave: "requiere_documento", etiqueta: "Exige número de documento", tipo: "booleano" },
            { clave: "activo", etiqueta: "Activo", tipo: "booleano", porDefecto: true },
          ]} />
      )}
      {tab === "tipos-movimiento" && (
        <Crud key="tm" sinEncabezado titulo="Tipos de movimiento" singular="tipo de movimiento" ruta="/tipos-movimiento" permiso="configuracion:editar"
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }, { clave: "signo", titulo: "Efecto", render: (t) => (t.signo > 0 ? "Entrada (+)" : t.signo < 0 ? "Salida (−)" : "Según el caso") }, { clave: "es_sistema", titulo: "De sistema", render: (t) => (t.es_sistema ? "Sí" : "") }, activoCol]}
          campos={[{ clave: "codigo", etiqueta: "Código", requerido: true, soloCrear: true }, { clave: "nombre", etiqueta: "Nombre", requerido: true }, { clave: "signo", etiqueta: "Efecto en stock", tipo: "select", requerido: true, opciones: [{ valor: 1, texto: "Entrada (+)" }, { valor: -1, texto: "Salida (−)" }] }, { clave: "activo", etiqueta: "Activo", tipo: "booleano", porDefecto: true }]} />
      )}
      {tab === "tipos-bodega" && (
        <Crud key="tb" sinEncabezado titulo="Tipos de bodega" singular="tipo de bodega" ruta="/tipos-bodega" permiso="configuracion:editar" eliminar={false}
          columnas={[{ clave: "codigo", titulo: "Código" }, { clave: "nombre", titulo: "Nombre" }]}
          campos={[{ clave: "codigo", etiqueta: "Código", requerido: true }, { clave: "nombre", etiqueta: "Nombre", requerido: true }]} />
      )}
      {tab === "etiquetas" && (
        <Crud key="e" sinEncabezado titulo="Plantillas de etiqueta" singular="plantilla de etiqueta" ruta="/plantillas-etiquetas" permiso="configuracion:editar" eliminar={false}
          columnas={[{ clave: "nombre", titulo: "Nombre" }, { clave: "tam", titulo: "Tamaño (mm)", render: (e) => `${e.ancho_mm} × ${e.alto_mm}` }, { clave: "campos", titulo: "Campos impresos", render: (e) => (e.campos ?? []).join(", ") }, { clave: "predeterminada", titulo: "Predeterminada", render: (e) => (e.predeterminada ? "Sí" : "") }]}
          campos={[{ clave: "nombre", etiqueta: "Nombre", requerido: true }, { clave: "predeterminada", etiqueta: "Predeterminada", tipo: "booleano" }, { clave: "ancho_mm", etiqueta: "Ancho (mm)", tipo: "numero", requerido: true, porDefecto: 100 }, { clave: "alto_mm", etiqueta: "Alto (mm)", tipo: "numero", requerido: true, porDefecto: 60 }]} />
      )}
    </>
  );
}
