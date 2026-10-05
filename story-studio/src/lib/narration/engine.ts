import { parseJsonSafe } from "@/lib/llm/json";
import type { ResolvedCtaConfig } from "@/lib/cta/config";
import {
  buildClosingCtaText,
  buildMidCtaText,
  ctaContainsFactualAssertion,
  ctaShareExceedsLimit,
  detectCtaParagraphs,
  hasSubscribeIntent,
  isSensitiveParagraph,
  recommendedMidIndices,
  validateCtaCoverage,
} from "@/lib/cta/validation";
import {
  estimateOutputTokensForChars,
  isOutputTruncated,
  maxCharsPerModelCall,
  tokensForNarrationCharBudget,
} from "@/lib/llm/errors";
import { allocateBeatBudgets, chunkBeatsByCharBudget, splitOversizedBeat, type BudgetBeat } from "@/lib/narration/budget";
import {
  assembleNarration,
  countCharacters,
  endsCoherently,
  formatLengthMissMessage,
  isInLengthRange,
  lengthRange,
  MAX_LENGTH_REPAIR_PASSES,
  resolveTargetCharCount,
  splitNarrationParagraphs,
  trimAtSentenceBoundary,
  type LengthRange,
  type LengthStatus,
} from "@/lib/narration/count";
import { NARRATION_ONLY_RULES, sanitizeNarration } from "@/lib/narration/sanitize";
import { applyEditorialPolish } from "@/lib/narration/editorial";
import { parseBeatParagraphs } from "@/lib/pipeline/normalize-llm";
import {
  buildBeatChunkPrompt,
  buildExpandPrompt,
  buildTrimPrompt,
  HINDI_WRITER_SYSTEM,
} from "@/lib/prompts";
import { SYSTEM_ISOLATION_RULES } from "@/lib/prompts/profile";

export type CompletionFn = (args: {
  prompt: string;
  system: string;
  maxTokens: number;
  jsonMode?: boolean;
  allowReasoning?: boolean;
  trace?: {
    stage: string;
    chunkId?: string;
    callId?: string;
    attempt?: number;
  };
}) => Promise<{ content: string; finishReason: string }>;

export type NarrationParagraph = {
  paragraphIndex: number;
  text: string;
  factIds: string[];
  beatNumber?: number;
  paragraphRole?: "narrative" | "cta_mid" | "cta_closing";
};

export type NarrationDraft = {
  paragraphs: NarrationParagraph[];
  narration: string;
  charCount: number;
  target: number;
  min: number;
  max: number;
  status: LengthStatus;
  message?: string;
  truncatedOutput: boolean;
};

export type NarrationGenerateInput = {
  targetCharCount: number | null | undefined;
  brief: Record<string, unknown>;
  style: Record<string, unknown>;
  beats: Array<{
    beatNumber: number;
    purpose: string;
    shortDescription: string;
    claimIds: string[];
    narrativeRole: string;
  }>;
  facts: Array<{ factId: string; neutralStatement: string; storyImportance?: string }>;
  avoidanceRules: string[];
  validFactIds: Set<string>;
  cta: ResolvedCtaConfig;
  channelStyle?: Record<string, unknown>;
  narrativePreferences?: {
    approach: string;
    approachCustom?: string;
    openingHook: string;
    openingHookCustom?: string;
  };
  onProgress?: (message: string) => void | Promise<void>;
};

const WRITER_SYSTEM = `${HINDI_WRITER_SYSTEM}\n\n${SYSTEM_ISOLATION_RULES}\n\n${NARRATION_ONLY_RULES}`;

