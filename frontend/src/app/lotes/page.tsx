"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Cargando, Encabezado, Entrada, Estado, Interruptor, Paginacion, Selector, Tabla, Tarjeta } from "@/components/ui";
import { clp, etiqueta, fecha, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

const ESTADOS = ["DISPONIBLE", "BLOQUEADO", "CUARENTENA", "VENCIDO", "AGOTADO", "ANULADO"];

export default function Lotes() {
  const router = useRouter();
  const { puede } = useSesion();
  const estadoInicial = useParametro("estado");
  const vence = useParametro("vence");
  const [f, setF] = useState<Record<string, any>>({ con_stock: true });
  const [pagina, setPagina] = useState(1);
  useEffect(() => {
    const limite = vence ? new Date(Date.now() + Number(vence) * 86_400_000).toISOString().slice(0, 10) : undefined;
    setF((a) => ({ ...a, estado: estadoInicial ?? a.estado, vence_antes: limite ?? a.vence_antes }));
  }, [estadoInicial, vence]);
  const { datos, cargando } = useDatos("/lotes", { ...f, pagina, tam: 50 });
  const clave = JSON.stringify(f);
  useEffect(() => setPagina(1), [clave]);
  const hoy = new Date().toISOString().slice(0, 10);

  return (
    <>
      <Encabezado titulo="Lotes" descripcion="Lote interno: identidad y trazabilidad. Un lote puede tener varias existencias en distintas ubicaciones." />
      <Tarjeta sinRelleno>
        <div className="grid grid-cols-2 items-center gap-2 border-b border-slate-100 p-3 md:grid-cols-5">
          <Entrada placeholder="Lote, producto o referencia…" value={f.q ?? ""} onChange={(e) => setF({ ...f, q: e.target.value })} className="col-span-2" />
          <Selector vacio="Todos los estados" value={f.estado ?? ""} onChange={(e) => setF({ ...f, estado: e.target.value })} opciones={ESTADOS.map((s) => ({ valor: s, texto: etiqueta(s) }))} />
          <Entrada type="date" aria-label="Vence antes de" title="Vence antes de" value={f.vence_antes ?? ""} onChange={(e) => setF({ ...f, vence_antes: e.target.value })} />
          <Interruptor valor={!!f.con_stock} onCambio={(v) => setF({ ...f, con_stock: v || undefined })} etiqueta="Solo con stock" />
        </div>
        {!datos && cargando ? (
          <Cargando />
        ) : (
          <Tabla
            filas={datos?.items ?? []}
            onFila={(l) => router.push(`/lotes/detalle/?id=${l.id}`)}
            columnas={[
              { clave: "codigo", titulo: "Lote interno", render: (l) => <span className="cifra font-semibold text-slate-900">{l.codigo}</span> },
              { clave: "producto", titulo: "Producto", render: (l) => <>{l.producto}<span className="block text-xs text-slate-500">{l.producto_codigo}</span></> },
              { clave: "fecha_ingreso", titulo: "Ingreso", ocultarMovil: true, render: (l) => fecha(l.fecha_ingreso) },
              { clave: "fecha_vencimiento", titulo: "Vence", render: (l) => <span className={l.fecha_vencimiento && l.fecha_vencimiento < hoy ? "font-semibold text-rose-700" : ""}>{fecha(l.fecha_vencimiento)}</span> },
              { clave: "cantidad_disponible", titulo: "Disponible", alinear: "derecha", render: (l) => <><b>{num(l.cantidad_disponible)}</b> <span className="text-xs text-slate-500">/ {num(l.cantidad_inicial)} {l.unidad}</span></> },
              { clave: "existencias", titulo: "Existencias", alinear: "derecha", ocultarMovil: true },
              ...(puede("costos:ver") ? [{ clave: "valor_disponible", titulo: "Valor", alinear: "derecha" as const, ocultarMovil: true, render: (l: any) => clp(l.valor_disponible) }] : []),
              { clave: "estado", titulo: "Estado", render: (l) => <Estado valor={l.estado} /> },
            ]}
          />
        )}
        {datos && <Paginacion pagina={pagina} tam={50} total={datos.total} onCambio={setPagina} />}
      </Tarjeta>
    </>
  );
}
