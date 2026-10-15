import { execFileSync } from "child_process";
import path from "path";
import { beforeEach, describe, expect, it } from "vitest";
import { resetTranscriptGateForTests, runTranscriptFetch, setTranscriptClockForTests } from "@/lib/transcript/gate";
import { readProxyMode } from "@/lib/transcript/python-runner";
import { createTranscriptProvider, isManualTranscriptMode, setTranscriptProviderForTests } from "@/lib/transcript/provider";
import { transcriptErrorMessage } from "@/lib/transcript/types";

const script = path.join(process.cwd(), "scripts", "fetch_public_captions.py");

describe("transcript provider", () => {
  beforeEach(() => {
    resetTranscriptGateForTests();
    setTranscriptProviderForTests(null);
    process.env.YOUTUBE_TRANSCRIPT_MIN_INTERVAL_MS = "0";
    process.env.YOUTUBE_TRANSCRIPT_PROXY = "off";
  });

  it("keeps manual paste available without fetching on import", () => {
    expect(isManualTranscriptMode()).toBe(true);
  });

  it("reuses a cached caption until refresh is requested", async () => {
    const store = new Map<string, { text: string; captionKind: "manual" | "generated" }>();
    let calls = 0;
    const provider = createTranscriptProvider({
      network: async () => {
        calls += 1;
        return {
          ok: true,
          language: "Hindi",
          languageCode: "hi",
          captionKind: "manual",
          segments: [{ text: "Fetched caption", start: 0, duration: 1 }],
        };
      },
      readCache: async (videoId, language) => {
        const hit = store.get(`${videoId}|${language}`);
        if (!hit) return null;
        return {
          videoId,
          language,
          languageCode: language,
          captionKind: hit.captionKind,
          text: hit.text,
          segments: [{ text: hit.text, start: 0, duration: 1 }],
        };
      },
      writeCache: async (entry) => {
        store.set(`${entry.videoId}|${entry.language}`, { text: entry.text, captionKind: entry.captionKind });
      },
    });

    const first = await provider.fetchTranscript({ videoId: "dQw4w9WgXcQ", language: "hi" });
    const second = await provider.fetchTranscript({ videoId: "dQw4w9WgXcQ", language: "hi" });
    const refreshed = await provider.fetchTranscript({ videoId: "dQw4w9WgXcQ", language: "hi", refresh: true });

    expect(first).toMatchObject({ ok: true, fromCache: false, text: "Fetched caption" });
    expect(second).toMatchObject({ ok: true, fromCache: true });
    expect(refreshed).toMatchObject({ ok: true, fromCache: false });
    expect(calls).toBe(2);
  });

  it("does not substitute another language", async () => {
    const languages: string[] = [];
    const provider = createTranscriptProvider({
      network: async ({ language }) => {
        languages.push(language);
        return {
          ok: false,
          code: "language_unavailable",
          message: transcriptErrorMessage("language_unavailable", [
            { languageCode: "en", language: "English", captionKind: "generated" },
          ]),
          availableLanguages: [{ languageCode: "en", language: "English", captionKind: "generated" }],
        };
      },
      readCache: async () => null,
      writeCache: async () => undefined,
    });

    const result = await provider.fetchTranscript({ videoId: "dQw4w9WgXcQ", language: "hi" });
    expect(languages).toEqual(["hi"]);
    expect(result).toMatchObject({
      ok: false,
      code: "language_unavailable",
      availableLanguages: [{ languageCode: "en" }],
    });
  });
});

describe("caption selection helper", () => {
  it("prefers human captions in the requested language", () => {
    const stdout = execFileSync("python3", [script, "--self-test"], { encoding: "utf8" });
    expect(JSON.parse(stdout).cases).toEqual({
      humanPreferred: "human",
      humanKind: "manual",
      generatedFallback: "auto-en",
      generatedKind: "generated",
      otherLanguage: null,
      otherKind: null,
    });
  });
});