function withCtaCoverage(
  paragraphs: NarrationParagraph[],
  config: ResolvedCtaConfig,
): { paragraphs: NarrationParagraph[]; note?: string } {
  if (paragraphs.length === 0) return { paragraphs };
  let next = [...paragraphs];
  let note: string | undefined;

  // Remove exact duplicate CTA paragraphs first.
  const seen = new Set<string>();
  next = next.filter((p, index) => {
    const isCta = detectCtaParagraphs([{ paragraphIndex: index, text: p.text, factIds: p.factIds }]).length > 0;
    if (!isCta) return true;
    // CTAs are placed by this function. Dropping model-authored ones prevents
    // factual or awkward prompts such as asking viewers to comment on a date.
    if (!p.paragraphRole?.startsWith("cta")) return false;
    const norm = p.text.replace(/\s+/g, " ").trim().toLowerCase();
    if (seen.has(norm)) return false;
    seen.add(norm);
    return true;
  });

  const midsNeeded = config.midCountEffective;
  const currentCtaIndices = detectCtaParagraphs(
    next.map((p, i) => ({ paragraphIndex: i, text: p.text, factIds: p.factIds })),
  );
  const closingIdx = next.length - 1;
  const closingText = next[closingIdx]?.text ?? "";
  const hasClosing =
    hasSubscribeIntent(closingText) ||
    Boolean(
      config.channelSignOff &&
      hasSubscribeIntent(config.channelSignOff) &&
      closingText.includes(config.channelSignOff),
    );
  const midNow = currentCtaIndices.filter((i) => i !== closingIdx).length;

  if (!hasClosing && config.closingRequired) {
    const ending = buildClosingCtaText(config);
    if (next.length > 0 && next[next.length - 1].text.trim().length < 240) {
      next[next.length - 1] = {
        ...next[next.length - 1],
        text: `${next[next.length - 1].text.trim()} ${ending}`.trim(),
        paragraphRole: "cta_closing",
      };
    } else {
      next.push({
        paragraphIndex: next.length,
        text: ending,
        factIds: [],
        paragraphRole: "cta_closing",
      });
    }
  }

  if (midNow < midsNeeded) {
    const picks = recommendedMidIndices(
      next.map((p, i) => ({ paragraphIndex: i, text: p.text, factIds: p.factIds })),
      midsNeeded - midNow,
    );

    for (const idx of picks) {
      const context = next[idx]?.text ?? "";
      const respectful = isSensitiveParagraph(context);
      const line = buildMidCtaText(context, respectful);
      next.splice(idx + 1, 0, {
        paragraphIndex: idx + 1,
        text: line,
        factIds: ctaContainsFactualAssertion(line) ? next[idx]?.factIds ?? [] : [],
        paragraphRole: "cta_mid",
      });
    }
    if (picks.length < midsNeeded - midNow) {
      note = "Could not place all requested middle CTAs naturally; retained available placements.";
    }
  }

  next = next.map((p, i) => ({ ...p, paragraphIndex: i }));

  for (let i = 0; i < next.length; i++) {
    const role = next[i].paragraphRole;
    if (!role?.startsWith("cta")) continue;
    if (!ctaContainsFactualAssertion(next[i].text)) continue;
    if (next[i].factIds.length > 0) continue;
    const fallbackFacts =
      next[i - 1]?.factIds?.length
        ? next[i - 1].factIds
        : next[i + 1]?.factIds?.length
          ? next[i + 1].factIds
          : [];
    next[i] = { ...next[i], factIds: fallbackFacts };
  }

  const totalChars = countCharacters(assembleNarration(next));
  const ctaChars = next
    .filter((p) => hasSubscribeIntent(p.text) || isSensitiveParagraph(p.text) || p.paragraphRole?.startsWith("cta"))
    .reduce((sum, p) => sum + countCharacters(p.text), 0);
  if (ctaShareExceedsLimit(ctaChars, totalChars)) {
    next = next.map((p) => {
      if (p.paragraphRole?.startsWith("cta") && p.text.includes("।")) {
        return { ...p, text: `${p.text.split("।")[0]}।` };
      }
      return p;
    });
  }

  return { paragraphs: next, note };
}

