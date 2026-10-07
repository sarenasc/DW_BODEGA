"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, ErrorApi, fijarToken, type Params, renovar } from "./api";

export type Usuario = {
  id: number;
  usuario: string;
  nombre: string;
  roles: string[];
  permisos: string[];
  empresa: { nombre: string; moneda: string };
  modo_demo: boolean;
  debe_cambiar_clave: boolean;
};

type Sesion = {
  usuario: Usuario | null;
  cargando: boolean;
  puede: (permiso: string) => boolean;
  entrar: (usuario: string, clave: string) => Promise<void>;
  salir: () => Promise<void>;
};

const Contexto = createContext<Sesion>({ usuario: null, cargando: true, puede: () => false, entrar: async () => {}, salir: async () => {} });
const PUBLICAS = ["/login", "/instalar"];

export function ProveedorSesion({ children }: { children: React.ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);
  const [sinInstalar, setSinInstalar] = useState(false);
  const router = useRouter();
  const ruta = usePathname();

  useEffect(() => {
    let vivo = true;
    (async () => {
      try {
        const estado = await api.get("/instalacion/estado");
        if (!estado.instalado) {
          if (vivo) setSinInstalar(true);
          return;
        }
        if (await renovar()) {
          const yo = await api.get<Usuario>("/auth/yo");
          if (vivo) setUsuario(yo);
        }
      } catch {
        // Sin conexion: se muestra el acceso y el error aparece al intentar entrar.
      } finally {
        if (vivo) setCargando(false);
      }
    })();
    const expirada = () => setUsuario(null);
    window.addEventListener("wms:sesion-expirada", expirada);
    return () => {
      vivo = false;
      window.removeEventListener("wms:sesion-expirada", expirada);
    };
  }, [router]);

  useEffect(() => {
    if (cargando) return;
    if (sinInstalar) {
      // Primera ejecucion: todo conduce al asistente (tambien si se abre /login directamente).
      if (!ruta.startsWith("/instalar")) router.replace("/instalar/");
      return;
    }
    const publica = PUBLICAS.some((p) => ruta.startsWith(p));
    if (!usuario && !publica) {
      const destino = ruta + (typeof window !== "undefined" ? window.location.search : "");
      router.replace(`/login/?volver=${encodeURIComponent(destino)}`);
    }
  }, [cargando, usuario, ruta, router, sinInstalar]);

  const entrar = useCallback(async (nombre: string, clave: string) => {
    const r = await api.post("/auth/login", { usuario: nombre, clave });
    fijarToken(r.token);
    setUsuario(r.usuario);
  }, []);

  const salir = useCallback(async () => {
    try {
      await api.post("/auth/salir");
    } catch {}
    fijarToken(null);
    setUsuario(null);
    router.replace("/login/");
  }, [router]);

  const valor = useMemo<Sesion>(
    () => ({ usuario, cargando, puede: (p) => !!usuario?.permisos.includes(p), entrar, salir }),
    [usuario, cargando, entrar, salir],
  );
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export const useSesion = () => useContext(Contexto);

/** Carga datos de la API y los recarga cuando cambian la ruta o los parametros. */
export function useDatos<T = any>(ruta: string | null, params?: Params) {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(!!ruta);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const clave = JSON.stringify(params ?? {});

  useEffect(() => {
    if (!ruta) {
      setDatos(null);
      setCargando(false);
      return;
    }
    let vivo = true;
    setCargando(true);
    api
      .get<T>(ruta, JSON.parse(clave))
      .then((d) => {
        if (vivo) {
          setDatos(d);
          setError(null);
        }
      })
      .catch((e: ErrorApi) => {
        if (vivo) setError(e.message);
      })
      .finally(() => {
        if (vivo) setCargando(false);
      });
    return () => {
      vivo = false;
    };
  }, [ruta, clave, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);
  return { datos, cargando, error, recargar, setDatos };
}

/** Parametro de la URL (?id=5). Las paginas son estaticas: el detalle se elige por parametro, no por segmento. */
export function useParametro(nombre: string): string | null {
  return useSearchParams().get(nombre);
}
