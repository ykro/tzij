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

export interface SideResult {
  status: "ok" | "error";
  text: string;
  latency_ms: number | null;
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
