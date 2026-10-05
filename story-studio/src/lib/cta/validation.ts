import { countCharacters } from "@/lib/narration/count";
import type { ResolvedCtaConfig } from "@/lib/cta/config";

export type ParagraphWithMeta = {
  paragraphIndex: number;
  text: string;
  factIds: string[];
  paragraphRole?: "narrative" | "cta_mid" | "cta_closing";
};

const CTA_CUES = [
  "कमेंट",
  "टिप्पणी",
  "बताइए",
  "सोचते",
  "आपकी राय",
  "जुड़िए",
  "सब्सक्राइब",
  "subscribe",
  "लाइक",
  "share",
  "शेयर",
];

const SENSITIVE_CUES = [
  "मौत",
  "हत्या",
  "त्रासदी",
  "पीड़ित",
  "हमला",
  "victim",
  "death",
  "massacre",
];

function normalize(s: string): string {
  return s.replace(/\s+/g, " ").trim().toLowerCase();
}

export function isCtaText(text: string): boolean {
  const t = normalize(text);
  return CTA_CUES.some((cue) => t.includes(cue.toLowerCase()));
}

export function isSensitiveParagraph(text: string): boolean {
  const t = normalize(text);
  return SENSITIVE_CUES.some((cue) => t.includes(cue.toLowerCase()));
}

export function ctaContainsFactualAssertion(text: string): boolean {
  const t = normalize(text);
  return /\b(19|20)\d{2}\b/.test(t) || /\d/.test(t);
}

export function hasSubscribeIntent(text: string): boolean {
  const t = normalize(text);
  return t.includes("सब्सक्राइब") || t.includes("subscribe") || t.includes("जुड़े रह");
}

export function detectCtaParagraphs(paragraphs: ParagraphWithMeta[]): number[] {
  return paragraphs
    .filter((p) => isCtaText(p.text))
    .map((p) => p.paragraphIndex);
}

function keywordSnippet(text: string): string {
  const words = text
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .map((w) => w.trim())
    .filter((w) => w.length >= 4);
  return words.slice(0, 6).join(" ");
}

export function buildMidCtaText(contextText: string, respectful: boolean): string {
  const context = keywordSnippet(contextText);
  if (respectful) {
    return `${context ? `${context} के इस पहलू` : "इस पहलू"} पर आपकी सोच क्या है, कमेंट में शांत और सम्मानजनक तरीके से अपनी राय जरूर बताइए।`;
  }
  return `${context ? `${context} जैसे मुद्दे` : "इस मुद्दे"} पर आपकी राय क्या है, कमेंट में जरूर बताइए।`;
}

export function buildClosingCtaText(config: ResolvedCtaConfig): string {
  const preferred = config.preferredClosingWording?.trim();
  if (preferred) return preferred;
  if (config.channelSignOff?.trim()) return config.channelSignOff.trim();
  const channelPart = config.channelName ? `${config.channelName} पर ` : "";
  return `अगर आप ऐसी गहरी डॉक्यूमेंट्री कहानियां पसंद करते हैं, तो ${channelPart}आने वाली कहानियों के लिए चैनल को सब्सक्राइब करें।`;
}

export function recommendedMidIndices(paragraphs: ParagraphWithMeta[], count: number): number[] {
  if (count <= 0 || paragraphs.length < 3) return [];
  const windows = count === 1 ? [[0.45, 0.6]] : [[0.3, 0.45], [0.65, 0.8]];
  const total = paragraphs.reduce((sum, p) => sum + countCharacters(p.text), 0) || 1;
  const cumulative: number[] = [];
  let running = 0;
  for (const p of paragraphs) {
    running += countCharacters(p.text);
    cumulative.push(running / total);
  }

  const used = new Set<number>();
  const picks: number[] = [];

  for (const [start, end] of windows) {
    let candidate = -1;
    let candidateDist = Number.POSITIVE_INFINITY;
    for (let i = 1; i < paragraphs.length - 1; i++) {
      if (used.has(i)) continue;
      if (isSensitiveParagraph(paragraphs[i].text)) continue;
      const ratio = cumulative[i];
      if (ratio < start || ratio > end) continue;
      const center = (start + end) / 2;
      const dist = Math.abs(center - ratio);
      if (dist < candidateDist) {
        candidate = i;
        candidateDist = dist;
      }
    }
    if (candidate >= 0) {
      picks.push(candidate);
      used.add(candidate);
    }
  }

  return picks;
}

export function validateCtaCoverage(
  paragraphs: ParagraphWithMeta[],
  config: ResolvedCtaConfig,
): {
  ok: boolean;
  midFound: number;
  closingFound: boolean;
  duplicateDetected: boolean;
  note?: string;
} {
  const ctaIndices = detectCtaParagraphs(paragraphs);
  const closingIndex = paragraphs.length - 1;
  const closingFound = ctaIndices.includes(closingIndex) || hasSubscribeIntent(paragraphs[closingIndex]?.text ?? "");
  const midFound = ctaIndices.filter((idx) => idx !== closingIndex).length;
  const normalized = ctaIndices.map((idx) => normalize(paragraphs[idx].text));
  const duplicateDetected = new Set(normalized).size !== normalized.length;
  const ok = midFound >= config.midCountEffective && (!config.closingRequired || closingFound) && !duplicateDetected;
  return {
    ok,
    midFound,
    closingFound,
    duplicateDetected,
    note: ok ? undefined : "CTA requirements were not fully satisfied.",
  };
}

export function ctaShareExceedsLimit(ctaChars: number, totalNarrationChars: number): boolean {
  if (totalNarrationChars <= 0) return false;
  return ctaChars / totalNarrationChars > 0.05;
}
