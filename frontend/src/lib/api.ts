// Cliente de la API. El token de acceso vive solo en memoria; la sesion renovable viaja en una cookie httpOnly.

const BASE = process.env.NEXT_PUBLIC_API ?? "";
let token: string | null = null;
let renovando: Promise<boolean> | null = null;

export class ErrorApi extends Error {
  constructor(
    public estado: number,
    public codigo: string,
    mensaje: string,
    public datos: any = {},
  ) {
    super(mensaje);
  }
}

export type Params = Record<string, string | number | boolean | null | undefined>;

export function url(ruta: string, params?: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v !== null && v !== undefined && v !== "") q.set(k, String(v));
  const s = q.toString();
  return `${BASE}/api${ruta}${s ? `?${s}` : ""}`;
}

export function fijarToken(t: string | null) {
  token = t;
}

/** Renueva el token de acceso con la cookie de sesion. Las llamadas simultaneas comparten una sola renovacion. */
export function renovar(): Promise<boolean> {
  renovando ??= fetch(url("/auth/refrescar"), { method: "POST", credentials: "include" })
    .then(async (r) => {
      if (!r.ok) return false;
      token = (await r.json()).token;
      return true;
    })
    .catch(() => false)
    .finally(() => {
      renovando = null;
    });
  return renovando;
}

async function pedir(ruta: string, init: RequestInit, params?: Params, reintento = true): Promise<Response> {
  const cabeceras = new Headers(init.headers);
  if (token) cabeceras.set("Authorization", `Bearer ${token}`);
  let r: Response;
  try {
    r = await fetch(url(ruta, params), { ...init, headers: cabeceras, credentials: "include" });
  } catch {
    throw new ErrorApi(0, "SIN_CONEXION", "No hay conexion con el servidor. Revise la red e intente de nuevo.");
  }
  if (r.status === 401 && reintento && !ruta.startsWith("/auth/")) {
    if (await renovar()) return pedir(ruta, init, params, false);
    if (typeof window !== "undefined") window.dispatchEvent(new Event("wms:sesion-expirada"));
  }
  if (!r.ok) {
    let cuerpo: any = {};
    try {
      cuerpo = await r.json();
    } catch {}
    const detalle = Array.isArray(cuerpo.detail)
      ? cuerpo.detail.map((d: any) => `${d.loc?.slice(1).join(".")}: ${d.msg}`).join("; ")
      : cuerpo.detail;
    throw new ErrorApi(r.status, cuerpo.codigo ?? "ERROR", cuerpo.mensaje ?? detalle ?? `Error ${r.status}`, cuerpo.datos);
  }
  return r;
}

async function json<T>(ruta: string, metodo: string, cuerpo?: unknown, params?: Params): Promise<T> {
  const r = await pedir(
    ruta,
    { method: metodo, headers: cuerpo !== undefined ? { "Content-Type": "application/json" } : undefined, body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined },
    params,
  );
  return r.json();
}

export const api = {
  get: <T = any>(ruta: string, params?: Params) => json<T>(ruta, "GET", undefined, params),
  post: <T = any>(ruta: string, cuerpo: unknown = {}, params?: Params) => json<T>(ruta, "POST", cuerpo, params),
  put: <T = any>(ruta: string, cuerpo: unknown = {}) => json<T>(ruta, "PUT", cuerpo),
  del: <T = any>(ruta: string) => json<T>(ruta, "DELETE"),
  /** Descarga binaria autenticada (PDF, Excel, adjuntos). */
  async blob(ruta: string, params?: Params): Promise<{ blob: Blob; nombre: string | null }> {
    const r = await pedir(ruta, { method: "GET" }, params);
    const nombre = /filename="?([^";]+)"?/.exec(r.headers.get("content-disposition") ?? "")?.[1] ?? null;
    return { blob: await r.blob(), nombre };
  },
  async subir<T = any>(ruta: string, datos: FormData): Promise<T> {
    return (await pedir(ruta, { method: "POST", body: datos })).json();
  },
};

/** Abre un PDF en otra pestana o descarga el archivo, segun el caso. */
export async function abrirArchivo(ruta: string, params?: Params, descargarComo?: string) {
  const { blob, nombre } = await api.blob(ruta, params);
  const enlace = URL.createObjectURL(blob);
  if (descargarComo || !blob.type.includes("pdf")) {
    const a = document.createElement("a");
    a.href = enlace;
    a.download = descargarComo ?? nombre ?? "archivo";
    a.click();
  } else {
    window.open(enlace, "_blank");
  }
  setTimeout(() => URL.revokeObjectURL(enlace), 60_000);
}

export function claveIdempotencia(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}
