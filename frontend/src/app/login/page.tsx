"use client";

import { Warehouse } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, Entrada } from "@/components/ui";
import { api } from "@/lib/api";
import { useParametro, useSesion } from "@/lib/sesion";

export default function Login() {
  const { usuario, entrar } = useSesion();
  const router = useRouter();
  const volver = useParametro("volver");
  const [nombre, setNombre] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [demo, setDemo] = useState(false);

  useEffect(() => {
    api.get("/instalacion/estado").then((e) => setDemo(e.modo_demo)).catch(() => {});
  }, []);
  useEffect(() => {
    if (usuario) router.replace(volver && volver.startsWith("/") && !volver.startsWith("//") ? volver : "/");
  }, [usuario, volver, router]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError(null);
    try {
      await entrar(nombre, clave);
    } catch (err: any) {
      setError(err.message);
      setOcupado(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center bg-panel p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center text-center">
          <span className="mb-3 flex size-14 items-center justify-center rounded-2xl bg-marca-500 text-white shadow-lg">
            <Warehouse className="size-7" />
          </span>
          <h1 className="text-2xl font-semibold text-white">WMS Bodegas</h1>
          <p className="text-sm text-slate-400">Inventario, lotes, QR y procesos productivos</p>
        </div>
        <form onSubmit={enviar} className="space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
          {error && <Aviso tipo="error">{error}</Aviso>}
          <Campo etiqueta="Usuario">
            <Entrada value={nombre} onChange={(e) => setNombre(e.target.value)} autoComplete="username" autoCapitalize="none" autoFocus required className="!h-12" />
          </Campo>
          <Campo etiqueta="Clave">
            <Entrada type="password" value={clave} onChange={(e) => setClave(e.target.value)} autoComplete="current-password" required className="!h-12" />
          </Campo>
          <Boton type="submit" tam="lg" cargando={ocupado} className="w-full">
            Entrar
          </Boton>
          {demo && (
            <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              <p className="mb-1.5 font-semibold">Modo Demo — usuarios de prueba (clave: Demo1234)</p>
              <div className="grid grid-cols-2 gap-1.5">
                {[
                  ["admin", "Administrador"],
                  ["jefe", "Jefe de área"],
                  ["bodega", "Digitador (sin costos)"],
                  ["lector", "Solo lectura"],
                ].map(([u, rol]) => (
                  <button
                    key={u}
                    type="button"
                    onClick={() => {
                      setNombre(u);
                      setClave("Demo1234");
                    }}
                    className="rounded-md border border-amber-200 bg-white px-2 py-1.5 text-left hover:border-amber-400"
                  >
                    <span className="block font-semibold">{u}</span>
                    <span className="block text-[10px] text-amber-700">{rol}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
