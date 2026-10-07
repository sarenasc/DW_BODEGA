"use client";

import {
  ArrowLeftRight, Bell, Boxes, Building2, ClipboardCheck, ClipboardList, Cog, Factory, FileBarChart, FileText, GitBranch, HandCoins, Handshake,
  History, LayoutDashboard, Layers, LogOut, Menu, PackagePlus, PackageSearch, Plug, QrCode, Ruler, ScanLine, Search, ShieldCheck, Tags, Truck, Users, Warehouse, X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Cargando, cx } from "./ui";

type Item = { href: string; texto: string; icono: React.ComponentType<{ className?: string }>; permiso?: string };
const MENU: { titulo: string; items: Item[] }[] = [
  {
    titulo: "Inicio",
    items: [
      { href: "/", texto: "Dashboard", icono: LayoutDashboard, permiso: "dashboard:ver" },
      { href: "/alertas/", texto: "Alertas", icono: Bell, permiso: "alertas:ver" },
    ],
  },
  {
    titulo: "Operación",
    items: [
      { href: "/consumo/", texto: "Consumo rápido", icono: ScanLine, permiso: "movimientos:crear" },
      { href: "/documentos/nuevo/?clase=INGRESO", texto: "Nuevo ingreso", icono: PackagePlus, permiso: "inventario:crear" },
      { href: "/stock/", texto: "Stock", icono: Boxes, permiso: "inventario:ver" },
      { href: "/existencias/", texto: "Existencias y QR", icono: QrCode, permiso: "inventario:ver" },
      { href: "/documentos/", texto: "Documentos", icono: FileText, permiso: "inventario:ver" },
      { href: "/movimientos/", texto: "Movimientos", icono: ArrowLeftRight, permiso: "movimientos:ver" },
      { href: "/reservas/", texto: "Reservas", icono: Handshake, permiso: "reservas:ver" },
    ],
  },
  {
    titulo: "Producción",
    items: [
      { href: "/procesos/", texto: "Procesos", icono: Factory, permiso: "procesos:ver" },
      { href: "/costos/", texto: "Costos", icono: HandCoins, permiso: "costos:ver" },
      { href: "/trazabilidad/", texto: "Trazabilidad", icono: GitBranch, permiso: "trazabilidad:ver" },
    ],
  },
  {
    titulo: "Control",
    items: [
      { href: "/lotes/", texto: "Lotes", icono: Layers, permiso: "lotes:ver" },
      { href: "/conteos/", texto: "Inventario físico", icono: ClipboardCheck, permiso: "conteos:ver" },
      { href: "/prestamos/", texto: "Préstamos", icono: ClipboardList, permiso: "prestamos:ver" },
      { href: "/reportes/", texto: "Reportes", icono: FileBarChart, permiso: "reportes:ver" },
    ],
  },
  {
    titulo: "Maestros",
    items: [
      { href: "/productos/", texto: "Productos", icono: PackageSearch, permiso: "catalogo:ver" },
      { href: "/familias/", texto: "Familias", icono: Tags, permiso: "catalogo:ver" },
      { href: "/bodegas/", texto: "Bodegas", icono: Warehouse, permiso: "bodegas:ver" },
      { href: "/plantillas-lote/", texto: "Creador de lotes", icono: Building2, permiso: "lotes:ver" },
      { href: "/proveedores/", texto: "Proveedores", icono: Truck, permiso: "catalogo:ver" },
      { href: "/unidades/", texto: "Unidades", icono: Ruler, permiso: "catalogo:ver" },
    ],
  },
  {
    titulo: "Administración",
    items: [
      { href: "/integraciones/", texto: "Integraciones", icono: Plug, permiso: "integraciones:administrar" },
      { href: "/usuarios/", texto: "Usuarios y roles", icono: Users, permiso: "usuarios:administrar" },
      { href: "/configuracion/", texto: "Configuración", icono: Cog, permiso: "configuracion:editar" },
      { href: "/auditoria/", texto: "Auditoría", icono: History, permiso: "auditoria:ver" },
    ],
  },
];
const INFERIOR: Item[] = [
  { href: "/consumo/", texto: "Consumo", icono: ScanLine, permiso: "movimientos:crear" },
  { href: "/existencia/", texto: "Escanear", icono: QrCode, permiso: "inventario:ver" },
  { href: "/stock/", texto: "Stock", icono: Boxes, permiso: "inventario:ver" },
  { href: "/alertas/", texto: "Alertas", icono: Bell, permiso: "alertas:ver" },
];
const SIN_MARCO = ["/login", "/instalar"];

