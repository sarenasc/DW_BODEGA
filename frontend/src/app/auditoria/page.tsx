"use client";

import { useEffect, useState } from "react";
import { Cargando, Encabezado, Entrada, Insignia, Modal, Paginacion, Tabla, Tarjeta } from "@/components/ui";
import { etiqueta, fechaHora } from "@/lib/formato";
import { useDatos } from "@/lib/sesion";

export default function Auditoria() {
  const [f, setF] = useState<Record<string, any>>({});
  const [pagina, setPagina] = useState(1);
  const [ver, setVer] = useState<any>(null);
  const { datos, cargando } = useDatos("/auditoria", { ...f, pagina, tam: 50 });
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave]);
  const claves = ver ? [...new Set([...Object.keys(ver.valor_anterior ?? {}), ...Object.keys(ver.valor_nuevo ?? {})])].filter((k) => JSON.stringify(ver.valor_anterior?.[k]) !== JSON.stringify(ver.valor_nuevo?.[k])) : [];
  return (
    <>
      <Encabezado titulo="Auditoría" descripcion="Quién hizo qué y cuándo: usuario, fecha, IP, dispositivo, entidad, acción, valor anterior, valor nuevo y motivo." />
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 gap-2 border-b border-slate-100 p-3 md:grid-cols-5">
          <Entrada placeholder="Entidad (producto, lote…)" value={f.entidad ?? ""} onChange={(e) => setF({ ...f, entidad: e.target.value.toLowerCase() })} />
          <Entrada placeholder="Id de la entidad" value={f.entidad_id ?? ""} onChange={(e) => setF({ ...f, entidad_id: e.target.value })} />
          <Entrada placeholder="Acción (CREAR, ANULAR…)" value={f.accion ?? ""} onChange={(e) => setF({ ...f, accion: e.target.value.toUpperCase() })} />
          <Entrada type="date" aria-label="Desde" value={f.desde ?? ""} onChange={(e) => setF({ ...f, desde: e.target.value })} />
          <Entrada type="date" aria-label="Hasta" value={f.hasta ? f.hasta.slice(0, 10) : ""} onChange={(e) => setF({ ...f, hasta: e.target.value ? `${e.target.value}T23:59:59` : "" })} />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            onFila={setVer}
            columnas={[
              { clave: "fecha", titulo: "Fecha", render: (a) => fechaHora(a.fecha) },
              { clave: "usuario", titulo: "Usuario", render: (a) => a.usuario ?? "Sistema" },
              { clave: "accion", titulo: "Acción", render: (a) => <Insignia tono={/ANULAR|ELIMINAR|DESACTIVAR/.test(a.accion) ? "rojo" : a.accion === "CREAR" ? "verde" : "azul"}>{etiqueta(a.accion)}</Insignia> },
              { clave: "entidad", titulo: "Entidad", render: (a) => `${etiqueta(a.entidad)} ${a.entidad_id ? `#${a.entidad_id}` : ""}` },
              { clave: "motivo", titulo: "Motivo", ocultarMovil: true, render: (a) => <span className="block max-w-64 truncate">{a.motivo ?? "—"}</span> },
              { clave: "ip", titulo: "IP", ocultarMovil: true },
              { clave: "dispositivo", titulo: "Dispositivo", ocultarMovil: true, render: (a) => <span className="block max-w-48 truncate" title={a.dispositivo ?? ""}>{a.dispositivo ?? "—"}</span> },
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>
      <Modal abierto={!!ver} titulo={ver ? `${etiqueta(ver.accion)} · ${etiqueta(ver.entidad)} ${ver.entidad_id ?? ""}` : ""} onCerrar={() => setVer(null)}>
        {ver && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-600">{fechaHora(ver.fecha)} · {ver.usuario ?? "Sistema"} · {ver.ip ?? "sin IP"}</p>
            {ver.motivo && <p><b>Motivo:</b> {ver.motivo}</p>}
            {claves.length === 0 ? <p className="text-slate-500">Sin detalle de valores.</p> : (
              <table className="tabla w-full">
                <thead><tr><th>Campo</th><th>Valor anterior</th><th>Valor nuevo</th></tr></thead>
                <tbody>
                  {claves.map((k) => (
                    <tr key={k}>
                      <td className="font-medium">{k}</td>
                      <td className="max-w-56 break-words text-slate-500">{ver.valor_anterior?.[k] === undefined ? "—" : JSON.stringify(ver.valor_anterior[k])}</td>
                      <td className="max-w-56 break-words">{ver.valor_nuevo?.[k] === undefined ? "—" : JSON.stringify(ver.valor_nuevo[k])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
