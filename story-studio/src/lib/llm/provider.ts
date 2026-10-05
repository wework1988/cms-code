import type { ZodType } from "zod";
import { extractJson, parseJsonSafe } from "@/lib/llm/json";
import { isOutputTruncated } from "@/lib/llm/errors";
import { estimateInputTokensFromChars, resolveModelCapabilities } from "@/lib/llm/capabilities";

export interface StructuredGenerationOptions {
  maxTokens?: number;
  jsonMode?: boolean;
  rejectTruncation?: boolean;
  /**
   * Long-form narration needs its entire output budget for visible prose.
   * DeepSeek V4 thinking is enabled by default and can otherwise consume that
   * budget before the model emits any `content`.
   */
  allowReasoning?: boolean;
  trace?: LLMTrace;
}

export type LLMCompletion = {
  content: string;
  finishReason: string;
  model?: string;
  usage?: {
    promptTokens?: number;
    completionTokens?: number;
    totalTokens?: number;
    reasoningTokens?: number;
  };
};

export type LLMTrace = {
  runId?: string;
  stage?: string;
  callId?: string;
  chunkId?: string;
  attempt?: number;
};

export interface LLMProvider {
  complete(args: {
    prompt: string;
    system?: string;
    maxTokens?: number;
    jsonMode?: boolean;
    allowReasoning?: boolean;
    trace?: LLMTrace;
  }): Promise<LLMCompletion>;
  generateStructured<T>(
    prompt: string,
    schema: ZodType<T>,
    system?: string,
    options?: StructuredGenerationOptions,
  ): Promise<T>;
  generateText(prompt: string, system?: string, options?: StructuredGenerationOptions): Promise<string>;
}

export function isLLMConfigured(): boolean {
  const provider = (process.env.LLM_PROVIDER ?? "deepseek").toLowerCase();
  if (provider === "openai") return Boolean(process.env.OPENAI_API_KEY?.trim());
  return Boolean(process.env.DEEPSEEK_API_KEY?.trim());
}

export function getLLMProvider(): LLMProvider {
  const provider = (process.env.LLM_PROVIDER ?? "deepseek").toLowerCase();
  if (provider === "openai") return new OpenAICompatibleProvider("openai");
  return new OpenAICompatibleProvider("deepseek");
}

class OpenAICompatibleProvider implements LLMProvider {
  constructor(private kind: "openai" | "deepseek") {}

  private requestTimeoutMs(): number {
    const env = Number(process.env.LLM_REQUEST_TIMEOUT_MS ?? "");
    if (Number.isFinite(env) && env >= 10_000) return Math.floor(env);
    return 180_000;
  }

  private envFlag(name: string, fallback = false): boolean {
    const value = process.env[name];
    if (!value) return fallback;
    return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  }

  private config() {
    if (this.kind === "openai") {
      return {
        apiKey: process.env.OPENAI_API_KEY ?? "",
        baseUrl: "https://api.openai.com/v1",
        model: process.env.OPENAI_MODEL || process.env.LLM_MODEL || "gpt-4o-mini",
      };
    }
    return {
      apiKey: process.env.DEEPSEEK_API_KEY ?? "",
      baseUrl: "https://api.deepseek.com/v1",
      model: process.env.DEEPSEEK_MODEL || process.env.LLM_MODEL || "deepseek-chat",
    };
  }

  private defaultMaxTokens(model: string, jsonMode = false): number {
    const capabilities = resolveModelCapabilities({ provider: this.kind, model });
    const envValue = Number(process.env.LLM_DEFAULT_MAX_TOKENS ?? "");
    if (Number.isFinite(envValue) && envValue > 0) {
      return Math.min(Math.floor(envValue), capabilities.maxOutputTokens);
    }
    return Math.min(capabilities.maxOutputTokens, jsonMode ? 8192 : capabilities.maxOutputTokens);
  }

