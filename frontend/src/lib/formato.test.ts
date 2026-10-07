import { describe, expect, it } from "vitest";
import { clp, clpCorto, etiqueta, fecha, num } from "./formato";

describe("formato", () => {
  it("numeros y montos con formato chileno", () => {
    expect(num(1234.5)).toBe("1.234,5");
    expect(num(null)).toBe("—");
    expect(clp(170000)).toBe("$170.000");
    expect(clp(8.5, 2)).toBe("$8,5");
    expect(clpCorto(4_200_000)).toBe("$4,2 M");
    expect(clpCorto(475_000)).toBe("$475 mil");
  });
  it("una fecha sin hora no se desplaza por la zona horaria", () => {
    expect(fecha("2026-10-06")).toBe("06-10-2026");
    expect(fecha(null)).toBe("—");
  });
  it("etiquetas legibles", () => {
    expect(etiqueta("STOCK_BAJO")).toBe("Stock bajo");
  });
});
