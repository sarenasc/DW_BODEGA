"use client";

// Pagina de mantenimiento generica para maestros: listado con busqueda, alta, edicion y baja logica.

import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useDatos, useSesion } from "@/lib/sesion";
import { Aviso, Boton, Campo, Cargando, type Columna, Encabezado, Entrada, Estado, Interruptor, Modal, Paginacion, Selector, Tabla, Tarjeta, useAccion } from "./ui";

export type CampoCrud = {
  clave: string;
  etiqueta: string;
  tipo?: "texto" | "numero" | "fecha" | "booleano" | "heredable" | "select" | "area";
  opciones?: { valor: string | number; texto: string }[];
  requerido?: boolean;
  ayuda?: string;
  ancho?: 1 | 2;
  porDefecto?: any;
  soloCrear?: boolean;
  seccion?: string;
};

/** Convierte el formulario al cuerpo de la API: vacio -> null, numeros como numero. */
export function aCuerpo(campos: CampoCrud[], f: Record<string, any>, editando: boolean): Record<string, any> {
  const cuerpo: Record<string, any> = {};
  for (const c of campos) {
    if (editando && c.soloCrear) continue;
    let v = f[c.clave];
    if (c.tipo === "heredable") v = v === "" || v === undefined ? null : v === "true" || v === true;
    else if (c.tipo === "booleano") v = !!v;
    else if (v === "" || v === undefined) v = null;
    else if (c.tipo === "numero") v = Number(v);
    else if (c.tipo === "select" && typeof c.opciones?.[0]?.valor === "number") v = Number(v);
    cuerpo[c.clave] = v;
  }
  return cuerpo;
}

export function CampoFormulario({ campo: c, valor, onCambio }: { campo: CampoCrud; valor: any; onCambio: (v: any) => void }) {
  if (c.tipo === "booleano") return <Interruptor valor={!!valor} onCambio={onCambio} etiqueta={c.etiqueta} />;
  return (
    <Campo etiqueta={c.etiqueta} requerido={c.requerido} ayuda={c.ayuda}>
      {c.tipo === "select" ? (
        <Selector value={valor ?? ""} onChange={(e) => onCambio(e.target.value)} opciones={c.opciones ?? []} vacio={c.requerido ? "Seleccione…" : "—"} />
      ) : c.tipo === "heredable" ? (
        <Selector value={valor === null || valor === undefined ? "" : String(valor)} onChange={(e) => onCambio(e.target.value)} vacio="Heredar" opciones={[{ valor: "true", texto: "Sí" }, { valor: "false", texto: "No" }]} />
      ) : c.tipo === "area" ? (
        <textarea className="campo" rows={3} value={valor ?? ""} onChange={(e) => onCambio(e.target.value)} />
      ) : (
        <Entrada type={c.tipo === "fecha" ? "date" : "text"} inputMode={c.tipo === "numero" ? "decimal" : undefined} value={valor ?? ""} onChange={(e) => onCambio(e.target.value)} />
      )}
    </Campo>
  );
}

