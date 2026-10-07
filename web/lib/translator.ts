// The demo page: David and Goliath translate the same text side by side.
// Pure helpers, tested in tests/translator.test.ts.

import { displayKiche, LANG_LABEL } from "./kiche";
import type { ContenderName, Direction } from "./types";

export const MAX_CHARS = 280; // same limit as the page service (MAX_PHRASE_CHARS)
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

/** What one translation cost: David, the seconds his GPU instance worked on it; Goliath, his tokens. */
export interface Cost {
  usd: number;
  gpu_seconds?: number;
  usd_per_hour?: number;
  tokens?: number;
}

export interface SideResult {
  status: "ok" | "error";
  text: string;
  latency_ms: number | null;
  closeness: number | null; // chrF++ against the licensed correct translation, 0-100 (when there is one)
  cost: Cost | null;
  error: string | null;
  model: string;
}

/** The licensed correct translation the page measured against: an example's, or a typed phrase that is in the data. */
export interface Reference {
  text: string;
  source: string;
  license: string;
  url: string;
  where: "ejemplo" | "prueba" | "memoria" | "diccionario";
}

/** For a typed phrase without a correct translation: the closest human translations in the memory. */
export interface Evidence {
  memory: { source_text: string; target_text: string; source: string }[];
  words: Partial<Record<ContenderName, { word: string; in_memory: boolean }[]>>;
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

/** Seconds, one decimal: "1.4 s". */
export function formatSeconds(ms: number | null | undefined): string {
  if (ms == null || Number.isNaN(ms)) return "";
  return `${(ms / 1000).toFixed(1)} s`;
}

/** A tiny amount in dollars, readable: "US$ 0.0004". */
export function formatCost(usd: number | null | undefined): string {
  if (usd == null || Number.isNaN(usd)) return "";
  if (usd === 0) return "US$ 0";
  if (usd >= 0.01) return `US$ ${usd.toFixed(2)}`;
  const digits = Math.max(4, 1 - Math.floor(Math.log10(usd)));
  return `US$ ${usd.toFixed(digits)}`;
}

/** The same cost for 1,000 translations, where differences are easy to compare: "US$ 0.40 por cada 1,000". */
export function costPerThousand(usd: number | null | undefined): string {
  if (usd == null || Number.isNaN(usd)) return "";
  return `US$ ${(usd * 1000).toFixed(2)} por cada 1,000`;
}

/** What the cost is made of, in plain words. */
export function costBasis(cost: Cost | null | undefined): string {
  if (!cost) return "";
  if (cost.gpu_seconds != null) {
    const hour = cost.usd_per_hour != null ? ` (US$ ${cost.usd_per_hour.toFixed(2)} por hora)` : "";
    return `${cost.gpu_seconds.toFixed(1)} s de su GPU en la nube${hour}`;
  }
  if (cost.tokens != null) return `${cost.tokens.toLocaleString("es-GT")} tokens de Gemini`;
  return "";
}

/** Where a typed phrase's correct translation was found, in plain words. */
export function referenceOrigin(ref: Reference): string {
  switch (ref.where) {
    case "prueba":
      return `Esta frase está en los datos de prueba (${ref.source}), con su traducción hecha por personas.`;
    case "memoria":
      return `Esta frase ya está en la memoria de traducción de David (${ref.source}), traducida por personas.`;
    case "diccionario":
      return `Esta palabra está en el diccionario (${ref.source}).`;
    default:
      return "";
  }
}

export function failureText(result: Pick<SideResult, "status">): string | null {
  return result.status === "ok" ? null : "No pudo traducir esta frase. Intenta de nuevo.";
}

/** The example a request belongs to: only when the box still holds that exact phrase. */
export function activeExample(examples: Example[], picked: string | null, text: string, direction: Direction): Example | null {
  const ex = examples.find((e) => e.pair_id === picked);
  return ex && ex.text === cleanInput(text) && ex.direction === direction ? ex : null;
}

export async function postJSON<T = unknown>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) {
    let detail = `Error ${res.status}`;
    try {
      const payload = await res.json();
      if (typeof payload.detail === "string") detail = payload.detail;
    } catch {
      /* keep the status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

/** David's GPU service sleeps when nobody uses the page; opening the page wakes it. */
export interface DavidState {
  ready: boolean;
  since: number; // ms epoch of the last change
}

export const WAKE_GIVE_UP_MS = 6 * 60 * 1000;

export function davidStatus(state: DavidState, now: number = Date.now()): string {
  if (state.ready) return "David listo";
  if (now - state.since > WAKE_GIVE_UP_MS) return "David no responde: recarga la página";
  return "Preparando a David…";
}
