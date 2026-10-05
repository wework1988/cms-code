import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { getLLMProvider } from "@/lib/llm/provider";

describe("LLM provider parsing", () => {
  const originalEnv = { ...process.env };
  const originalFetch = global.fetch;

  beforeEach(() => {
    process.env = {
      ...originalEnv,
      LLM_PROVIDER: "deepseek",
      DEEPSEEK_API_KEY: "test-key",
      DEEPSEEK_MODEL: "deepseek-v4-pro",
      DEEPSEEK_DEEP_THINKING: "true",
      DEEPSEEK_REASONING_EFFORT: "high",
    };
  });

  afterEach(() => {
    process.env = { ...originalEnv };
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it("accepts content returned as structured parts", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return {
        ok: true,
        json: async () => ({
          choices: [{ finish_reason: "stop", message: { content: [{ type: "text", text: "नमस्ते दुनिया" }] } }],
        }),
      } as Response;
    });
    global.fetch = fetchMock as typeof fetch;

    const provider = getLLMProvider();
    const result = await provider.complete({ prompt: "test prompt" });

    expect(result.content).toBe("नमस्ते दुनिया");
    expect(result.finishReason).toBe("stop");
  });

  it("retries without reasoning when first response has empty visible content", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ choices: [{ finish_reason: "stop", message: { content: "" } }] }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ choices: [{ finish_reason: "stop", message: { content: "पूरा उत्तर" } }] }),
      });
    global.fetch = fetchMock as typeof fetch;

    const provider = getLLMProvider();
    const result = await provider.complete({ prompt: "retry prompt" });

    expect(result.content).toBe("पूरा उत्तर");
    expect(fetchMock).toHaveBeenCalledTimes(2);

    const firstBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string) as Record<string, unknown>;
    const secondBody = JSON.parse((fetchMock.mock.calls[1]?.[1] as RequestInit).body as string) as Record<string, unknown>;

    expect(firstBody.reasoning_effort).toBe("high");
    expect(secondBody.thinking).toEqual({ type: "disabled" });
    expect(secondBody.reasoning_effort).toBe("none");
  });

  it("explicitly disables DeepSeek thinking when a long-form caller reserves tokens for output", async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return {
        ok: true,
        json: async () => ({ choices: [{ finish_reason: "stop", message: { content: "पूरा उत्तर" } }] }),
      } as Response;
    });
    global.fetch = fetchMock as typeof fetch;

    const provider = getLLMProvider();
    const result = await provider.complete({ prompt: "long-form prompt", allowReasoning: false });

    expect(result.content).toBe("पूरा उत्तर");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const body = JSON.parse((fetchMock.mock.calls[0]?.[1] as RequestInit).body as string) as Record<string, unknown>;
    expect(body.thinking).toEqual({ type: "disabled" });
    expect(body.reasoning_effort).toBe("none");
  });

  it("accepts valid structured JSON even when finish_reason is length", async () => {
    const fetchMock = vi.fn(async () => {
      return {
        ok: true,
        json: async () => ({
          choices: [{ finish_reason: "length", message: { content: '{"ok":true,"items":[1,2]}' } }],
        }),
      } as Response;
    });
    global.fetch = fetchMock as typeof fetch;

    const provider = getLLMProvider();
    const parsed = await provider.generateStructured(
      "structured prompt",
      z.object({ ok: z.boolean(), items: z.array(z.number()) }),
    );

    expect(parsed).toEqual({ ok: true, items: [1, 2] });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