export function FormularioCampos({ campos, valores, onCambio }: { campos: CampoCrud[]; valores: Record<string, any>; onCambio: (clave: string, v: any) => void }) {
  const secciones = [...new Set(campos.map((c) => c.seccion ?? ""))];
  return (
    <div className="space-y-5">
      {secciones.map((s) => (
        <div key={s}>
          {s && <p className="mb-2 border-b border-slate-100 pb-1 text-xs font-semibold tracking-wide text-slate-500 uppercase">{s}</p>}
          <div className="grid gap-x-4 gap-y-3 sm:grid-cols-2">
            {campos
              .filter((c) => (c.seccion ?? "") === s)
              .map((c) => (
                <div key={c.clave} className={c.ancho === 2 ? "sm:col-span-2" : ""}>
                  <CampoFormulario campo={c} valor={valores[c.clave]} onCambio={(v) => onCambio(c.clave, v)} />
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

type Props = {
  titulo: string;
  descripcion?: string;
  ruta: string;
  singular: string;
  columnas: Columna[];
  campos: CampoCrud[];
  permiso: string;
  filtros?: Record<string, any>;
  barra?: React.ReactNode;
  sinEncabezado?: boolean;
  onFila?: (fila: any) => void;
  tam?: number;
  acciones?: (fila: any, recargar: () => void) => React.ReactNode;
  valoresIniciales?: Record<string, any>;
  eliminar?: boolean;
};

export function Crud({ titulo, descripcion, ruta, singular, columnas, campos, permiso, filtros, barra, sinEncabezado, onFila, tam = 50, acciones, valoresIniciales, eliminar = true }: Props) {
  const { puede } = useSesion();
  const editable = puede(permiso);
  const [q, setQ] = useState("");
  const [pagina, setPagina] = useState(1);
  const [soloActivos, setSoloActivos] = useState(true);
  const { datos, cargando, error, recargar } = useDatos(ruta, { q, pagina, tam, activo: soloActivos ? true : undefined, ...filtros });
  const [form, setForm] = useState<Record<string, any> | null>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  const { ejecutar, ocupado } = useAccion();
  const clavesFiltro = JSON.stringify(filtros ?? {});
  useEffect(() => setPagina(1), [q, clavesFiltro]);

  const nuevo = () => {
    setFallo(null);
    setForm({ ...Object.fromEntries(campos.filter((c) => c.porDefecto !== undefined).map((c) => [c.clave, c.porDefecto])), ...valoresIniciales });
  };

  async function guardar() {
    if (!form) return;
    const falta = campos.find((c) => c.requerido && (form[c.clave] === "" || form[c.clave] === null || form[c.clave] === undefined));
    if (falta) return setFallo(`Complete el campo "${falta.etiqueta}".`);
    setFallo(null);
    try {
      const cuerpo = aCuerpo(campos, form, !!form.id);
      if (form.id) await api.put(`${ruta}/${form.id}`, cuerpo);
      else await api.post(ruta, cuerpo);
      setForm(null);
      recargar();
    } catch (e: any) {
      setFallo(e.message);
    }
  }

  const cols: Columna[] = [
    ...columnas,
    ...(editable
      ? [
          {
            clave: "_acciones",
            titulo: "",
            alinear: "derecha" as const,
            render: (f: any) => (
              <span className="flex justify-end gap-1" onClick={(e) => e.stopPropagation()}>
                {acciones?.(f, recargar)}
                <Boton variante="fantasma" tam="sm" aria-label="Editar" onClick={() => { setFallo(null); setForm({ ...f }); }}>
                  <Pencil className="size-4" />
                </Boton>
                {eliminar && (f.activo ?? f.activa ?? true) && (
                  <Boton variante="fantasma" tam="sm" aria-label="Desactivar" onClick={() => confirm(`¿Desactivar ${singular} "${f.nombre ?? f.codigo ?? ""}"?`) && ejecutar(async () => { await api.del(`${ruta}/${f.id}`); recargar(); }, "Registro desactivado")}>
                    <Trash2 className="size-4 text-rose-600" />
                  </Boton>
                )}
              </span>
            ),
          },
        ]
      : []),
  ];

  return (
    <>
      {!sinEncabezado && (
        <Encabezado titulo={titulo} descripcion={descripcion}>
          {editable && (
            <Boton icono={<Plus className="size-4" />} onClick={nuevo}>
              Nuevo
            </Boton>
          )}
        </Encabezado>
      )}
      <Tarjeta sinRelleno>
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 p-3">
          <div className="relative min-w-48 flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
            <Entrada value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar…" className="pl-9" aria-label={`Buscar ${titulo}`} />
          </div>
          {barra}
          <Interruptor valor={soloActivos} onCambio={setSoloActivos} etiqueta="Solo activos" />
          {sinEncabezado && editable && (
            <Boton icono={<Plus className="size-4" />} onClick={nuevo}>
              Nuevo
            </Boton>
          )}
        </div>
        {error && <Aviso tipo="error" className="m-3">{error}</Aviso>}
        {!datos && cargando ? <Cargando /> : <Tabla columnas={cols} filas={datos?.items ?? []} onFila={onFila} />}
        {datos && <Paginacion pagina={pagina} tam={tam} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>
      <Modal
        abierto={!!form}
        titulo={`${form?.id ? "Editar" : "Nuevo"} ${singular}`}
        onCerrar={() => setForm(null)}
        pie={
          <>
            <Boton variante="secundario" onClick={() => setForm(null)}>
              Cancelar
            </Boton>
            <Boton onClick={guardar} cargando={ocupado}>
              Guardar
            </Boton>
          </>
        }
      >
        {fallo && <Aviso tipo="error" className="mb-4">{fallo}</Aviso>}
        {form && <FormularioCampos campos={campos.filter((c) => !(form.id && c.soloCrear))} valores={form} onCambio={(k, v) => setForm((a) => ({ ...a!, [k]: v }))} />}
      </Modal>
    </>
  );
}

export const activoCol: Columna = { clave: "activo", titulo: "Estado", render: (f) => <Estado valor={(f.activo ?? f.activa) ? "ACTIVO" : "ANULADO"} /> };
