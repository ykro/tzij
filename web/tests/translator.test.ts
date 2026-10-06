import { describe, expect, it } from "vitest";
import {
  activeExample,
  cleanInput,
  closenessPercent,
  costPerThousand,
  displayIn,
  type Example,
  failureText,
  formatCost,
  formatSeconds,
  languages,
  MAX_CHARS,
  swapDirection,
  targetLang,
} from "../lib/translator";

const EX: Example = {
  pair_id: "p1", direction: "es-quc", text: "Conexión segura", reference: "Chajital t'iqonem",
  source: "Mozilla Pontoon (Firefox Focus)", url: "https://huggingface.co/datasets/ayymen/Pontoon-Translations", license: "MPL-2.0",
};

describe("translator page helpers", () => {
  it("swaps the direction and names its languages", () => {
    expect(swapDirection("es-quc")).toBe("quc-es");
    expect(swapDirection("quc-es")).toBe("es-quc");
    expect(languages("es-quc")).toEqual({ from: "Español", to: "Kʼicheʼ" });
    expect(targetLang("es-quc")).toBe("quc");
  });

  it("cleans the input and refuses an empty box", () => {
    expect(cleanInput("  Conexión   segura \n")).toBe("Conexión segura");
    expect(cleanInput("   ")).toBeNull();
    expect(cleanInput("a".repeat(MAX_CHARS + 50))).toHaveLength(MAX_CHARS);
  });

  it("shows K'iche' with the saltillo, Spanish as is", () => {
    expect(displayIn("Chajital t'iqonem", "quc")).toBe("Chajital tʼiqonem");
    expect(displayIn("Conexión segura", "es")).toBe("Conexión segura");
  });

  it("turns chrF++ into a plain closeness percentage", () => {
    expect(closenessPercent(86.6)).toBe(87);
    expect(closenessPercent(100)).toBe(100);
    expect(closenessPercent(null)).toBeNull();
  });

  it("formats time and cost so the difference reads at a glance", () => {
    expect(formatSeconds(2370)).toBe("2.4 s");
    expect(formatSeconds(null)).toBe("—");
    expect(formatCost(0)).toBe("Gratis");
    expect(formatCost(0.000123)).toBe("US$ 0.000123");
    expect(costPerThousand(0.000123)).toBe("US$ 0.12 por cada 1,000");
    expect(costPerThousand(0)).toBeNull();
  });

  it("says why a side has no translation, in plain words", () => {
    expect(failureText("goliath", { status: "offline", error: null })).toMatch(/^Sin conexión/);
    expect(failureText("david", { status: "error", error: "x" })).toBe("No pudo traducir esta frase. Intenta de nuevo.");
    expect(failureText("david", { status: "ok", error: null })).toBeNull();
  });

  it("only compares with the correct translation while the box holds the example", () => {
    expect(activeExample([EX], "p1", " Conexión segura ", "es-quc")).toBe(EX);
    expect(activeExample([EX], "p1", "Conexión segura hoy", "es-quc")).toBeNull();
    expect(activeExample([EX], "p1", "Conexión segura", "quc-es")).toBeNull();
    expect(activeExample([EX], null, "Conexión segura", "es-quc")).toBeNull();
  });
});