function finalizeDraft(
  paragraphs: NarrationParagraph[],
  range: LengthRange,
  validFactIds: Set<string>,
  ctaConfig: ResolvedCtaConfig,
  extras?: { truncatedOutput?: boolean; status?: LengthStatus; message?: string },
): NarrationDraft {
  const ctaApplied = withCtaCoverage(paragraphs, ctaConfig);
  const cleaned = ctaApplied.paragraphs
    .map((p, i) => ({
      ...p,
      paragraphIndex: i,
      text: sanitizeNarration(p.text),
      factIds: filterFactIds(p.factIds, validFactIds),
      paragraphRole: p.paragraphRole,
    }))
    .filter((p) => p.text.trim());

  const narration = assembleNarration(cleaned);
  const charCount = countCharacters(narration);
  const truncatedOutput = Boolean(extras?.truncatedOutput);
  const inRange = isInLengthRange(charCount, range) && endsCoherently(narration) && !truncatedOutput;
  const status: LengthStatus = extras?.status && extras.status !== "ready"
    ? extras.status
    : inRange
      ? "ready"
      : "target_not_reached";

  return {
    paragraphs: cleaned,
    narration,
    charCount,
    target: range.target,
    min: range.min,
    max: range.max,
    status: inRange ? "ready" : status === "expanding" || status === "trimming" || status === "drafting" ? status : "target_not_reached",
    truncatedOutput,
    message: !inRange
      ? extras?.message ?? formatLengthMissMessage(charCount, range.target)
      : extras?.message ?? ctaApplied.note,
  };
}

function filterFactIds(ids: string[], valid: Set<string>): string[] {
  return ids.filter((id) => valid.has(id));
}

function continuityFor(paragraphs: NarrationParagraph[]) {
  if (paragraphs.length === 0) {
    return { continuitySummary: "", previousEnding: "" };
  }
  const last = paragraphs[paragraphs.length - 1].text;
  const previousEnding = last.slice(Math.max(0, last.length - 400));
  const continuitySummary = paragraphs
    .slice(-2)
    .map((p) => p.text.replace(/\s+/g, " ").slice(0, 180))
    .join(" / ");
  return { continuitySummary, previousEnding };
}

async function requestParagraphs(
  complete: CompletionFn,
  prompt: string,
  charBudget: number,
  trace: { stage: string; chunkId?: string; callId?: string; attempt?: number },
): Promise<{ paragraphs: Array<{ beatNumber?: number; text: string; factIds: string[] }>; truncated: boolean }> {
  try {
    const result = await complete({
      prompt,
      system: WRITER_SYSTEM,
      maxTokens: tokensForNarrationCharBudget(charBudget),
      jsonMode: true,
      trace,
    });
    const truncated = isOutputTruncated(result.finishReason);
    const parsed = parseBeatParagraphs(parseJsonSafe(result.content));
    return { paragraphs: parsed, truncated };
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    if (
      msg.includes("LLM output stopped because of the output-token limit") ||
      msg.includes("finish_reason: length")
    ) {
      // Treat token-stop as recoverable so callers can subdivide/retry work.
      return { paragraphs: [], truncated: true };
    }
    throw error;
  }
}

export async function draftFromBeats(
  input: NarrationGenerateInput,
  complete: CompletionFn,
): Promise<{ paragraphs: NarrationParagraph[]; truncatedOutput: boolean }> {
  const range = lengthRange(resolveTargetCharCount(input.targetCharCount));
  const budgeted = allocateBeatBudgets(input.beats, range.target);
  const maxPerCall = maxCharsPerModelCall();
  const chunks = chunkBeatsByCharBudget(budgeted, maxPerCall);

  const collected: NarrationParagraph[] = [];
  let truncatedOutput = false;

  for (let i = 0; i < chunks.length; i++) {
    await input.onProgress?.(`Writing section ${i + 1} of ${chunks.length}`);
    const chunk = chunks[i];
    const produced = await writeChunk(input, chunk, collected, i === 0, i === chunks.length - 1, complete);
    truncatedOutput = truncatedOutput || produced.truncated;
    collected.push(...produced.paragraphs);
  }

  return { paragraphs: collected, truncatedOutput };
}

