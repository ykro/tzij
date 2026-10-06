import { describe, expect, it } from "vitest";
import { cleanInput, displayOutput, errorMessage, formatLatency, languages, MAX_CHARS, swapDirection } from "../lib/translator";

describe("translator page helpers", () => {
  it("swaps the direction both ways", () => {
    expect(swapDirection("es-quc")).toBe("quc-es");
    expect(swapDirection("quc-es")).toBe("es-quc");
  });

  it("names the languages of each direction", () => {
    expect(languages("es-quc")).toEqual({ from: "Español", to: "Kʼicheʼ" });
    expect(languages("quc-es")).toEqual({ from: "Kʼicheʼ", to: "Español" });
  });

  it("cleans the input and refuses an empty box", () => {
    expect(cleanInput("  Conexión   segura \n")).toBe("Conexión segura");
    expect(cleanInput("   ")).toBeNull();
    expect(cleanInput("a".repeat(MAX_CHARS + 50))).toHaveLength(MAX_CHARS);
  });

  it("shows K'iche' output with the saltillo, Spanish as is", () => {
    expect(displayOutput({ direction: "es-quc", text: "Chajital t'iqonem" })).toBe("Chajital tʼiqonem");
    expect(displayOutput({ direction: "quc-es", text: "Conexión segura" })).toBe("Conexión segura");
  });

  it("explains a failed translation", () => {
    expect(errorMessage({ status: "ok", error: null })).toBeNull();
    expect(errorMessage({ status: "error", error: "recuperación: sin Ollama" })).toBe("David no pudo traducir: recuperación: sin Ollama");
    expect(errorMessage({ status: "error", error: null })).toBe("David no pudo traducir esta frase.");
  });

  it("formats latency in seconds", () => {
    expect(formatLatency(2370)).toBe("2.4 s");
    expect(formatLatency(null)).toBe("");
  });
});
