// Display helpers. Data keeps the ASCII apostrophe (easy to type, what the pipeline
// normalizes to); the screen shows the modifier letter apostrophe U+02BC, the
// typographically correct glottal stop that Literata draws as a proper saltillo.

export const SALTILLO = "ʼ";

export function displayKiche(text: string): string {
  return text.replace(/'/g, SALTILLO);
}

export const LANG_LABEL = { es: "Español", quc: `K${SALTILLO}iche${SALTILLO}` } as const;

/** A model tag as people read it: our fine-tunes (tzij-YYYY-MM-…) show their base and date. */
export function modelName(tag: string | null | undefined): string {
  if (!tag) return "";
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
