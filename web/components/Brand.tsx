// Tzij brand: the saltillo (ʼ) of ALMG K'iche' spelling is the mark. Cochineal for David,
// a slate point for Goliath. Drawn as SVG so it stays crisp on a projector.

export function Mark({ size = 40, title }: { size?: number; title?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role={title ? "img" : undefined} aria-hidden={title ? undefined : true} aria-label={title}>
      <path d="M15 4h13c1.5 9.2-1.3 22.6-9.3 35.2l-6-.3C16.6 27.8 17.6 16 15 4z" fill="var(--cochineal)" />
      <circle cx="33" cy="38" r="5.5" fill="var(--slate)" />
    </svg>
  );
}

export function Wordmark({ size = "regular" }: { size?: "regular" | "large" }) {
  return (
    <span className={`wordmark wordmark--${size}`}>
      <Mark size={size === "large" ? 56 : 36} />
      <span className="wordmark__text">Tzij</span>
    </span>
  );
}
