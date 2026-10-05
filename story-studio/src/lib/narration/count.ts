/** Unicode code-point count — the only length measure for narration. */
export function countCharacters(text: string): number {
  return Array.from(text ?? "").length;
}

export const NARRATION_SEPARATOR = "\n\n";
export const LENGTH_TOLERANCE = 0.05;
export const DEFAULT_TARGET_CHARS = 6000;
export const MAX_LENGTH_REPAIR_PASSES = 3;

export type LengthRange = {
  target: number;
  min: number;
  max: number;
};

export type LengthStatus =
  | "drafting"
  | "expanding"
  | "trimming"
  | "ready"
  | "target_not_reached";

export function resolveTargetCharCount(saved: number | null | undefined): number {
  if (typeof saved === "number" && Number.isFinite(saved) && saved > 0) return Math.round(saved);
  return DEFAULT_TARGET_CHARS;
}

export function lengthRange(target: number): LengthRange {
  const t = resolveTargetCharCount(target);
  return {
    target: t,
    min: Math.round(t * (1 - LENGTH_TOLERANCE)),
    max: Math.round(t * (1 + LENGTH_TOLERANCE)),
  };
}

export function assembleNarration(paragraphs: Array<{ text: string } | string>): string {
  return paragraphs
    .map((p) => (typeof p === "string" ? p : p.text).trim())
    .filter(Boolean)
    .join(NARRATION_SEPARATOR);
}

export function splitNarrationParagraphs(narration: string): string[] {
  return narration
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export function isInLengthRange(actual: number, range: LengthRange): boolean {
  return actual >= range.min && actual <= range.max;
}

export function lengthStatusLabel(status: LengthStatus): string {
  switch (status) {
    case "drafting":
      return "Drafting";
    case "expanding":
      return "Expanding";
    case "trimming":
      return "Trimming";
    case "ready":
      return "Ready";
    case "target_not_reached":
      return "Target not reached";
  }
}

export function formatLengthMissMessage(actual: number, target: number): string {
  return `Draft saved: ${actual.toLocaleString("en-IN")} / ${target.toLocaleString("en-IN")} characters. Length target not reached.`;
}

export function endsCoherently(text: string): boolean {
  const trimmed = text.trim();
  if (!trimmed) return false;
  return /[।.!?…"'”’]$/.test(trimmed);
}

/** Trim from the end at sentence boundaries only. Never cuts mid-sentence. */
export function trimAtSentenceBoundary(text: string, maxChars: number): string {
  if (countCharacters(text) <= maxChars) return text;

  const sentences = text
    .split(/(?<=[।.!?…])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);

  if (sentences.length <= 1) return text;

  let kept = sentences[0];
  for (let i = 1; i < sentences.length; i++) {
    const candidate = `${kept} ${sentences[i]}`.replace(/\s+/g, " ").trim();
    if (countCharacters(candidate) > maxChars) break;
    kept = candidate;
  }

  return kept;
}
