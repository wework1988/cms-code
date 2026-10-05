const EXTRA_SECTION_HEADINGS = [
  /^#{1,6}\s+/,
  /^(pre-?write|prewrite)\s+validator/i,
  /^fact[- ]check/i,
  /^research\s+(report|notes?)/i,
  /^source\s+(list|notes?|citations?)/i,
  /^originality\s+(report|qa|review)/i,
  /^character[- ]count/i,
  /^title\s+(options?|ideas?)/i,
  /^thumbnail/i,
  /^animation\s+notes?/i,
  /^character\s+sheet/i,
  /^production\s+(notes?|instructions?)/i,
  /^validator/i,
  /^beat\s+\d+/i,
  /^दृश्य\s*\d+/,
  /^scene\s+\d+/i,
  /^internal\s+notes?/i,
];

const EXTRA_DELIVERABLE_PATTERN =
  /fact[- ]check|research report|character sheet|thumbnail options?|title options?|animation notes?|pre-?write validator|source list|originality report|production instructions?/i;

export const NARRATION_ONLY_RULES = `
OUTPUT MODE: Narration only.
Write continuous spoken Devanagari Hindi with paragraph breaks.
Do not include: pre-write validators, fact-check or research sections, source lists,
citations as separate sections, originality reports, character-count reports,
titles, thumbnail options, animation notes, character sheets, production instructions,
JSON, fact IDs, beat headings, or English meta commentary.
Do not repeat the full script twice. Return paragraph text once.
This output-mode rule overrides any prompt-profile request for extra deliverables.
Keep the profile's writing style, vocabulary and pacing.
`.trim();

export function stripExtraDeliverableInstructions(text: string | null | undefined): string {
  if (!text?.trim()) return "";
  return text
    .split(/\n+/)
    .filter((line) => !EXTRA_DELIVERABLE_PATTERN.test(line) && !EXTRA_SECTION_HEADINGS.some((re) => re.test(line.trim())))
    .join("\n")
    .replace(/fact[- ]check|research report|character sheet|thumbnail options?|title options?|animation notes?/gi, "")
    .trim();
}

export function sanitizeNarration(text: string): string {
  const withoutFences = text.replace(/```(?:json|markdown|md|text)?\s*[\s\S]*?```/g, "").trim();
  const lines = withoutFences.split("\n");
  const kept: string[] = [];
  let skippingSection = false;

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      kept.push("");
      continue;
    }

    if (EXTRA_SECTION_HEADINGS.some((re) => re.test(trimmed))) {
      skippingSection = true;
      continue;
    }

    if (skippingSection && /^[A-Z].{0,40}:$/.test(trimmed)) {
      continue;
    }

    if (skippingSection && /[।.!?]$/.test(trimmed)) {
      skippingSection = false;
    }

    if (skippingSection) continue;

    if (/^fact-\d+$/i.test(trimmed)) continue;
    if (/editorial draft|not legal clearance|^\s*---+\s*$/i.test(trimmed)) continue;
    if (/^\s*\{[\s\S]*\}\s*$/.test(trimmed)) continue;

    kept.push(line);
  }

  return kept
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export function buildNarrationExport(narration: string): string {
  return sanitizeNarration(narration);
}
