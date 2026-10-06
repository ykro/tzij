import { describe, expect, it } from "vitest";
import { displayKiche, LANG_LABEL, modelName } from "../lib/kiche";

describe("K'iche' display", () => {
  it("shows the glottal stop as U+02BC", () => {
    expect(displayKiche("Le tz'i' kawar")).toBe("Le tzʼiʼ kawar");
    expect(LANG_LABEL.quc).toBe("Kʼicheʼ");
  });
  it("names the models", () => {
    expect(modelName("gemini-3.8-flash")).toBe("Gemini 3.8 Flash");
    expect(modelName("tzij-2026-10-mix-s7")).toBe("Gemma 4 E4B ajustado 10/2026");
    expect(modelName("")).toBe("");
  });
});
