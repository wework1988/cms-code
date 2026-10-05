export type ModelCapabilities = {
  provider: "deepseek" | "openai";
  model: string;
  contextWindowTokens: number;
  maxOutputTokens: number;
  outputTokenParam: "max_tokens";
  reasoningSupported: boolean;
};

const CAPABILITIES: Record<string, Omit<ModelCapabilities, "provider" | "model">> = {
  "deepseek-v4-pro": {
    contextWindowTokens: 128_000,
    maxOutputTokens: 8_192,
    outputTokenParam: "max_tokens",
    reasoningSupported: true,
  },
  "deepseek-chat": {
    contextWindowTokens: 64_000,
    maxOutputTokens: 8_192,
    outputTokenParam: "max_tokens",
    reasoningSupported: false,
  },
  "gpt-4o-mini": {
    contextWindowTokens: 128_000,
    maxOutputTokens: 16_384,
    outputTokenParam: "max_tokens",
    reasoningSupported: false,
  },
};

export function resolveModelCapabilities(input?: {
  provider?: string;
  model?: string;
}): ModelCapabilities {
  const provider = (input?.provider ?? process.env.LLM_PROVIDER ?? "deepseek").toLowerCase() as
    | "deepseek"
    | "openai";
  const model =
    input?.model ??
    (provider === "openai"
      ? process.env.OPENAI_MODEL || process.env.LLM_MODEL || "gpt-4o-mini"
      : process.env.DEEPSEEK_MODEL || process.env.LLM_MODEL || "deepseek-v4-pro");

  const fromMap = CAPABILITIES[model];
  const fallback: Omit<ModelCapabilities, "provider" | "model"> =
    provider === "openai"
      ? {
          contextWindowTokens: 128_000,
          maxOutputTokens: 8_192,
          outputTokenParam: "max_tokens",
          reasoningSupported: false,
        }
      : {
          contextWindowTokens: 64_000,
          maxOutputTokens: 6_144,
          outputTokenParam: "max_tokens",
          reasoningSupported: false,
        };

  const cap = fromMap ?? fallback;
  const outputOverride = Number(process.env.LLM_MAX_OUTPUT_TOKENS);
  const safeOutput =
    Number.isFinite(outputOverride) && outputOverride > 0
      ? Math.min(Math.floor(outputOverride), cap.maxOutputTokens)
      : cap.maxOutputTokens;

  return {
    provider,
    model,
    contextWindowTokens: cap.contextWindowTokens,
    maxOutputTokens: safeOutput,
    outputTokenParam: cap.outputTokenParam,
    reasoningSupported: cap.reasoningSupported,
  };
}

export function estimateInputTokensFromChars(chars: number): number {
  // Conservative Hindi-heavy estimate + JSON overhead.
  return Math.ceil(Math.max(0, chars) / 1.2) + 128;
}
