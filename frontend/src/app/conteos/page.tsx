"use client";

import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Boton, Campo, Cargando, Encabezado, Entrada, Estado, Modal, Selector, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { fechaHora } from "@/lib/formato";
import { useDatos, useSesion } from "@/lib/sesion";

export default function Conteos() {
  const router = useRouter();
  const { puede } = useSesion();
  const cat = useDatos("/catalogos");
  const { datos } = useDatos("/conteos", { tam: 100 });
  const [nuevo, setNuevo] = useState<Record<string, any> | null>(null);
  const ubic = useDatos(nuevo?.bodega_id ? "/ubicaciones" : null, { bodega_id: nuevo?.bodega_id });
  const { ejecutar, ocupado } = useAccion();
  return (
    <>
      <Encabezado titulo="Inventario físico" descripcion="Seleccione bodega y ubicación, escanee, ingrese la cantidad encontrada, compare con el sistema y genere el ajuste tras la autorización.">
        {puede("conteos:contar") && <Boton icono={<Plus className="size-4" />} onClick={() => setNuevo({ bodega_id: cat.datos?.bodegas[0]?.id ?? "", ubicacion_id: "", observaciones: "" })}>Nuevo conteo</Boton>}
      </Encabezado>
      <Tarjeta sinRelleno>
        {!datos ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos.items}
            vacio="Aún no hay conteos."
            onFila={(c) => router.push(`/conteos/detalle/?id=${c.id}`)}
            columnas={[
              { clave: "numero", titulo: "Conteo", render: (c) => <span className="cifra font-medium">{c.numero}</span> },
              { clave: "fecha", titulo: "Fecha", render: (c) => fechaHora(c.fecha) },
              { clave: "bodega", titulo: "Bodega" },
              { clave: "ubicacion", titulo: "Ubicación", render: (c) => c.ubicacion ?? "Toda la bodega" },
              { clave: "avance", titulo: "Avance", alinear: "derecha", render: (c) => `${c.contadas} / ${c.lineas}` },
              { clave: "con_diferencia", titulo: "Con diferencia", alinear: "derecha", render: (c) => (c.con_diferencia ? <b className="text-rose-700">{c.con_diferencia}</b> : "0") },
              { clave: "usuario", titulo: "Usuario", ocultarMovil: true },
              { clave: "estado", titulo: "Estado", render: (c) => <Estado valor={c.estado} /> },
            ]}
          />
        )}
      </Tarjeta>
      <Modal abierto={!!nuevo} titulo="Nuevo conteo" onCerrar={() => setNuevo(null)} ancho="max-w-md"
        pie={<Boton cargando={ocupado} onClick={() => ejecutar(async () => { const c = await api.post("/conteos", { bodega_id: Number(nuevo!.bodega_id), ubicacion_id: nuevo!.ubicacion_id ? Number(nuevo!.ubicacion_id) : null, observaciones: nuevo!.observaciones || null }); router.push(`/conteos/detalle/?id=${c.id}`); })}>Iniciar conteo</Boton>}>
        {nuevo && (
          <div className="grid gap-3">
            <Campo etiqueta="Bodega" requerido><Selector value={nuevo.bodega_id} onChange={(e) => setNuevo({ ...nuevo, bodega_id: e.target.value, ubicacion_id: "" })} opciones={(cat.datos?.bodegas ?? []).map((b: any) => ({ valor: b.id, texto: b.nombre }))} /></Campo>
            <Campo etiqueta="Ubicación" ayuda="Un rack o zona incluye todas sus posiciones."><Selector vacio="Toda la bodega" value={nuevo.ubicacion_id} onChange={(e) => setNuevo({ ...nuevo, ubicacion_id: e.target.value })} opciones={(ubic.datos ?? []).map((u: any) => ({ valor: u.id, texto: u.codigo_completo }))} /></Campo>
            <Campo etiqueta="Observaciones"><Entrada value={nuevo.observaciones} onChange={(e) => setNuevo({ ...nuevo, observaciones: e.target.value })} /></Campo>
          </div>
        )}
      </Modal>
    </>
  );
}