function activo(ruta: string, href: string) {
  const base = href.split("?")[0];
  return base === "/" ? ruta === "/" : ruta.startsWith(base);
}

function Buscador() {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState<any[] | null>(null);
  const router = useRouter();
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (q.trim().length < 2) {
      setResultados(null);
      return;
    }
    const t = setTimeout(() => api.get("/buscar", { q }).then(setResultados).catch(() => setResultados([])), 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const fuera = (e: MouseEvent) => !caja.current?.contains(e.target as Node) && setResultados(null);
    document.addEventListener("mousedown", fuera);
    return () => document.removeEventListener("mousedown", fuera);
  }, []);

  return (
    <div ref={caja} className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400" />
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Buscar producto, lote, QR, ubicación, documento, proceso…"
        aria-label="Buscador general"
        className="h-10 w-full rounded-lg border border-slate-200 bg-slate-50 pr-3 pl-9 text-sm outline-none focus:border-marca-500 focus:bg-white focus:ring-2 focus:ring-marca-500/20"
      />
      {resultados && (
        <div className="aparecer absolute top-11 z-40 max-h-96 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
          {resultados.length === 0 && <p className="px-3 py-3 text-sm text-slate-500">Sin resultados para “{q}”.</p>}
          {resultados.map((r, i) => (
            <button
              key={i}
              onClick={() => {
                setResultados(null);
                setQ("");
                router.push(r.enlace);
              }}
              className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-slate-50"
            >
              <span className="w-20 shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-center text-[10px] font-semibold text-slate-600 uppercase">{r.tipo}</span>
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium text-slate-900">{r.titulo}</span>
                <span className="block truncate text-xs text-slate-500">{r.detalle}</span>
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function Marco({ children }: { children: React.ReactNode }) {
  const ruta = usePathname();
  const { usuario, cargando, puede, salir } = useSesion();
  const [abierto, setAbierto] = useState(false);
  const [alertas, setAlertas] = useState<{ abiertas: number; criticas: number } | null>(null);

  useEffect(() => setAbierto(false), [ruta]);
  useEffect(() => {
    if (!usuario || !usuario.permisos.includes("alertas:ver")) return;
    const cargar = () => api.get("/alertas/resumen").then(setAlertas).catch(() => {});
    cargar();
    const t = setInterval(cargar, 60_000);
    return () => clearInterval(t);
  }, [usuario, ruta]);

  if (SIN_MARCO.some((p) => ruta.startsWith(p))) return <>{children}</>;
  if (cargando || !usuario) return <Cargando texto="Iniciando…" />;

  const menu = MENU.map((s) => ({ ...s, items: s.items.filter((i) => !i.permiso || puede(i.permiso)) })).filter((s) => s.items.length);
  const inferior = INFERIOR.filter((i) => !i.permiso || puede(i.permiso));

  const lateral = (
    <nav className="flex h-full flex-col bg-panel text-slate-300">
      <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-white/10 px-4">
        <span className="flex size-8 items-center justify-center rounded-lg bg-marca-500 text-white">
          <Warehouse className="size-4.5" />
        </span>
        <div className="min-w-0 leading-tight">
          <p className="truncate text-sm font-semibold text-white">WMS Bodegas</p>
          <p className="truncate text-[11px] text-slate-400">{usuario.empresa.nombre}</p>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto px-2 py-3">
        {menu.map((s) => (
          <div key={s.titulo} className="mb-3">
            <p className="px-2 pb-1 text-[10px] font-semibold tracking-widest text-slate-500 uppercase">{s.titulo}</p>
            {s.items.map((i) => (
              <Link
                key={i.href}
                href={i.href}
                className={cx("flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition", activo(ruta, i.href) ? "bg-white/10 font-medium text-white" : "hover:bg-white/5 hover:text-white")}
              >
                <i.icono className="size-4 shrink-0" />
                <span className="truncate">{i.texto}</span>
                {i.href === "/alertas/" && !!alertas?.abiertas && (
                  <span className={cx("ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold text-white", alertas.criticas ? "bg-rose-500" : "bg-amber-500")}>{alertas.abiertas}</span>
                )}
              </Link>
            ))}
          </div>
        ))}
      </div>
      <div className="shrink-0 border-t border-white/10 p-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-xs font-semibold text-white">{usuario.nombre.slice(0, 1)}</span>
          <div className="min-w-0 flex-1 leading-tight">
            <p className="truncate text-sm font-medium text-white">{usuario.nombre}</p>
            <p className="truncate text-[11px] text-slate-400">{usuario.roles.join(", ")}</p>
          </div>
          <button onClick={salir} title="Cerrar sesión" aria-label="Cerrar sesión" className="rounded-lg p-2 text-slate-400 hover:bg-white/10 hover:text-white">
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </nav>
  );

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="no-imprimir hidden w-60 shrink-0 lg:block">{lateral}</aside>
      {abierto && (
        <div className="no-imprimir fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/60" onClick={() => setAbierto(false)} />
          <aside className="aparecer absolute inset-y-0 left-0 w-72 max-w-[85vw] shadow-2xl">{lateral}</aside>
          <button onClick={() => setAbierto(false)} aria-label="Cerrar menú" className="absolute top-3 right-3 rounded-full bg-white/10 p-2 text-white">
            <X className="size-5" />
          </button>
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-imprimir flex h-14 shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-3 sm:px-5">
          <button onClick={() => setAbierto(true)} aria-label="Abrir menú" className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden">
            <Menu className="size-5" />
          </button>
          <Buscador />
          <div className="ml-auto flex items-center gap-1">
            {usuario.modo_demo && <span className="hidden rounded-md bg-amber-100 px-2 py-1 text-[11px] font-semibold text-amber-800 sm:inline">MODO DEMO</span>}
            {puede("alertas:ver") && (
              <Link href="/alertas/" aria-label="Alertas" className="relative rounded-lg p-2 text-slate-600 hover:bg-slate-100">
                <Bell className="size-5" />
                {!!alertas?.abiertas && (
                  <span className={cx("absolute -top-0.5 -right-0.5 flex min-w-4.5 items-center justify-center rounded-full px-1 text-[10px] font-bold text-white", alertas.criticas ? "bg-rose-600" : "bg-amber-500")}>
                    {alertas.abiertas > 99 ? "99+" : alertas.abiertas}
                  </span>
                )}
              </Link>
            )}
            <ShieldCheck className="hidden size-4 text-slate-300 sm:block" aria-hidden />
          </div>
        </header>
        <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          <div className="mx-auto w-full max-w-[1500px] p-3 sm:p-5">{children}</div>
        </main>
        {inferior.length > 0 && (
          <nav className="no-imprimir fixed inset-x-0 bottom-0 z-30 grid border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] lg:hidden" style={{ gridTemplateColumns: `repeat(${inferior.length + 1}, 1fr)` }}>
            {inferior.map((i) => (
              <Link key={i.href} href={i.href} className={cx("flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium", activo(ruta, i.href) ? "text-marca-700" : "text-slate-500")}>
                <i.icono className="size-6" />
                {i.texto}
              </Link>
            ))}
            <button onClick={() => setAbierto(true)} className="flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium text-slate-500">
              <Menu className="size-6" />
              Más
            </button>
          </nav>
        )}
      </div>
    </div>
  );
}
