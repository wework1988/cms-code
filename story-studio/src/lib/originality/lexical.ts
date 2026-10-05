const STOP_WORDS = new Set([
  "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "is", "was", "were",
  "that", "this", "with", "from", "by", "as", "it", "be", "are", "has", "had", "have",
  "का", "की", "के", "में", "से", "को", "पर", "और", "या", "था", "थी", "थे", "है", "हैं",
  "एक", "यह", "वह", "जो", "कि", "भी", "तो", "ही", "न", "ने",
]);

export function normalizeForOverlap(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function buildShingles(text: string, size = 4): Set<string> {
  const tokens = normalizeForOverlap(text)
    .split(" ")
    .filter((t) => t.length > 2 && !STOP_WORDS.has(t));

  const shingles = new Set<string>();
  for (let i = 0; i <= tokens.length - size; i++) {
    shingles.add(tokens.slice(i, i + size).join(" "));
  }
  return shingles;
}

export function lexicalOverlapScore(sourceText: string, scriptText: string): {
  score: number;
  sharedPhrases: string[];
  status: "pass" | "warn" | "block";
} {
  const sourceShingles = buildShingles(sourceText);
  const scriptShingles = buildShingles(scriptText);
  if (sourceShingles.size === 0 || scriptShingles.size === 0) {
    return { score: 0, sharedPhrases: [], status: "pass" };
  }

  const shared: string[] = [];
  for (const shingle of scriptShingles) {
    if (sourceShingles.has(shingle)) shared.push(shingle);
  }

  const score = shared.length / Math.max(1, scriptShingles.size);
  let status: "pass" | "warn" | "block" = "pass";
  if (score > 0.08) status = "block";
  else if (score > 0.03) status = "warn";

  return { score, sharedPhrases: shared.slice(0, 10), status };
}
