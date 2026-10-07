"use client";

import { Ban, Check, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { EntradaCodigo, pitido, vibrar } from "@/components/Escaner";
import { Aviso, Boton, Cargando, cx, Encabezado, Entrada, Estado, Indicador, Modal, Tabla, Tarjeta, useAccion } from "@/components/ui";
import { api } from "@/lib/api";
import { clp, fechaHora, num } from "@/lib/formato";
import { useDatos, useParametro, useSesion } from "@/lib/sesion";

export default function DetalleConteo() {
  const id = useParametro("id");
  const { puede } = useSesion();
  const { datos: c, setDatos, recargar, error } = useDatos(id ? `/conteos/${id}` : null);
  const [actual, setActual] = useState<any>(null);
  const [cantidad, setCantidad] = useState("");
  const [fallo, setFallo] = useState<string | null>(null);
  const [ultimo, setUltimo] = useState<any>(null);
  const { ejecutar, ocupado } = useAccion();
  if (error) return <Aviso tipo="error">{error}</Aviso>;
  if (!c) return <Cargando />;
  const abierto = c.estado === "ABIERTO";
  const costos = puede("costos:ver");

  async function leer(codigo: string) {
    setFallo(null);
    try {
      const e = await api.get("/existencias/por-codigo", { codigo });
      setActual(e);
      setCantidad("");
      vibrar(40);
      pitido(true);
    } catch (err: any) {
      setFallo(err.message);
      pitido(false);
    }
  }
  const registrar = () =>
    ejecutar(async () => {
      const r = await api.post(`/conteos/${c.id}/contar`, { existencia_id: actual.id, cantidad: Number(cantidad.replace(",", ".")) });
      setUltimo(r.linea);
      setActual(null);
      recargar();
    });

  return (
    <>
      <Encabezado titulo={`Conteo ${c.numero}`} descripcion={`${c.bodega} · ${c.ubicacion ?? "toda la bodega"} · ${fechaHora(c.fecha)} · ${c.usuario ?? ""}`} volver="/conteos/">
        <Estado valor={c.estado} />
        {abierto && puede("conteos:contar") && (
          <>
            <Boton variante="secundario" icono={<Check className="size-4" />} onClick={() => { const cero = c.contadas < c.lineas && confirm(`Quedan ${c.lineas - c.contadas} existencia(s) sin contar.\n\nAceptar: registrarlas como NO ENCONTRADAS (cantidad 0).\nCancelar: dejarlas sin ajuste.`); ejecutar(async () => setDatos(await api.post(`/conteos/${c.id}/cerrar`, {}, { no_contadas_en_cero: cero })), "Conteo enviado a revisión"); }}>Terminar conteo</Boton>
            <Boton variante="fantasma" icono={<Ban className="size-4 text-rose-600" />} onClick={() => confirm("¿Anular el conteo?") && ejecutar(async () => { await api.post(`/conteos/${c.id}/anular`); recargar(); })}>Anular</Boton>
          </>
        )}
        {c.estado === "EN_REVISION" && puede("conteos:autorizar") && <Boton icono={<ShieldCheck className="size-4" />} cargando={ocupado} onClick={() => confirm(`Se generarán los ajustes de ${c.con_diferencia} existencia(s) con diferencia. ¿Autorizar?`) && ejecutar(async () => setDatos(await api.post(`/conteos/${c.id}/autorizar`)), "Ajustes generados")}>Autorizar ajustes</Boton>}
      </Encabezado>
      {c.estado === "EN_REVISION" && <Aviso tipo="alerta" className="mb-3">En revisión: el stock aún no cambia. Los ajustes se generan al autorizar{puede("conteos:autorizar") ? "." : " (requiere permiso de autorización)."}</Aviso>}
      <div className="mb-3 grid grid-cols-3 gap-3">
        <Indicador titulo="Existencias" valor={c.lineas} />
        <Indicador titulo="Contadas" valor={c.contadas} tono={c.contadas === c.lineas ? "ok" : "normal"} />
        <Indicador titulo="Con diferencia" valor={c.con_diferencia} tono={c.con_diferencia ? "peligro" : "ok"} />
      </div>

      {abierto && puede("conteos:contar") && (
        <Tarjeta titulo="Escanear y contar" className="mb-3">
          {fallo && <Aviso tipo="error" className="mb-3">{fallo}</Aviso>}
          {ultimo && (
            <Aviso tipo={Number(ultimo.diferencia) === 0 ? "exito" : "alerta"} className="mb-3" titulo={`${ultimo.codigo_publico} · ${ultimo.producto}`}>
              Sistema {num(ultimo.cantidad_sistema)} · contado {num(ultimo.cantidad_contada)} · diferencia <b>{Number(ultimo.diferencia) > 0 ? "+" : ""}{num(ultimo.diferencia)} {ultimo.unidad}</b>
            </Aviso>
          )}
          <EntradaCodigo onCodigo={leer} activa={!actual} />
        </Tarjeta>
      )}

      <Tarjeta titulo="Detalle" sinRelleno>
        <Tabla
          filas={c.detalles}
          onFila={abierto ? (x) => leer(x.codigo_publico) : undefined}
          columnas={[
            { clave: "codigo_publico", titulo: "Existencia", render: (x) => <span className="cifra font-medium">{x.codigo_publico}</span> },
            { clave: "producto", titulo: "Producto", render: (x) => <>{x.producto}<span className="block text-xs text-slate-500">Lote {x.lote ?? "—"} · {x.ubicacion ?? "sin ubicación"}</span></> },
            { clave: "cantidad_sistema", titulo: "Sistema", alinear: "derecha", render: (x) => `${num(x.cantidad_sistema)} ${x.unidad}` },
            { clave: "cantidad_contada", titulo: "Contado", alinear: "derecha", render: (x) => (x.cantidad_contada == null ? <span className="text-slate-400">Pendiente</span> : num(x.cantidad_contada)) },
            { clave: "diferencia", titulo: "Diferencia", alinear: "derecha", render: (x) => (x.diferencia == null ? "—" : <b className={cx(Number(x.diferencia) < 0 && "text-rose-700", Number(x.diferencia) > 0 && "text-amber-700")}>{Number(x.diferencia) > 0 ? "+" : ""}{num(x.diferencia)}</b>) },
            ...(costos ? [{ clave: "valor_diferencia", titulo: "Valor dif.", alinear: "derecha" as const, ocultarMovil: true, render: (x: any) => (x.valor_diferencia ? clp(x.valor_diferencia) : "—") }] : []),
            { clave: "observacion", titulo: "Observación", ocultarMovil: true },
            { clave: "movimiento_ajuste_id", titulo: "Ajuste", render: (x) => (x.movimiento_ajuste_id ? <Estado valor="OK" /> : "") },
          ]}
        />
      </Tarjeta>

      <Modal abierto={!!actual} titulo={actual?.codigo_publico} onCerrar={() => setActual(null)} ancho="max-w-md"
        pie={<Boton tam="lg" className="w-full" cargando={ocupado} disabled={cantidad === "" || Number(cantidad.replace(",", ".")) < 0} onClick={registrar}>Registrar cantidad</Boton>}>
        {actual && (
          <div className="space-y-3">
            <p className="text-lg font-semibold text-slate-900">{actual.producto}</p>
            <p className="text-sm text-slate-600">Lote {actual.lote ?? "—"} · {actual.ubicacion ?? actual.bodega}</p>
            <label className="block">
              <span className="mb-1 block text-xs font-medium text-slate-700">Cantidad encontrada ({actual.unidad})</span>
              <Entrada inputMode="decimal" autoFocus className="!h-16 text-center !text-3xl font-semibold" value={cantidad} onChange={(e) => setCantidad(e.target.value)} onKeyDown={(e) => e.key === "Enter" && cantidad !== "" && registrar()} />
            </label>
            <p className="text-xs text-slate-500">La diferencia contra el sistema se mostrará al registrar. Si no se encuentra, registre 0.</p>
          </div>
        )}
      </Modal>
    </>
  );
}
