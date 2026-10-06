// The translator page (/traductor/): David alone. Pure helpers, tested in tests/translator.test.ts.

import { displayKiche, LANG_LABEL } from "./kiche";
import type { Direction } from "./types";

export const MAX_CHARS = 280; // same limit as the duel service (MAX_PHRASE_CHARS)

export interface Example {
  pair_id: string;
  direction: Direction;
  text: string;
  source: string;
  url: string;
  license: string;
}

export interface TranslationResult {
  direction: Direction;
  source_text: string;
  status: "ok" | "offline" | "error";
  text: string;
  latency_ms: number | null;
  error: string | null;
  model: string;
}

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

/** K'iche' output is shown with the saltillo (ʼ); Spanish output as is. */
export function displayOutput(result: Pick<TranslationResult, "text" | "direction">): string {
  return result.direction === "es-quc" ? displayKiche(result.text) : result.text;
}

export function errorMessage(result: Pick<TranslationResult, "status" | "error">): string | null {
  if (result.status === "ok") return null;
  return result.error ? `David no pudo traducir: ${result.error}` : "David no pudo traducir esta frase.";
}

export function formatLatency(ms: number | null): string {
  if (ms == null) return "";
  return `${(ms / 1000).toLocaleString("es-GT", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;
}