  private logTrace(
    trace: LLMTrace | undefined,
    meta: {
      model: string;
      maxTokens: number;
      inputEstimate: number;
      reasoningEnabled?: boolean;
      finishReason?: string;
      usage?: { promptTokens?: number; completionTokens?: number; totalTokens?: number; reasoningTokens?: number };
    },
  ) {
    const stage = trace?.stage ?? "unknown";
    const callId = trace?.callId ?? "n/a";
    const chunkId = trace?.chunkId ?? "-";
    const attempt = trace?.attempt ?? 1;
    const runId = trace?.runId ?? "-";
    console.info(
      `[LLM] run=${runId} stage=${stage} call=${callId} chunk=${chunkId} attempt=${attempt} provider=${this.kind} model=${meta.model} maxOut=${meta.maxTokens} inputEst=${meta.inputEstimate}` +
        (meta.reasoningEnabled === undefined ? "" : ` thinking=${meta.reasoningEnabled ? "on" : "off"}`) +
        (meta.finishReason ? ` finish=${meta.finishReason}` : "") +
        (meta.usage?.promptTokens ? ` promptTok=${meta.usage.promptTokens}` : "") +
        (meta.usage?.completionTokens ? ` completionTok=${meta.usage.completionTokens}` : "") +
        (meta.usage?.reasoningTokens ? ` reasoningTok=${meta.usage.reasoningTokens}` : "") +
        (meta.usage?.totalTokens ? ` totalTok=${meta.usage.totalTokens}` : ""),
    );
  }

  private extractMessageContent(raw: unknown): string {
    if (typeof raw === "string") return raw.trim();
    if (!Array.isArray(raw)) return "";

    const parts: string[] = [];
    for (const part of raw) {
      if (typeof part === "string") {
        parts.push(part);
        continue;
      }
      if (!part || typeof part !== "object") continue;
      const text =
        ("text" in part && typeof part.text === "string" && part.text) ||
        ("content" in part && typeof part.content === "string" && part.content) ||
        "";
      if (text) parts.push(text);
    }
    return parts.join("").trim();
  }

