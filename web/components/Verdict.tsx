import type { VerdictName } from "@/lib/types";

// Verdicts always carry an icon and a word, never color alone (WCAG 1.4.1).
export const VERDICT_LABEL: Record<VerdictName, string> = {
  correcta: "Correcta",
  aceptable: "Aceptable",
  incorrecta: "Incorrecta",
};

export function VerdictIcon({ verdict, size = 20 }: { verdict: VerdictName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
    strokeWidth: 2.4, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };
  if (verdict === "correcta") return <svg {...common}><path d="M4.5 12.5l5 5 10-11" /></svg>;
  if (verdict === "aceptable") return <svg {...common}><path d="M4 13.5c2.5-4 5.5-4 8 0s5.5 4 8 0" /></svg>;
  return <svg {...common}><path d="M6 6l12 12M18 6L6 18" /></svg>;
}
