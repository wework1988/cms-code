const FACTUAL_TOKENS = new Set([
  "east", "india", "company", "plassey", "1757", "1600", "queen", "elizabeth",
  "battle", "british", "bengal", "trade", "charter", "monopoly",
  "ईस्ट", "इंडिया", "कंपनी", "प्लासी", "युद्ध", "व्यापार", "अनुमति",
]);

/** Normalize Hindi/Latin/Hinglish text for cross-language comparison. */
export function normalizeMultilingual(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0900-\u097F]+/g, (m) => m)
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function tokenizeMeaningful(text: string): string[] {
  return normalizeMultilingual(text)
    .split(" ")
    .filter((t) => t.length > 2 && !FACTUAL_TOKENS.has(t));
}

/** Jaccard similarity on meaningful tokens — catches paraphrased EN/HI/Hinglish overlap. */
export function semanticSimilarity(a: string, b: string): number {
  const tokensA = new Set(tokenizeMeaningful(a));
  const tokensB = new Set(tokenizeMeaningful(b));
  if (tokensA.size === 0 || tokensB.size === 0) return 0;

  let intersection = 0;
  for (const t of tokensA) {
    if (tokensB.has(t)) intersection++;
    else {
      for (const tb of tokensB) {
        if (t.includes(tb) || tb.includes(t)) {
          intersection++;
          break;
        }
      }
    }
  }
  const union = new Set([...tokensA, ...tokensB]).size;
  return union === 0 ? 0 : intersection / union;
}

export function compareOpenings(script: string, sourceTranscript: string): number {
  const scriptOpening = script.slice(0, 400);
  const sourceOpening = sourceTranscript.slice(0, 400);
  return semanticSimilarity(scriptOpening, sourceOpening);
}

export function compareEndings(script: string, sourceTranscript: string): number {
  const scriptEnding = script.slice(-400);
  const sourceEnding = sourceTranscript.slice(-400);
  return semanticSimilarity(scriptEnding, sourceEnding);
}
