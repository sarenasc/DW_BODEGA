"use client";

import { Plus } from "lucide-react";
import { useState } from "react";
import { Aviso, Boton, Campo, Cargando, cx, Encabezado, Entrada, Estado, Insignia, Interruptor, Modal, Pestanas, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { etiqueta, fechaHora } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

function Casillas({ opciones, valores, onCambio }: { opciones: { id: number; nombre: string }[]; valores: number[]; onCambio: (v: number[]) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {opciones.map((o) => {
        const activo = valores.includes(o.id);
        return (
          <button key={o.id} type="button" onClick={() => onCambio(activo ? valores.filter((x) => x !== o.id) : [...valores, o.id])} className={cx("rounded-lg border px-2.5 py-1 text-sm font-medium transition", activo ? "border-marca-600 bg-marca-600 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50")}>
            {o.nombre}
          </button>
        );
      })}
    </div>
  );
}

export default function Usuarios() {
  const [tab, setTab] = useState("usuarios");
  const usuarios = useDatos("/usuarios");
  const roles = useDatos<any[]>("/roles");
  const permisos = useDatos<any[]>("/permisos");
  const cat = useDatos("/catalogos");
  const [u, setU] = useState<Record<string, any> | null>(null);
  const [rol, setRol] = useState<Record<string, any> | null>(null);
  const [fallo, setFallo] = useState<string | null>(null);
  const { ejecutar, ocupado } = useAccion();

  async function guardarUsuario() {
    setFallo(null);
    try {
      const cuerpo: Record<string, any> = { usuario: u!.usuario, nombre: u!.nombre, email: u!.email || null, activo: u!.activo, roles: u!.roles, todas_bodegas: u!.todas_bodegas, bodegas: u!.bodegas, todas_familias: u!.todas_familias, familias: u!.familias, debe_cambiar_clave: !!u!.debe_cambiar_clave };
      if (u!.clave) cuerpo.clave = u!.clave;
      if (u!.id) await api.put(`/usuarios/${u!.id}`, cuerpo);
      else await api.post("/usuarios", cuerpo);
      setU(null);
      usuarios.recargar();
    } catch (e: any) {
      setFallo(e.message);
    }
  }
  async function guardarRol() {
    setFallo(null);
    try {
      const cuerpo = { codigo: rol!.codigo, nombre: rol!.nombre, descripcion: rol!.descripcion || null, permisos: rol!.permisos };
      if (rol!.id) await api.put(`/roles/${rol!.id}`, cuerpo);
      else await api.post("/roles", cuerpo);
      setRol(null);
      roles.recargar();
    } catch (e: any) {
      setFallo(e.message);
    }
  }
  if (!usuarios.datos || !roles.datos || !permisos.datos) return <Cargando />;
  const modulos = [...new Set(permisos.datos.map((p) => p.modulo))];

  return (
    <>
      <Encabezado titulo="Usuarios y roles" descripcion="Control de acceso por rol (módulo y acción), con alcance opcional por bodega y por familia de productos.">
        <Boton icono={<Plus className="size-4" />} onClick={() => { setFallo(null); tab === "usuarios" ? setU({ usuario: "", nombre: "", email: "", clave: "", activo: true, roles: [], todas_bodegas: true, bodegas: [], todas_familias: true, familias: [] }) : setRol({ codigo: "", nombre: "", descripcion: "", permisos: [] }); }}>
          {tab === "usuarios" ? "Nuevo usuario" : "Nuevo rol"}
        </Boton>
      </Encabezado>
      <Pestanas valor={tab} onCambio={setTab} opciones={[{ valor: "usuarios", texto: "Usuarios", contador: usuarios.datos.total }, { valor: "roles", texto: "Roles y permisos", contador: roles.datos.length }]} />
      {tab === "usuarios" ? (
        <Tarjeta sinRelleno>
          <Tabla
            filas={usuarios.datos.items}
            onFila={(x) => { setFallo(null); setU({ ...x, clave: "" }); }}
            columnas={[
              { clave: "usuario", titulo: "Usuario", render: (x) => <span className="font-medium text-slate-900">{x.usuario}</span> },
              { clave: "nombre", titulo: "Nombre" },
              { clave: "roles_nombres", titulo: "Roles", render: (x) => <span className="flex flex-wrap gap-1">{x.roles_nombres.map((r: string) => <Insignia key={r} tono="azul">{r}</Insignia>)}</span> },
              { clave: "alcance", titulo: "Alcance", ocultarMovil: true, render: (x) => `${x.todas_bodegas ? "Todas las bodegas" : `${x.bodegas.length} bodega(s)`} · ${x.todas_familias ? "todas las familias" : `${x.familias.length} familia(s)`}` },
              { clave: "ultimo_acceso", titulo: "Último acceso", ocultarMovil: true, render: (x) => fechaHora(x.ultimo_acceso) },
              { clave: "activo", titulo: "Estado", render: (x) => <Estado valor={x.activo ? "ACTIVO" : "ANULADO"} /> },
            ]}
          />
        </Tarjeta>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {roles.datos.map((r) => (
            <Tarjeta key={r.id} titulo={r.nombre} accion={<Boton tam="sm" variante="secundario" onClick={() => { setFallo(null); setRol({ ...r }); }}>Editar permisos</Boton>}>
              <p className="text-sm text-slate-600">{r.descripcion}</p>
              <p className="mt-2 text-xs text-slate-500">{r.permisos.length} permisos{r.es_sistema ? " · rol inicial (editable)" : ""}</p>
              <div className="mt-2 flex flex-wrap gap-1">
                {r.permisos.filter((p: string) => permisos.datos!.find((x) => x.codigo === p)?.especial).map((p: string) => <Insignia key={p} tono="ambar">{p}</Insignia>)}
                {r.permisos.includes("costos:ver") ? <Insignia tono="verde">Ve costos</Insignia> : <Insignia>Sin costos</Insignia>}
              </div>
            </Tarjeta>
          ))}
        </div>
      )}

      <Modal abierto={!!u} titulo={u?.id ? `Editar ${u.usuario}` : "Nuevo usuario"} onCerrar={() => setU(null)} pie={<><Boton variante="secundario" onClick={() => setU(null)}>Cancelar</Boton><Boton cargando={ocupado} onClick={guardarUsuario}>Guardar</Boton></>}>
        {u && (
          <div className="grid gap-3 sm:grid-cols-2">
            {fallo && <Aviso tipo="error" className="sm:col-span-2">{fallo}</Aviso>}
            <Campo etiqueta="Usuario" requerido><Entrada value={u.usuario} autoComplete="off" onChange={(e) => setU({ ...u, usuario: e.target.value.trim() })} /></Campo>
            <Campo etiqueta="Nombre" requerido><Entrada value={u.nombre} onChange={(e) => setU({ ...u, nombre: e.target.value })} /></Campo>
            <Campo etiqueta="Correo"><Entrada type="email" value={u.email ?? ""} onChange={(e) => setU({ ...u, email: e.target.value })} /></Campo>
            <Campo etiqueta={u.id ? "Nueva clave (opcional)" : "Clave"} requerido={!u.id} ayuda="Mínimo 8 caracteres, con letras y números."><Entrada type="password" autoComplete="new-password" value={u.clave} onChange={(e) => setU({ ...u, clave: e.target.value })} /></Campo>
            <div className="sm:col-span-2"><p className="mb-1.5 text-xs font-medium text-slate-700">Roles</p><Casillas opciones={roles.datos} valores={u.roles} onCambio={(v) => setU({ ...u, roles: v })} /></div>
            <div className="rounded-lg bg-slate-50 p-3 sm:col-span-2">
              <Interruptor valor={u.todas_bodegas} onCambio={(v) => setU({ ...u, todas_bodegas: v })} etiqueta="Acceso a todas las bodegas" />
              {!u.todas_bodegas && <div className="mt-2"><Casillas opciones={cat.datos?.bodegas ?? []} valores={u.bodegas} onCambio={(v) => setU({ ...u, bodegas: v })} /></div>}
            </div>
            <div className="rounded-lg bg-slate-50 p-3 sm:col-span-2">
              <Interruptor valor={u.todas_familias} onCambio={(v) => setU({ ...u, todas_familias: v })} etiqueta="Acceso a todas las familias de productos" />
              {!u.todas_familias && <div className="mt-2"><Casillas opciones={cat.datos?.familias ?? []} valores={u.familias} onCambio={(v) => setU({ ...u, familias: v })} /></div>}
            </div>
            <Interruptor valor={u.activo} onCambio={(v) => setU({ ...u, activo: v })} etiqueta="Usuario activo" />
          </div>
        )}
      </Modal>

      <Modal abierto={!!rol} titulo={rol?.id ? `Permisos de ${rol.nombre}` : "Nuevo rol"} onCerrar={() => setRol(null)} ancho="max-w-3xl" pie={<><Boton variante="secundario" onClick={() => setRol(null)}>Cancelar</Boton><Boton cargando={ocupado} onClick={guardarRol}>Guardar</Boton></>}>
        {rol && (
          <div className="space-y-4">
            {fallo && <Aviso tipo="error">{fallo}</Aviso>}
            <div className="grid gap-3 sm:grid-cols-3">
              <Campo etiqueta="Código" requerido><Entrada value={rol.codigo} disabled={rol.es_sistema} onChange={(e) => setRol({ ...rol, codigo: e.target.value.toUpperCase() })} /></Campo>
              <Campo etiqueta="Nombre" requerido><Entrada value={rol.nombre} onChange={(e) => setRol({ ...rol, nombre: e.target.value })} /></Campo>
              <Campo etiqueta="Descripción"><Entrada value={rol.descripcion ?? ""} onChange={(e) => setRol({ ...rol, descripcion: e.target.value })} /></Campo>
            </div>
            <div className="space-y-2">
              {modulos.map((m) => (
                <div key={m} className="grid gap-2 rounded-lg border border-slate-200 p-2.5 sm:grid-cols-[130px_1fr]">
                  <p className="text-sm font-semibold text-slate-800">{etiqueta(m)}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {permisos.datos!.filter((p) => p.modulo === m).map((p) => {
                      const activo = rol.permisos.includes(p.codigo);
                      return (
                        <button key={p.codigo} type="button" title={p.descripcion} onClick={() => setRol({ ...rol, permisos: activo ? rol.permisos.filter((x: string) => x !== p.codigo) : [...rol.permisos, p.codigo] })} className={cx("rounded-md border px-2 py-1 text-xs font-medium transition", activo ? (p.especial ? "border-amber-500 bg-amber-500 text-white" : "border-marca-600 bg-marca-600 text-white") : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50")}>
                          {etiqueta(p.accion)}{p.especial ? " ★" : ""}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500">★ Permiso especial (autoriza excepciones: omitir FIFO, consumir lotes bloqueados, cerrar sin sincronizar…). Pase el cursor sobre un permiso para ver su descripción.</p>
            {rol.id && !rol.es_sistema && <Boton variante="fantasma" onClick={() => confirm("¿Eliminar este rol?") && ejecutar(async () => { await api.del(`/roles/${rol.id}`); setRol(null); roles.recargar(); })}>Eliminar rol</Boton>}
          </div>
        )}
      </Modal>
    </>
  );
}
