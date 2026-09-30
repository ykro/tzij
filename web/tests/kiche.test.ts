import { describe, expect, it } from "vitest";
import { directionLabel, displayKiche, displaySource, displayTarget, formatCost, formatCount, modelName } from "../lib/kiche";

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
  });
});