  private async chatCompletion(
    messages: Array<{ role: string; content: string }>,
    options?: { jsonMode?: boolean; maxTokens?: number; allowReasoning?: boolean; trace?: LLMTrace },
  ): Promise<LLMCompletion> {
    const { apiKey, baseUrl, model } = this.config();
    if (!apiKey) throw new Error("LLM API key is not configured.");

    const deepThinkingEnabled =
      this.kind === "deepseek" &&
      this.envFlag("DEEPSEEK_DEEP_THINKING", model.toLowerCase().includes("deepseek-v4-pro"));
    const useReasoning = deepThinkingEnabled && options?.allowReasoning !== false;
    const deepThinkingEffort = process.env.DEEPSEEK_REASONING_EFFORT?.trim() || "high";

    const maxTokens = options?.maxTokens ?? this.defaultMaxTokens(model, options?.jsonMode ?? false);
    const body: Record<string, unknown> = {
      model,
      messages,
      temperature: 0.2,
      max_tokens: maxTokens,
    };
    const inputEstimate = estimateInputTokensFromChars(
      messages.reduce((sum, m) => sum + m.content.length, 0),
    );
    this.logTrace(options?.trace, { model, maxTokens, inputEstimate, reasoningEnabled: useReasoning });

    if (useReasoning) {
      body.reasoning_effort = deepThinkingEffort;
    } else if (this.kind === "deepseek" && options?.allowReasoning === false) {
      // V4 enables thinking by default. Omitting reasoning_effort is therefore
      // not enough to disable it, so make the non-thinking request explicit.
      body.thinking = { type: "disabled" };
      body.reasoning_effort = "none";
    }

    if (options?.jsonMode) {
      body.response_format = { type: "json_object" };
    }

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeoutMs());
    const res = await fetch(`${baseUrl}/chat/completions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
      signal: controller.signal,
    })
      .catch((error) => {
        const message = error instanceof Error ? error.message : String(error);
        if (message.includes("aborted") || message.includes("AbortError")) {
          throw new Error(`LLM request timed out after ${this.requestTimeoutMs()}ms.`);
        }
        throw error;
      })
      .finally(() => clearTimeout(timeout));

    if (!res.ok) {
      const errBody = await res.text();
      throw new Error(`LLM request failed (${res.status}): ${errBody}`);
    }

    const json = (await res.json()) as {
      choices?: Array<{
        finish_reason?: string;
        finishReason?: string;
        message?: { content?: unknown };
      }>;
      model?: string;
      usage?: {
        prompt_tokens?: number;
        completion_tokens?: number;
        total_tokens?: number;
        completion_tokens_details?: { reasoning_tokens?: number };
      };
    };
    const choice = json.choices?.[0];
    const content = this.extractMessageContent(choice?.message?.content);
    const finishReason = choice?.finish_reason ?? choice?.finishReason ?? "stop";
    const usage = {
      promptTokens: json.usage?.prompt_tokens,
      completionTokens: json.usage?.completion_tokens,
      totalTokens: json.usage?.total_tokens,
      reasoningTokens: json.usage?.completion_tokens_details?.reasoning_tokens,
    };
    this.logTrace(options?.trace, {
      model: json.model ?? model,
      maxTokens,
      inputEstimate,
      reasoningEnabled: useReasoning,
      finishReason,
      usage,
    });
    if (!content && useReasoning) {
      // Some DeepSeek reasoning responses can return an empty visible answer.
      // Retry once without reasoning mode to obtain the actual output content.
      return this.chatCompletion(messages, { ...options, allowReasoning: false });
    }
    if (!content) {
      if (isOutputTruncated(finishReason)) {
        throw new Error("LLM output stopped because of the output-token limit.");
      }
      throw new Error(`LLM returned empty content (finish_reason: ${finishReason}).`);
    }
    return {
      content,
      finishReason,
      model: json.model ?? model,
      usage,
    };
  }

  async complete(args: {
    prompt: string;
    system?: string;
    maxTokens?: number;
    jsonMode?: boolean;
    allowReasoning?: boolean;
    trace?: LLMTrace;
  }): Promise<LLMCompletion> {
    return this.chatCompletion(
      [
        ...(args.system ? [{ role: "system", content: args.system }] : []),
        { role: "user", content: args.prompt },
      ],
      {
        jsonMode: args.jsonMode ?? false,
        maxTokens: args.maxTokens,
        allowReasoning: args.allowReasoning,
        trace: args.trace,
      },
    );
  }

  async generateText(prompt: string, system?: string, options?: StructuredGenerationOptions): Promise<string> {
    const result = await this.complete({
      prompt,
      system,
      maxTokens: options?.maxTokens,
      jsonMode: options?.jsonMode ?? false,
      allowReasoning: options?.allowReasoning,
      trace: options?.trace,
    });
    if (options?.rejectTruncation && isOutputTruncated(result.finishReason)) {
      throw new Error("LLM output stopped because of the output-token limit.");
    }
    return result.content;
  }

  async generateStructured<T>(
    prompt: string,
    schema: ZodType<T>,
    system?: string,
    options?: StructuredGenerationOptions,
  ): Promise<T> {
    const maxTokens = options?.maxTokens ?? 8192;
    const jsonInstruction =
      "Return one valid JSON object only. No markdown fences. No prose before or after JSON.";

    const messages = [
      ...(system ? [{ role: "system", content: `${system}\n\n${jsonInstruction}` }] : []),
      { role: "user", content: prompt },
    ];

    let completion = await this.chatCompletion(messages, {
      jsonMode: true,
      maxTokens,
      allowReasoning: options?.allowReasoning,
      trace: options?.trace,
    });

    for (let attempt = 0; attempt < 3; attempt++) {
      const parsed = parseJsonSafe(completion.content);
      try {
        return schema.parse(parsed);
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : String(error);
        if (
          isOutputTruncated(completion.finishReason) &&
          options?.rejectTruncation !== false &&
          attempt === 2
        ) {
          throw new Error("LLM output stopped because of the output-token limit.");
        }
        if (attempt === 2) break;

        completion = await this.chatCompletion(
          [
            ...(system ? [{ role: "system", content: `${system}\n\n${jsonInstruction}` }] : []),
            {
              role: "user",
              content: `Return ONLY valid JSON matching the schema. Previous output was invalid (${errMsg}).\n\nRequired task:\n${prompt}`,
            },
          ],
            {
              jsonMode: true,
              maxTokens,
              allowReasoning: options?.allowReasoning,
              trace: options?.trace,
            },
        );
        continue;
      }

      completion = await this.chatCompletion(
        [
          ...(system ? [{ role: "system", content: `${system}\n\n${jsonInstruction}` }] : []),
          { role: "user", content: prompt },
        ],
        {
          jsonMode: true,
          maxTokens,
          allowReasoning: options?.allowReasoning,
          trace: options?.trace,
        },
      );
    }

    const fallback = parseJsonSafe(completion.content);
    try {
      return schema.parse(fallback);
    } catch (finalError) {
      if (isOutputTruncated(completion.finishReason) && options?.rejectTruncation !== false) {
        throw new Error("LLM output stopped because of the output-token limit.");
      }
      try {
        const { parseNarrativePlansLenient } = await import("@/lib/pipeline/normalize-llm");
        return schema.parse(parseNarrativePlansLenient(fallback));
      } catch {
        const msg = finalError instanceof Error ? finalError.message : String(finalError);
        const preview = extractJson(completion.content).slice(0, 200);
        throw new Error(
          `LLM structured response invalid after repair: ${msg}. Response preview: ${preview || "(empty)"}`,
        );
      }
    }
  }
}
