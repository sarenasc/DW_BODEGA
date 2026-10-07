"use client";

import { Check, CheckCircle2, Database, Warehouse } from "lucide-react";
import { useEffect, useState } from "react";
import { Aviso, Boton, Campo, cx, Entrada, Interruptor, Selector } from "@/components/ui";
import { api } from "@/lib/api";

const PASOS = ["Idioma", "Empresa", "Base de datos", "Probar conexión", "Crear estructura", "Administrador", "Configuración inicial", "Entrar"];

export default function Instalar() {
  const [paso, setPaso] = useState(0);
  const [motores, setMotores] = useState<any[]>([]);
  const [idioma, setIdioma] = useState("es");
  const [empresa, setEmpresa] = useState({ codigo: "EMP", nombre: "", rut: "", moneda: "CLP", zona_horaria: "America/Santiago" });
  const [bd, setBd] = useState({ motor: "", servidor: "localhost", puerto: "", usuario: "", clave: "", base_datos: "wms", parametros: "" });
  const [admin, setAdmin] = useState({ usuario: "admin", nombre: "", email: "", clave: "", repetir: "" });
  const [temporada, setTemporada] = useState(() => {
    const d = new Date();
    const a = d.getMonth() >= 6 ? d.getFullYear() : d.getFullYear() - 1;
    return `${a}-${a + 1}`;
  });
  const [datosDemo, setDatosDemo] = useState(false);
  const [prueba, setPrueba] = useState<any>(null);
  const [estructura, setEstructura] = useState<string[] | null>(null);
  const [final, setFinal] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    api.get("/instalacion/estado").then((e) => {
      if (e.instalado) window.location.href = "/login/";
      setMotores(e.motores);
    });
  }, []);

  const esDemo = bd.motor === "demo";
  const cuerpoBd = () => ({
    motor: bd.motor,
    servidor: bd.servidor,
    puerto: bd.puerto ? Number(bd.puerto) : null,
    usuario: bd.usuario,
    clave: bd.clave,
    base_datos: esDemo ? "" : bd.base_datos,
    parametros: Object.fromEntries(bd.parametros.split(/[;\n]/).map((p) => p.split("=").map((x) => x.trim())).filter((p) => p.length === 2 && p[0])),
  });

  async function accion(f: () => Promise<void>) {
    setOcupado(true);
    setError(null);
    try {
      await f();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setOcupado(false);
    }
  }

  const probar = () => accion(async () => setPrueba(await api.post("/instalacion/probar-conexion", cuerpoBd())));
  const crear = () => accion(async () => setEstructura((await api.post("/instalacion/crear-estructura", cuerpoBd())).pasos));
  const instalar = () =>
    accion(async () => {
      const r = await api.post("/instalacion/ejecutar", {
        idioma,
        empresa: { ...empresa, rut: empresa.rut || null },
        bd: cuerpoBd(),
        admin: { usuario: admin.usuario, nombre: admin.nombre, email: admin.email || null, clave: admin.clave },
        temporada: temporada || null,
        datos_demo: datosDemo,
      });
      setFinal(r.pasos);
      setPaso(7);
    });

  const valido = [
    true,
    empresa.nombre.trim().length > 1 && empresa.codigo.trim().length > 0,
    !!bd.motor && (esDemo || (!!bd.servidor && !!bd.base_datos)),
    !!prueba?.ok,
    !!estructura,
    admin.usuario.length > 2 && admin.nombre.length > 1 && admin.clave.length >= 8 && admin.clave === admin.repetir,
    true,
    true,
  ][paso];

  return (
    <div className="min-h-dvh bg-panel p-4 sm:p-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center gap-3 text-white">
          <span className="flex size-11 items-center justify-center rounded-xl bg-marca-500">
            <Warehouse className="size-6" />
          </span>
          <div>
            <h1 className="text-xl font-semibold">Instalación de WMS Bodegas</h1>
            <p className="text-sm text-slate-400">
              Paso {paso + 1} de {PASOS.length}: {PASOS[paso]}
            </p>
          </div>
        </div>
        <ol className="mb-5 flex gap-1.5">
          {PASOS.map((p, i) => (
            <li key={p} title={p} className={cx("h-1.5 flex-1 rounded-full", i < paso ? "bg-marca-500" : i === paso ? "bg-white" : "bg-white/20")} />
          ))}
        </ol>
        <div className="rounded-2xl bg-white p-5 shadow-2xl sm:p-7">
          {error && (
            <Aviso tipo="error" className="mb-4">
              {error}
            </Aviso>
          )}

          {paso === 0 && (
            <Campo etiqueta="Idioma de la aplicación">
              <Selector value={idioma} onChange={(e) => setIdioma(e.target.value)} opciones={[{ valor: "es", texto: "Español" }]} />
            </Campo>
          )}

          {paso === 1 && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Nombre de la empresa" requerido className="sm:col-span-2">
                <Entrada value={empresa.nombre} onChange={(e) => setEmpresa({ ...empresa, nombre: e.target.value })} autoFocus />
              </Campo>
              <Campo etiqueta="Código corto" requerido ayuda="Se usa en los lotes que incluyan el código de empresa.">
                <Entrada value={empresa.codigo} maxLength={20} onChange={(e) => setEmpresa({ ...empresa, codigo: e.target.value.toUpperCase() })} />
              </Campo>
              <Campo etiqueta="RUT">
                <Entrada value={empresa.rut} onChange={(e) => setEmpresa({ ...empresa, rut: e.target.value })} />
              </Campo>
              <Campo etiqueta="Moneda">
                <Selector value={empresa.moneda} onChange={(e) => setEmpresa({ ...empresa, moneda: e.target.value })} opciones={["CLP", "USD", "EUR", "PEN", "ARS", "MXN", "COP"].map((m) => ({ valor: m, texto: m }))} />
              </Campo>
              <Campo etiqueta="Zona horaria">
                <Entrada value={empresa.zona_horaria} onChange={(e) => setEmpresa({ ...empresa, zona_horaria: e.target.value })} />
              </Campo>
            </div>
          )}

          {paso === 2 && (
            <div className="space-y-4">
              <p className="text-sm font-medium text-slate-800">¿Qué base de datos desea utilizar?</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {motores.map((m) => (
                  <button
                    key={m.codigo}
                    type="button"
                    onClick={() => {
                      setBd({ ...bd, motor: m.codigo, puerto: m.puerto ? String(m.puerto) : "" });
                      setPrueba(null);
                      setEstructura(null);
                    }}
                    className={cx("flex items-center gap-3 rounded-xl border-2 p-3 text-left transition", bd.motor === m.codigo ? "border-marca-500 bg-marca-50" : "border-slate-200 hover:border-slate-300")}
                  >
                    <span className={cx("flex size-5 items-center justify-center rounded-full border-2", bd.motor === m.codigo ? "border-marca-600 bg-marca-600 text-white" : "border-slate-300")}>
                      {bd.motor === m.codigo && <Check className="size-3" />}
                    </span>
                    <Database className="size-5 text-slate-500" />
                    <span className="text-sm font-medium text-slate-800">{m.nombre}</span>
                  </button>
                ))}
              </div>
              {bd.motor && !esDemo && (
                <div className="grid gap-4 sm:grid-cols-6">
                  <Campo etiqueta="Servidor" requerido className="sm:col-span-4">
                    <Entrada value={bd.servidor} onChange={(e) => setBd({ ...bd, servidor: e.target.value })} />
                  </Campo>
                  <Campo etiqueta="Puerto" className="sm:col-span-2">
                    <Entrada inputMode="numeric" value={bd.puerto} onChange={(e) => setBd({ ...bd, puerto: e.target.value.replace(/\D/g, "") })} />
                  </Campo>
                  <Campo etiqueta="Usuario" className="sm:col-span-3">
                    <Entrada value={bd.usuario} autoComplete="off" onChange={(e) => setBd({ ...bd, usuario: e.target.value })} />
                  </Campo>
                  <Campo etiqueta="Contraseña" className="sm:col-span-3">
                    <Entrada type="password" value={bd.clave} autoComplete="new-password" onChange={(e) => setBd({ ...bd, clave: e.target.value })} />
                  </Campo>
                  <Campo etiqueta="Base de datos" requerido className="sm:col-span-3" ayuda="Si no existe y el usuario tiene permisos, se creará.">
                    <Entrada value={bd.base_datos} onChange={(e) => setBd({ ...bd, base_datos: e.target.value })} />
                  </Campo>
                  <Campo etiqueta="Parámetros adicionales" className="sm:col-span-3" ayuda="clave=valor separados por punto y coma.">
                    <Entrada value={bd.parametros} placeholder="TrustServerCertificate=yes" onChange={(e) => setBd({ ...bd, parametros: e.target.value })} />
                  </Campo>
                </div>
              )}
              {esDemo && <Aviso>El Modo Demo usa una base SQLite local. No requiere servidor ni credenciales.</Aviso>}
            </div>
          )}

          {paso === 3 && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Se comprobará que el sistema puede conectarse con los datos indicados.</p>
              <Boton onClick={probar} cargando={ocupado} variante="oscuro" icono={<Database className="size-4" />}>
                Probar conexión
              </Boton>
              {prueba && <Aviso tipo={prueba.ok ? "exito" : "error"}>{prueba.mensaje}</Aviso>}
            </div>
          )}

          {paso === 4 && (
            <div className="space-y-4">
              <p className="text-sm text-slate-600">Se crearán la base (si no existe), las tablas, los índices y las relaciones mediante migraciones.</p>
              {!estructura && (
                <Boton onClick={crear} cargando={ocupado} variante="oscuro">
                  Crear estructura
                </Boton>
              )}
              {estructura && (
                <ul className="space-y-1.5">
                  {estructura.map((p) => (
                    <li key={p} className="flex items-center gap-2 text-sm text-slate-700">
                      <CheckCircle2 className="size-4 text-marca-600" /> {p}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {paso === 5 && (
            <div className="grid gap-4 sm:grid-cols-2">
              <Campo etiqueta="Usuario" requerido>
                <Entrada value={admin.usuario} autoComplete="off" onChange={(e) => setAdmin({ ...admin, usuario: e.target.value.trim() })} />
              </Campo>
              <Campo etiqueta="Nombre completo" requerido>
                <Entrada value={admin.nombre} onChange={(e) => setAdmin({ ...admin, nombre: e.target.value })} />
              </Campo>
              <Campo etiqueta="Correo" className="sm:col-span-2">
                <Entrada type="email" value={admin.email} onChange={(e) => setAdmin({ ...admin, email: e.target.value })} />
              </Campo>
              <Campo etiqueta="Clave" requerido ayuda="Mínimo 8 caracteres, con letras y números.">
                <Entrada type="password" autoComplete="new-password" value={admin.clave} onChange={(e) => setAdmin({ ...admin, clave: e.target.value })} />
              </Campo>
              <Campo etiqueta="Repetir clave" requerido error={admin.repetir && admin.repetir !== admin.clave ? "Las claves no coinciden." : null}>
                <Entrada type="password" autoComplete="new-password" value={admin.repetir} onChange={(e) => setAdmin({ ...admin, repetir: e.target.value })} />
              </Campo>
            </div>
          )}

          {paso === 6 && (
            <div className="space-y-4">
              <Campo etiqueta="Temporada inicial" ayuda="Formato AAAA-AAAA. Puede dejarse vacío y crearla después.">
                <Entrada value={temporada} onChange={(e) => setTemporada(e.target.value)} className="max-w-xs" />
              </Campo>
              <Interruptor valor={datosDemo} onCambio={setDatosDemo} etiqueta="Cargar datos de demostración (productos, bodegas, stock, procesos)" />
              <Aviso>Se crearán los roles iniciales (Administrador, Jefe de área, Digitador, Lector), unidades, tipos de movimiento, motivos y reglas de alerta. Todo es editable después.</Aviso>
            </div>
          )}

          {paso === 7 && (
            <div className="space-y-4 text-center">
              <CheckCircle2 className="mx-auto size-14 text-marca-600" />
              <h2 className="text-lg font-semibold text-slate-900">Instalación completa</h2>
              <ul className="mx-auto max-w-sm space-y-1 text-left text-sm text-slate-600">
                {final?.map((p) => (
                  <li key={p} className="flex items-center gap-2">
                    <Check className="size-4 text-marca-600" /> {p}
                  </li>
                ))}
              </ul>
              <Boton tam="lg" onClick={() => (window.location.href = "/login/")}>
                Entrar al sistema
              </Boton>
            </div>
          )}

          {paso < 7 && (
            <div className="mt-7 flex justify-between border-t border-slate-100 pt-4">
              <Boton variante="fantasma" disabled={paso === 0 || ocupado} onClick={() => setPaso(paso - 1)}>
                Atrás
              </Boton>
              {paso < 6 ? (
                <Boton disabled={!valido} onClick={() => setPaso(paso + 1)}>
                  Continuar
                </Boton>
              ) : (
                <Boton onClick={instalar} cargando={ocupado}>
                  Finalizar instalación
                </Boton>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
