// La exportacion estatica de Next.js guarda los datos de cada segmento en carpetas anidadas
// (__next.bodegas/plano/__PAGE__.txt), pero el navegador los pide con puntos
// (__next.bodegas.plano.__PAGE__.txt). Este paso crea esas copias para que cualquier servidor
// de archivos estaticos (el backend, nginx, Caddy) las entregue sin reglas de reescritura.
import { copyFileSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const RAIZ = new URL("../out/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
let copias = 0;

function archivos(dir) {
  return readdirSync(dir).flatMap((n) => {
    const ruta = join(dir, n);
    return statSync(ruta).isDirectory() ? archivos(ruta) : [ruta];
  });
}

function recorrer(dir) {
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre);
    if (!statSync(ruta).isDirectory()) continue;
    if (nombre.startsWith("__next.")) {
      for (const archivo of archivos(ruta)) {
        const plano = `${nombre}.${relative(ruta, archivo).split(sep).join(".")}`;
        copyFileSync(archivo, join(dir, plano));
        copias++;
      }
    } else if (nombre !== "_next") {
      recorrer(ruta);
    }
  }
}

recorrer(decodeURIComponent(RAIZ));
console.log(`Exportacion aplanada: ${copias} archivos de segmento.`);
