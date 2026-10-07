import { describe, expect, it } from "vitest";
import { celdasRack, colorOcupacion, type Elemento, huella, VACIO } from "./tipos";

const rack: Elemento = { clave: "e1", tipo: "RACK", nombre: "R01", x: 2, y: 1, ancho: 6, fondo: 1.2, alto: 4.5, rotacion: 0, color: null, parametros: { niveles: 2, posiciones: 3 }, ubicacion_id: 10 };
const u = (id: number, padre_id: number | null, codigo: string, orden: number) => ({ id, padre_id, tipo: "X", codigo, orden, codigo_completo: codigo, almacenable: true, capacidad: null });

describe("plano", () => {
  it("la huella en planta respeta la rotacion", () => {
    expect(huella(rack)).toEqual({ w: 6, d: 1.2 });
    expect(huella({ ...rack, rotacion: 90 })).toEqual({ w: 1.2, d: 6 });
  });
  it("cada celda del rack corresponde a su ubicacion logica", () => {
    const ubicaciones = [u(11, 10, "N01", 1), u(12, 10, "N02", 2), u(21, 11, "P01", 1), u(22, 11, "P02", 2), u(23, 11, "P03", 3), u(31, 12, "P01", 1)];
    const celdas = celdasRack(rack, ubicaciones);
    expect(celdas).toHaveLength(6);
    expect(celdas.find((c) => c.nivel === 0 && c.posicion === 2)?.ubicacion?.id).toBe(23);
    expect(celdas.find((c) => c.nivel === 1 && c.posicion === 0)?.ubicacion?.id).toBe(31);
    expect(celdas.find((c) => c.nivel === 1 && c.posicion === 2)?.ubicacion).toBeNull();
  });
  it("color segun el modo", () => {
    const o = { ubicacion_id: 1, existencias: 1, cantidad: 10, valor: 1000, dias_antiguedad: 100, dias_para_vencer: -2, ocupacion: 0.95 };
    expect(colorOcupacion(undefined, "ocupacion", 0)).toBe(VACIO);
    expect(colorOcupacion(o, "antiguedad", 0)).toBe("#b91c1c");
    expect(colorOcupacion(o, "vencimiento", 0)).toBe("#b91c1c");
    expect(colorOcupacion({ ...o, dias_para_vencer: null }, "vencimiento", 0)).toBe("#94a3b8");
    expect(colorOcupacion(o, "ocupacion", 0)).toBe("#0f766e");
  });
});