async function writeChunk(
  input: NarrationGenerateInput,
  chunk: BudgetBeat[],
  prior: NarrationParagraph[],
  isOpeningChunk: boolean,
  isClosingChunk: boolean,
  complete: CompletionFn,
): Promise<{ paragraphs: NarrationParagraph[]; truncated: boolean }> {
  const chunkBudget = chunk.reduce((sum, b) => sum + b.characterBudget, 0);
  const { continuitySummary, previousEnding } = continuityFor(prior);
  const chunkFactIds = new Set(chunk.flatMap((b) => b.claimIds));
  const facts = input.facts.filter((f) => chunkFactIds.has(f.factId) || chunkFactIds.size === 0);
  const range = lengthRange(resolveTargetCharCount(input.targetCharCount));

  const prompt = buildBeatChunkPrompt({
    targetCharCount: range.target,
    minChars: range.min,
    maxChars: range.max,
    chunkCharBudget: chunkBudget,
    brief: { ...input.brief, targetCharCount: range.target },
    style: input.style,
    beats: chunk,
    facts: facts.length > 0 ? facts : input.facts,
    avoidanceRules: input.avoidanceRules,
    cta: input.cta,
    narrativePreferences: input.narrativePreferences,
    continuitySummary,
    previousEnding,
    isOpeningChunk,
    isClosingChunk,
  });

  const traceBase = {
    stage: "script_write",
    chunkId: chunk
      .map((b) =>
        b.segmentCount && b.segmentIndex
          ? `${b.beatNumber}.${b.segmentIndex}`
          : String(b.beatNumber),
      )
      .join(","),
    callId: `chunk-${prior.length}-${chunk.length}`,
  };
  const { paragraphs, truncated } = await requestParagraphs(complete, prompt, chunkBudget, traceBase);

  if (truncated && chunk.length > 1) {
    const paragraphs: NarrationParagraph[] = [];
    let anyTruncated = false;
    for (const beat of chunk) {
      const single = await writeChunk(
        input,
        [beat],
        [...prior, ...paragraphs],
        isOpeningChunk && paragraphs.length === 0 && prior.length === 0,
        isClosingChunk && beat === chunk[chunk.length - 1],
        complete,
      );
      anyTruncated = anyTruncated || single.truncated;
      paragraphs.push(...single.paragraphs);
    }
    return { paragraphs, truncated: anyTruncated };
  }
  if (truncated && chunk.length === 1 && chunk[0].characterBudget > 850) {
    const smaller = splitOversizedBeat(chunk[0], Math.max(700, Math.floor(chunk[0].characterBudget / 2)));
    const recursed: NarrationParagraph[] = [];
    let anyTruncated = false;
    for (let i = 0; i < smaller.length; i++) {
      const part = await writeChunk(
        input,
        [smaller[i]],
        [...prior, ...recursed],
        isOpeningChunk && i === 0,
        isClosingChunk && i === smaller.length - 1,
        complete,
      );
      anyTruncated = anyTruncated || part.truncated;
      recursed.push(...part.paragraphs);
    }
    return { paragraphs: recursed, truncated: anyTruncated };
  }

  const mapped: NarrationParagraph[] = paragraphs.map((p, i) => ({
    paragraphIndex: prior.length + i,
    text: sanitizeNarration(p.text),
    factIds: filterFactIds(p.factIds.length > 0 ? p.factIds : chunk[Math.min(i, chunk.length - 1)]?.claimIds ?? [], input.validFactIds),
    beatNumber: p.beatNumber ?? chunk[Math.min(i, chunk.length - 1)]?.beatNumber,
  }));

  return { paragraphs: mapped.filter((p) => p.text), truncated };
}

