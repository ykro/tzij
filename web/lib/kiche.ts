// Display helpers. Data keeps the ASCII apostrophe (easy to type, what the pipeline
// normalizes to); the screen shows the modifier letter apostrophe U+02BC, the
// typographically correct glottal stop that Literata draws as a proper saltillo.

import type { Direction } from "./types";

export const SALTILLO = "ʼ";

export function displayKiche(text: string): string {
  // Apostrophes after a letter or at a word start inside K'iche' are glottal stops.
  return text.replace(/'/g, SALTILLO);
}

export function sourceIsKiche(direction: Direction): boolean {
  return direction === "quc-es";
}

export function displaySource(text: string, direction: Direction): string {
  return sourceIsKiche(direction) ? displayKiche(text) : text;
}

export function displayTarget(text: string, direction: Direction): string {
  return sourceIsKiche(direction) ? text : displayKiche(text);
}

export const LANG_LABEL = { es: "Español", quc: `K${SALTILLO}iche${SALTILLO}` } as const;

export function directionLabel(direction: Direction): string {
  return direction === "es-quc" ? `${LANG_LABEL.es} → ${LANG_LABEL.quc}` : `${LANG_LABEL.quc} → ${LANG_LABEL.es}`;
}

export function formatSeconds(ms: number | null | undefined): string {
  if (ms == null) return "—";
  return `${(ms / 1000).toLocaleString("es-GT", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} s`;
}

export function formatCost(usd: number | null | undefined): string {
  if (!usd) return "$0.00";
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(2)}`;
}

export function formatCount(n: number | null | undefined): string {
  if (n == null) return "—";
  // Thin no-break space as thousands separator: reads cleanly at 32 px and in Spanish.
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

export function modelName(tag: string | null | undefined): string {
  if (!tag) return "—";
  // Our fine-tunes are published as tzij-YYYY-MM[-recipe]: show the base and that it was tuned.
  const tuned = tag.match(/^tzij-(\d{4})-(\d{2})/);
  if (tuned) return `Gemma 4 E4B ajustado ${tuned[2]}/${tuned[1]}`;
  return tag
    .replace(/^gemma(\d)[:-]?/i, "Gemma $1 ")
    .replace(/^gemini-/i, "Gemini ")
    .replace(/-it-qat$/i, "")
    .replace(/-flash/i, " Flash")
    .replace(/\be(\d)b\b/i, (_, n) => `E${n}B`)
    .trim();
}
