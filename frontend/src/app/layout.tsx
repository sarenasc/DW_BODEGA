import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { Marco } from "@/components/Marco";
import { ProveedorAvisos } from "@/components/ui";
import { ProveedorSesion } from "@/lib/sesion";
import "./globals.css";

export const metadata: Metadata = {
  title: "WMS Bodegas",
  description: "Gestión de bodegas, inventario, lotes, QR, consumos y procesos productivos",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#111c2e" };

export default function Raiz({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <Suspense>
          <ProveedorAvisos>
            <ProveedorSesion>
              <Marco>{children}</Marco>
            </ProveedorSesion>
          </ProveedorAvisos>
        </Suspense>
      </body>
    </html>
  );
}