describe("transcript fetch gate", () => {
  beforeEach(() => {
    resetTranscriptGateForTests();
    process.env.YOUTUBE_TRANSCRIPT_MIN_INTERVAL_MS = "0";
    process.env.YOUTUBE_TRANSCRIPT_MAX_RETRIES = "2";
    process.env.YOUTUBE_TRANSCRIPT_BLOCK_COOLDOWN_MS = "900000";
  });

  it("retries temporary failures a bounded number of times", async () => {
    const sleeps: number[] = [];
    let now = 0;
    setTranscriptClockForTests({
      now: () => now,
      sleep: async (ms) => {
        sleeps.push(ms);
        now += ms;
      },
      random: () => 0,
    });
    let calls = 0;
    const result = await runTranscriptFetch("video|hi", async () => {
      calls += 1;
      if (calls < 3) return { ok: false as const, code: "temporary" as const, message: "" };
      return { ok: true as const };
    });
    expect(result.ok).toBe(true);
    expect(calls).toBe(3);
    expect(sleeps).toHaveLength(2);
  });

  it("stops on an IP block and does not call the provider again during cooldown", async () => {
    let now = 0;
    setTranscriptClockForTests({
      now: () => now,
      sleep: async (ms) => {
        now += ms;
      },
      random: () => 0,
    });
    let calls = 0;
    const blocked = await runTranscriptFetch("video-a|hi", async () => {
      calls += 1;
      return { ok: false as const, code: "blocked" as const, message: "" };
    });
    const second = await runTranscriptFetch("video-b|en", async () => {
      calls += 1;
      return { ok: true as const };
    });
    expect(blocked).toMatchObject({ ok: false, code: "blocked" });
    expect(blocked.ok ? "" : blocked.message).toContain("Paste the transcript manually");
    expect(second).toMatchObject({ ok: false, code: "blocked" });
    expect(calls).toBe(1);
  });

  it("waits for the shared request interval between videos", async () => {
    process.env.YOUTUBE_TRANSCRIPT_MIN_INTERVAL_MS = "8000";
    let now = 0;
    const starts: number[] = [];
    setTranscriptClockForTests({
      now: () => now,
      sleep: async (ms) => {
        now += ms;
      },
      random: () => 0,
    });
    await runTranscriptFetch("one|hi", async () => {
      starts.push(now);
      return { ok: true as const };
    });
    await runTranscriptFetch("two|hi", async () => {
      starts.push(now);
      return { ok: true as const };
    });
    expect(starts).toEqual([0, 8000]);
  });

  it("deduplicates simultaneous requests for the same video", async () => {
    let calls = 0;
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const run = () => {
      calls += 1;
      return gate.then(() => ({ ok: true as const }));
    };
    const first = runTranscriptFetch("same|hi", run);
    const second = runTranscriptFetch("same|hi", run);
    release();
    await Promise.all([first, second]);
    expect(calls).toBe(1);
  });

  it("does not retry a permanent caption failure", async () => {
    let calls = 0;
    const result = await runTranscriptFetch("none|hi", async () => {
      calls += 1;
      return { ok: false as const, code: "no_captions" as const, message: "" };
    });
    expect(result).toMatchObject({ ok: false, code: "no_captions" });
    expect(calls).toBe(1);
  });

  it("respects a long Retry-After by not retrying immediately", async () => {
    let calls = 0;
    const result = await runTranscriptFetch("rate|hi", async () => {
      calls += 1;
      return { ok: false as const, code: "rate_limited" as const, message: "", retryAfterMs: 60_000 };
    });
    expect(result).toMatchObject({ ok: false, code: "rate_limited" });
    expect(calls).toBe(1);
  });
});

describe("proxy configuration", () => {
  beforeEach(() => {
    process.env.YOUTUBE_TRANSCRIPT_PROXY = "off";
    delete process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME;
    delete process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD;
    delete process.env.YOUTUBE_TRANSCRIPT_HTTP_PROXY;
    delete process.env.YOUTUBE_TRANSCRIPT_HTTPS_PROXY;
  });

  it("stays off by default and does not echo credentials in a configuration error", () => {
    expect(readProxyMode()).toEqual({ mode: "off" });
    process.env.YOUTUBE_TRANSCRIPT_PROXY = "webshare";
    process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD = "super-secret-password";
    const mode = readProxyMode();
    expect(mode).toEqual({ mode: "invalid" });
    expect(JSON.stringify(mode)).not.toContain("super-secret-password");
    process.env.YOUTUBE_TRANSCRIPT_PROXY = "off";
    delete process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD;
  });
});
