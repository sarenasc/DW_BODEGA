"use client";

// Lectura de QR: camara del telefono (BarcodeDetector nativo o jsQR como respaldo) y lectores USB/Bluetooth,
// que se comportan como un teclado que escribe el codigo y termina con Enter.

import { Camera, CameraOff, Keyboard } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Boton, cx } from "./ui";

export function vibrar(patron: number | number[] = 60) {
  try {
    navigator.vibrate?.(patron);
  } catch {}
}

export function pitido(ok = true) {
  try {
    const Ctx = window.AudioContext ?? (window as any).webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gan = ctx.createGain();
    osc.frequency.value = ok ? 1100 : 320;
    gan.gain.value = 0.06;
    osc.connect(gan).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + (ok ? 0.09 : 0.25));
    osc.onended = () => ctx.close();
  } catch {}
}

/** Vista de camara que entrega cada codigo leido. Se pausa sola mientras `activa` es falso. */
export function CamaraQR({ activa, onLeer, className }: { activa: boolean; onLeer: (codigo: string) => void; className?: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  const ultimo = useRef({ codigo: "", t: 0 });
  const leer = useRef(onLeer);
  leer.current = onLeer;

  useEffect(() => {
    if (!activa) return;
    let vivo = true;
    let flujo: MediaStream | null = null;
    let cuadro = 0;
    const lienzo = document.createElement("canvas");
    const entregar = (codigo: string) => {
      const ahora = Date.now();
      // Evita registrar varias veces la misma etiqueta mientras sigue frente a la camara.
      if (codigo === ultimo.current.codigo && ahora - ultimo.current.t < 2500) return;
      ultimo.current = { codigo, t: ahora };
      leer.current(codigo);
    };
    (async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(window.isSecureContext ? "Este navegador no permite usar la cámara." : "La cámara requiere una conexión segura (HTTPS).");
        return;
      }
      try {
        flujo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } }, audio: false });
      } catch (e: any) {
        setError(e?.name === "NotAllowedError" ? "Permiso de cámara denegado. Habilítelo en el navegador." : "No se pudo abrir la cámara.");
        return;
      }
      if (!vivo || !video.current) return flujo.getTracks().forEach((t) => t.stop());
      video.current.srcObject = flujo;
      await video.current.play().catch(() => {});
      setError(null);
      const Detector = (window as any).BarcodeDetector;
      const nativo = Detector ? new Detector({ formats: ["qr_code"] }) : null;
      const jsQR = nativo ? null : (await import("jsqr")).default;
      const ciclo = async () => {
        if (!vivo) return;
        const v = video.current;
        if (v && v.readyState >= 2 && v.videoWidth) {
          try {
            if (nativo) {
              const r = await nativo.detect(v);
              if (r[0]?.rawValue) entregar(r[0].rawValue);
            } else if (jsQR) {
              const escala = Math.min(1, 640 / v.videoWidth);
              lienzo.width = v.videoWidth * escala;
              lienzo.height = v.videoHeight * escala;
              const ctx = lienzo.getContext("2d", { willReadFrequently: true })!;
              ctx.drawImage(v, 0, 0, lienzo.width, lienzo.height);
              const r = jsQR(ctx.getImageData(0, 0, lienzo.width, lienzo.height).data, lienzo.width, lienzo.height, { inversionAttempts: "dontInvert" });
              if (r?.data) entregar(r.data);
            }
          } catch {}
        }
        cuadro = window.setTimeout(ciclo, 140);
      };
      ciclo();
    })();
    return () => {
      vivo = false;
      clearTimeout(cuadro);
      flujo?.getTracks().forEach((t) => t.stop());
    };
  }, [activa]);

  return (
    <div className={cx("relative overflow-hidden rounded-2xl bg-slate-900", className)}>
      <video ref={video} playsInline muted className="h-full w-full object-cover" />
      {!error && activa && <div className="pointer-events-none absolute inset-[18%] rounded-2xl border-4 border-white/80 shadow-[0_0_0_9999px_rgba(15,23,42,0.35)]" />}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center text-sm text-slate-200">
          <CameraOff className="size-8" />
          {error}
          <span className="text-xs text-slate-400">Puede digitar el código INV o usar un lector USB/Bluetooth.</span>
        </div>
      )}
    </div>
  );
}

/**
 * Entrada unificada de codigos: camara opcional + campo que recibe lectores USB/Bluetooth o digitacion manual.
 * El campo recupera el foco solo, para que el lector externo siempre "escriba" en el lugar correcto.
 */
export function EntradaCodigo({ onCodigo, activa = true, autoCamara = false, ayuda }: { onCodigo: (codigo: string) => void; activa?: boolean; autoCamara?: boolean; ayuda?: string }) {
  const [camara, setCamara] = useState(autoCamara);
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLInputElement>(null);

  const enviar = useCallback(
    (codigo: string) => {
      const limpio = codigo.trim();
      if (!limpio) return;
      setTexto("");
      onCodigo(limpio);
    },
    [onCodigo],
  );

  useEffect(() => {
    if (!activa || camara) return;
    const t = setInterval(() => {
      const foco = document.activeElement;
      if (!foco || foco === document.body) campo.current?.focus({ preventScroll: true });
    }, 600);
    campo.current?.focus({ preventScroll: true });
    return () => clearInterval(t);
  }, [activa, camara]);

  return (
    <div className="space-y-3">
      {camara && <CamaraQR activa={activa} onLeer={enviar} className="aspect-square max-h-[46dvh] w-full" />}
      <form onSubmit={(e) => { e.preventDefault(); enviar(texto); }} className="flex gap-2">
        <input ref={campo} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder="Escanee o digite el código (INV-…)" autoComplete="off" autoCapitalize="characters" enterKeyHint="go" aria-label="Código de existencia" className="campo !h-14 flex-1 !text-lg" />
        <Boton type="submit" tam="lg" variante="oscuro" disabled={!texto.trim()}>
          Buscar
        </Boton>
      </form>
      <div className="flex items-center justify-between gap-2 text-xs text-slate-500">
        <span className="flex items-center gap-1.5">
          <Keyboard className="size-3.5" /> {ayuda ?? "Lector USB/Bluetooth: apunte y dispare; el código entra solo."}
        </span>
        <Boton tam="sm" variante={camara ? "secundario" : "primario"} icono={camara ? <CameraOff className="size-4" /> : <Camera className="size-4" />} onClick={() => setCamara(!camara)}>
          {camara ? "Apagar cámara" : "Usar cámara"}
        </Boton>
      </div>
    </div>
  );
}