export async function repairNarrationLength(
  draft: NarrationDraft,
  input: Pick<
    NarrationGenerateInput,
    "facts" | "validFactIds" | "cta" | "narrativePreferences" | "onProgress"
  >,
  complete: CompletionFn,
): Promise<NarrationDraft> {
  const range: LengthRange = { target: draft.target, min: draft.min, max: draft.max };
  let current = draft;

  for (let pass = 0; pass < MAX_LENGTH_REPAIR_PASSES; pass++) {
    await input.onProgress?.(`Length repair pass ${pass + 1} of ${MAX_LENGTH_REPAIR_PASSES}`);
    if (isInLengthRange(current.charCount, range) && endsCoherently(current.narration) && !current.truncatedOutput) {
      return { ...current, status: "ready", message: undefined, truncatedOutput: false };
    }

    if (current.charCount < range.min) {
      const shortfall = range.min - current.charCount;
      current = await expandDraft(current, input, complete, shortfall, "expanding");
      continue;
    }

    if (current.charCount > range.max) {
      const excess = current.charCount - range.max;
      current = await trimDraft(
        current,
        complete,
        excess,
        input.validFactIds,
        input.cta,
        input.narrativePreferences,
      );
    }
  }

  if (isInLengthRange(current.charCount, range) && endsCoherently(current.narration) && !current.truncatedOutput) {
    return finalizeDraft(current.paragraphs, range, input.validFactIds, input.cta, {
      truncatedOutput: false,
      status: "ready",
      message: undefined,
    });
  }

  return finalizeDraft(current.paragraphs, range, input.validFactIds, input.cta, {
    truncatedOutput: current.truncatedOutput,
    status: "target_not_reached",
  });
}

async function expandDraft(
  draft: NarrationDraft,
  input: Pick<
    NarrationGenerateInput,
    "facts" | "validFactIds" | "cta" | "narrativePreferences" | "onProgress"
  >,
  complete: CompletionFn,
  shortfall: number,
  status: LengthStatus,
): Promise<NarrationDraft> {
  const range = lengthRange(draft.target);
  const next = [...draft.paragraphs];
  let remaining = shortfall;
  const candidates = next
    .map((p, idx) => ({ idx, p }))
    .filter(({ p }) => !p.paragraphRole?.startsWith("cta"))
    .sort((a, b) => countCharacters(a.p.text) - countCharacters(b.p.text))
    .slice(0, 8);

  for (const candidate of candidates) {
    if (remaining <= 0) break;
    const before = next[Math.max(0, candidate.idx - 1)]?.text ?? "";
    const center = next[candidate.idx]?.text ?? "";
    const after = next[Math.min(next.length - 1, candidate.idx + 1)]?.text ?? "";
    const context = [before, center, after].filter(Boolean).join("\n\n");
    const supportedFacts = input.facts.filter((f) => next[candidate.idx]?.factIds.includes(f.factId));
    const expandBy = Math.min(remaining, 1400);
    const { paragraphs, truncated } = await requestParagraphs(
      complete,
      buildExpandPrompt({
        shortfall: expandBy,
        target: range.target,
        min: range.min,
        max: range.max,
        narration: context,
        facts: supportedFacts.length > 0 ? supportedFacts : input.facts.slice(0, 8),
        cta: input.cta,
        narrativePreferences: input.narrativePreferences,
      }),
      Math.min(2200, expandBy + 700),
      { stage: "length_expand_segment", callId: `expand-p${candidate.idx}` },
    );
    if (truncated || paragraphs.length === 0) continue;
    const rawAddition = paragraphs
      .map((p) => sanitizeNarration(p.text))
      .find((text) => text && text !== center);
    const addition = rawAddition
      ? trimAtSentenceBoundary(rawAddition, Math.min(1800, expandBy + 350))
      : "";
    if (!addition) continue;
    next.splice(candidate.idx + 1, 0, {
      paragraphIndex: 0,
      text: addition,
      factIds: filterFactIds(
        paragraphs[0]?.factIds?.length ? paragraphs[0].factIds : next[candidate.idx].factIds,
        input.validFactIds,
      ),
      beatNumber: next[candidate.idx].beatNumber,
    });
    remaining = Math.max(0, range.min - countCharacters(assembleNarration(next)));
  }

  return finalizeDraft(
    next.map((p, i) => ({ ...p, paragraphIndex: i })),
    range,
    input.validFactIds,
    input.cta,
    { truncatedOutput: false, status },
  );
}

