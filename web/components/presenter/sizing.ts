// Type scales down with length so a long sentence still fits the 16:9 frame.
export function phraseSize(text: string): number {
  const n = text.length;
  return n <= 32 ? 112 : n <= 60 ? 88 : n <= 110 ? 68 : 54;
}

// A column is ~816 px wide: about 16 characters per line at 96 px, 3 lines max.
export function answerSize(text: string): number {
  const n = text.length;
  return n <= 16 ? 96 : n <= 34 ? 80 : n <= 64 ? 64 : n <= 110 ? 52 : 44;
}
