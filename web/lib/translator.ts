// The translator page (/traductor/): David and Goliath translate the same text side by side.
// Pure helpers, tested in tests/translator.test.ts.

import { displayKiche, LANG_LABEL } from "./kiche";
import type { ContenderName, Direction } from "./types";

export const MAX_CHARS = 280; // same limit as the duel service (MAX_PHRASE_CHARS)
export const SIDES: ContenderName[] = ["david", "goliath"];

export interface Example {
  pair_id: string;
  direction: Direction;
  text: string;
  reference: string;
  source: string;
  url: string;
  license: string;
}

export interface SideResult {
  status: "ok" | "offline" | "error";
  text: string;
  latency_ms: number | null;
  cost_usd: number;
  closeness: number | null; // chrF++ against the licensed correct translation, 0-100 (examples only)
  error: string | null;
  model: string;
}

export type SideState =
  | { phase: "idle" }
  | { phase: "busy" }
  | { phase: "done"; result: SideResult }
  | { phase: "failed"; message: string };

export function swapDirection(direction: Direction): Direction {
  return direction === "es-quc" ? "quc-es" : "es-quc";
}

export function languages(direction: Direction): { from: string; to: string } {
  return direction === "es-quc" ? { from: LANG_LABEL.es, to: LANG_LABEL.quc } : { from: LANG_LABEL.quc, to: LANG_LABEL.es };
}

/** Text ready to send: trimmed, inner whitespace collapsed, within the limit; null if empty. */
export function cleanInput(text: string): string | null {
  const clean = text.replace(/\s+/g, " ").trim().slice(0, MAX_CHARS);
  return clean ? clean : null;
}

/** K'iche' is shown with the saltillo (ʼ); Spanish as is. */
export function displayIn(text: string, lang: "es" | "quc"): string {
  return lang === "quc" ? displayKiche(text) : text;
}

export function targetLang(direction: Direction): "es" | "quc" {
  return direction === "es-quc" ? "quc" : "es";
}

/** chrF++ (0-100) as a whole percentage, the "se parece a la correcta" figure. */
export function closenessPercent(chrf: number | null | undefined): number | null {
  if (chrf == null || Number.isNaN(chrf)) return null;
  return Math.round(Math.min(100, Math.max(0, chrf)));
}

export function formatSeconds(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return `${(ms / 1000).toLocaleString("es-GT", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;
}

/** The cost of one translation, readable: "Gratis" for $0, otherwise dollars with enough decimals to see it. */
export function formatCost(usd: number | null | undefined): string {
  if (!usd) return "Gratis";
  if (usd >= 0.01) return `US$ ${usd.toFixed(2)}`;
  return `US$ ${usd.toFixed(6).replace(/0+$/, "")}`;
}

/** The same cost scaled to 1,000 translations, where the difference is easy to grasp. */
export function costPerThousand(usd: number | null | undefined): string | null {
  if (!usd) return null;
  return `US$ ${(usd * 1000).toFixed(2)} por cada 1,000`;
}

export function failureText(side: ContenderName, result: Pick<SideResult, "status" | "error">): string | null {
  if (result.status === "ok") return null;
  if (result.status === "offline") {
    return side === "goliath" ? "Sin conexión: Gemini vive en la nube y esta laptop no tiene internet." : "Sin conexión.";
  }
  return "No pudo traducir esta frase. Intenta de nuevo.";
}

/** The example a request belongs to: only when the box still holds that exact phrase. */
export function activeExample(examples: Example[], picked: string | null, text: string, direction: Direction): Example | null {
  const ex = examples.find((e) => e.pair_id === picked);
  return ex && ex.text === cleanInput(text) && ex.direction === direction ? ex : null;
}