async function trimDraft(
  draft: NarrationDraft,
  complete: CompletionFn,
  excess: number,
  validFactIds: Set<string>,
  cta: ResolvedCtaConfig,
  narrativePreferences?: {
    approach: string;
    approachCustom?: string;
    openingHook: string;
    openingHookCustom?: string;
  },
): Promise<NarrationDraft> {
  const range = lengthRange(draft.target);
  const next = [...draft.paragraphs];
  let currentChars = countCharacters(assembleNarration(next));
  const protectedTail = Math.max(1, Math.floor(next.length * 0.15));
  const candidates = next
    .map((p, idx) => ({ idx, p }))
    .filter(({ idx, p }) => idx < next.length - protectedTail && !p.paragraphRole?.startsWith("cta"))
    .sort((a, b) => countCharacters(b.p.text) - countCharacters(a.p.text))
    .slice(0, 8);

  for (const candidate of candidates) {
    if (currentChars <= range.max) break;
    const targetLocal = Math.max(180, Math.floor(countCharacters(candidate.p.text) * 0.7));
    const { paragraphs, truncated } = await requestParagraphs(
      complete,
      buildTrimPrompt({
        excess: currentChars - range.max,
        target: range.target,
        min: range.min,
        max: range.max,
        narration: candidate.p.text,
        cta,
        narrativePreferences,
      }),
      Math.min(1800, targetLocal + 500),
      { stage: "length_trim_segment", callId: `trim-p${candidate.idx}` },
    );
    if (truncated || paragraphs.length === 0) continue;
    const replacement = sanitizeNarration(paragraphs[0]?.text ?? "");
    if (!replacement) continue;
    next[candidate.idx] = {
      ...next[candidate.idx],
      text: trimAtSentenceBoundary(replacement, targetLocal),
      factIds: filterFactIds(paragraphs[0]?.factIds ?? next[candidate.idx].factIds, validFactIds),
    };
    currentChars = countCharacters(assembleNarration(next));
  }

  const assembled = assembleNarration(next);
  const fallbackTrimmed = currentChars > range.max ? trimAtSentenceBoundary(assembled, range.max) : assembled;
  const parts = splitNarrationParagraphs(fallbackTrimmed).map((text, i) => ({
    paragraphIndex: i,
    text,
    factIds: next[i]?.factIds ?? draft.paragraphs[i]?.factIds ?? [],
  }));

  return finalizeDraft(parts, range, validFactIds, cta, {
    truncatedOutput: false,
    status: "trimming",
  });
}

export async function generateNarration(
  input: NarrationGenerateInput,
  complete: CompletionFn,
): Promise<NarrationDraft> {
  const range = lengthRange(resolveTargetCharCount(input.targetCharCount));
  const { paragraphs, truncatedOutput } = await draftFromBeats(input, complete);
  const polishedDraft = applyEditorialPolish(
    paragraphs.map((p, i) => ({
      paragraphIndex: i,
      text: p.text,
      factIds: p.factIds,
    })),
  );
  const initial = finalizeDraft(polishedDraft, range, input.validFactIds, input.cta, {
    truncatedOutput,
    status: truncatedOutput ? "target_not_reached" : "drafting",
  });
  let repaired = await repairNarrationLength(initial, input, complete);

  const ctaCheck = validateCtaCoverage(
    repaired.paragraphs.map((p, i) => ({
      paragraphIndex: i,
      text: p.text,
      factIds: p.factIds,
      paragraphRole: p.paragraphRole,
    })),
    input.cta,
  );

  if (!ctaCheck.ok) {
    repaired = finalizeDraft(repaired.paragraphs, range, input.validFactIds, input.cta, {
      status: repaired.status,
      message: ctaCheck.note ?? repaired.message,
    });
  }

  const polished = applyEditorialPolish(
    repaired.paragraphs.map((p, i) => ({
      paragraphIndex: i,
      text: p.text,
      factIds: p.factIds,
    })),
  );
  repaired = finalizeDraft(polished, range, input.validFactIds, input.cta, {
    status: repaired.status,
    truncatedOutput: repaired.truncatedOutput,
    message: repaired.status === "target_not_reached" ? undefined : repaired.message,
  });

  return repaired;
}

export function requiredTokensExceedModelLimit(targetChars: number): boolean {
  return estimateOutputTokensForChars(targetChars) > Math.floor(maxCharsPerModelCall() / 0.8 + 256);
}

export { WRITER_SYSTEM };
