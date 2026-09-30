// Type scales down with length so a long sentence still fits the 16:9 frame.
export function phraseSize(text: string): number {
  const n = text.length;
  return n <= 32 ? 112 : n <= 60 ? 88 : n <= 110 ? 68 : 54;
}

export function answerSize(text: string): number {
  const n = text.length;
  return n <= 28 ? 96 : n <= 56 ? 76 : n <= 100 ? 58 : 46;
}
