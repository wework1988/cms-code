import { resolveModelCapabilities } from "@/lib/llm/capabilities";

export class OutputTruncatedError extends Error {
  constructor(public partialContent: string) {
    super("LLM output stopped because of the output-token limit.");
    this.name = "OutputTruncatedError";
  }
}

export function isOutputTruncated(finishReason: string | null | undefined): boolean {
  const reason = (finishReason ?? "").toLowerCase();
  return (
    reason === "length" ||
    reason === "max_tokens" ||
    reason.includes("length") ||
    reason.includes("max_token") ||
    reason.includes("token_limit")
  );
}

/** Conservative token estimate for Devanagari-heavy JSON output. */
export function estimateOutputTokensForChars(chars: number): number {
  return Math.ceil(Math.max(0, chars) / 0.8) + 256;
}

export function getModelOutputTokenLimit(): number {
  return resolveModelCapabilities().maxOutputTokens;
}

export function maxCharsPerModelCall(): number {
  const tokenBudget = Math.floor(getModelOutputTokenLimit() * 0.85);
  return Math.max(800, Math.floor((tokenBudget - 256) * 0.8));
}

export function tokensForCharBudget(chars: number): number {
  const needed = estimateOutputTokensForChars(chars);
  return Math.min(getModelOutputTokenLimit(), Math.max(512, needed));
}

/**
 * A script section needs room for both its visible Hindi JSON and DeepSeek V4's
 * internal reasoning. The ordinary per-call cap is intentionally conservative
 * for structured utility tasks, but is too small for high-quality long-form
 * narration when thinking mode is enabled.
 */
export function tokensForNarrationCharBudget(chars: number): number {
  const requested = Number(process.env.LLM_NARRATION_MAX_TOKENS ?? "");
  const configuredMinimum =
    Number.isFinite(requested) && requested >= 1_024 ? Math.floor(requested) : 65_536;
  const capabilities = resolveModelCapabilities();
  const thinkingReserve =
    capabilities.provider === "deepseek" && capabilities.reasoningSupported ? configuredMinimum : 0;

  return Math.max(tokensForCharBudget(chars), thinkingReserve);
}
