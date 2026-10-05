import { countCharacters } from "@/lib/narration/count";

type Paragraph = { paragraphIndex: number; text: string; factIds: string[] };

function normalizeSentence(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function wordNgrams(text: string, width = 5): Set<string> {
  const words = normalizeSentence(text)
    .split(" ")
    .filter((word) => word.length >= 2);
  const ngrams = new Set<string>();
  for (let i = 0; i <= words.length - width; i++) {
    ngrams.add(words.slice(i, i + width).join(" "));
  }
  return ngrams;
}

function substantiallyRepeats(candidate: string, earlier: string): boolean {
  const normalizedCandidate = normalizeSentence(candidate);
  const normalizedEarlier = normalizeSentence(earlier);
  if (normalizedEarlier.includes(normalizedCandidate)) {
    return true;
  }
  if (
    normalizedCandidate.includes(normalizedEarlier) &&
    normalizedCandidate.length <= normalizedEarlier.length * 1.2
  ) {
    return true;
  }
  const candidateNgrams = wordNgrams(candidate);
  const earlierNgrams = wordNgrams(earlier);
  if (candidateNgrams.size < 6 || earlierNgrams.size < 6) return false;

  // Only discard a shorter recap. A longer paragraph may deliberately expand
  // on an earlier point and must remain available to length repair.
  if (candidateNgrams.size >= earlierNgrams.size * 0.8) return false;

  let shared = 0;
  for (const ngram of candidateNgrams) {
    if (earlierNgrams.has(ngram)) shared += 1;
  }
  return shared / Math.min(candidateNgrams.size, earlierNgrams.size) >= 0.45;
}

function isDegenerateRepeat(text: string): boolean {
  const normalized = normalizeSentence(text);
  if (/^(.+?)(?: \1){2,}$/.test(normalized)) return true;
  const words = normalized.split(" ").filter(Boolean);
  return words.length >= 4 && new Set(words).size <= 2;
}

function softenOverclaim(text: string): string {
  return text
    .replace(/केवल यही कारण था/g, "यह एक महत्वपूर्ण कारण था")
    .replace(/यही एकमात्र वजह थी/g, "यह एक प्रमुख वजह थी")
    .replace(/साबित करता है कि/gi, "संकेत देता है कि")
    .replace(/बिलकुल तय है कि/gi, "कई संकेत बताते हैं कि");
}

export function reduceRepetition<T extends Paragraph>(paragraphs: T[]): T[] {
  const seen = new Set<string>();
  const kept: T[] = [];
  for (const p of paragraphs) {
    const key = normalizeSentence(p.text);
    if (!key || isDegenerateRepeat(p.text) || seen.has(key)) continue;
    if (kept.some((prior) => substantiallyRepeats(p.text, prior.text))) continue;
    seen.add(key);
    kept.push(p);
  }
  return kept;
}

export function applyEditorialPolish<T extends Paragraph>(paragraphs: T[]): T[] {
  const deduped = reduceRepetition(paragraphs);
  return deduped.map((p, i) => ({
    ...p,
    paragraphIndex: i,
    text: softenOverclaim(p.text),
  })) as T[];
}

export function hasHeavyRepetition(paragraphs: Paragraph[]): boolean {
  if (paragraphs.length <= 1) return false;
  const before = paragraphs.reduce((sum, p) => sum + countCharacters(p.text), 0);
  const after = reduceRepetition(paragraphs).reduce((sum, p) => sum + countCharacters(p.text), 0);
  return before > 0 && (before - after) / before > 0.1;
}
