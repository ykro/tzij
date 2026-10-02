import { describe, expect, it } from "vitest";
import { directionLabel, displayKiche, displaySource, displayTarget, formatCost, formatCount, modelName, roundKindLabel } from "../lib/kiche";

describe("K'iche' display", () => {
  it("shows the glottal stop as U+02BC", () => {
    expect(displayKiche("Le tz'i' kawar")).toBe("Le tzʼiʼ kawar");
  });
  it("only converts the K'iche' side", () => {
    expect(displaySource("l'agua", "es-quc")).toBe("l'agua");
    expect(displayTarget("k'ak'", "es-quc")).toBe("kʼakʼ");
    expect(displaySource("k'ak'", "quc-es")).toBe("kʼakʼ");
  });
  it("labels directions in Spanish", () => {
    expect(directionLabel("es-quc")).toBe("Español → Kʼicheʼ");
  });
  it("formats numbers for the stage", () => {
    expect(formatCount(9812)).toBe("9 812");
    expect(formatCost(0)).toBe("$0.00");
    expect(formatCost(0.00312)).toBe("$0.0031");
    expect(modelName("gemma4:e2b-it-qat")).toBe("Gemma 4 E2B");
    expect(modelName("gemini-3.8-flash")).toBe("Gemini 3.8 Flash");
    expect(modelName("tzij-2026-10-raft-bt-s3")).toBe("Gemma 4 E4B ajustado 10/2026");
  });
});

describe("round labels", () => {
  it("names specialty rounds next to the normal ones", () => {
    expect(roundKindLabel({ kind: "en_vivo", reference_meta: null })).toBe("En vivo");
    const meta = { source_name: "bloom_kiche", url: "", license: "", status: "auto_validated" };
    expect(roundKindLabel({ kind: "evaluacion", reference_meta: meta })).toBe("Evaluación");
    expect(roundKindLabel({ kind: "evaluacion", reference_meta: { ...meta, specialty: true } }))
      .toBe("Ronda de especialidad: memoria de traducción (Firefox Focus)");
  });
});
