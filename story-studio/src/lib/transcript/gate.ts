import {
  isRetryableTranscriptError,
  transcriptErrorMessage,
  type TranscriptFailure,
} from "@/lib/transcript/types";

export type Clock = {
  now: () => number;
  sleep: (ms: number) => Promise<void>;
  random: () => number;
};

const defaultClock: Clock = {
  now: () => Date.now(),
  sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
  random: Math.random,
};

let clock: Clock = defaultClock;
let tail: Promise<void> = Promise.resolve();
let lastNetworkAt: number | null = null;
let blockedUntil = 0;
const inflight = new Map<string, Promise<TranscriptFailure | { ok: true }>>();

export function transcriptMinIntervalMs(): number {
  const value = Number(process.env.YOUTUBE_TRANSCRIPT_MIN_INTERVAL_MS ?? "8000");
  if (!Number.isFinite(value) || value < 0) return 8000;
  return value;
}

export function transcriptMaxRetries(): number {
  const value = Number(process.env.YOUTUBE_TRANSCRIPT_MAX_RETRIES ?? "2");
  if (!Number.isFinite(value) || value < 0) return 2;
  return Math.min(3, Math.floor(value));
}

export function transcriptBlockCooldownMs(): number {
  const value = Number(process.env.YOUTUBE_TRANSCRIPT_BLOCK_COOLDOWN_MS ?? "900000");
  if (!Number.isFinite(value) || value < 0) return 900000;
  return value;
}

export function backoffWithJitter(attempt: number, random: () => number = Math.random): number {
  const base = Math.min(8000, 500 * 2 ** attempt);
  return base + Math.floor(random() * 250);
}

export function setTranscriptClockForTests(next: Clock | null): void {
  clock = next ?? defaultClock;
}

export function resetTranscriptGateForTests(): void {
  tail = Promise.resolve();
  lastNetworkAt = null;
  blockedUntil = 0;
  inflight.clear();
  clock = defaultClock;
}

export function transcriptCooldownUntil(): number {
  return blockedUntil;
}

function blockedFailure(): TranscriptFailure {
  return {
    ok: false,
    code: "blocked",
    message: transcriptErrorMessage("blocked"),
  };
}

function withMessage(result: TranscriptFailure): TranscriptFailure {
  return {
    ...result,
    message: result.message || transcriptErrorMessage(result.code, result.availableLanguages),
  };
}

async function executeWithPolicy<T extends { ok: true } | TranscriptFailure>(
  run: () => Promise<T>,
): Promise<T | TranscriptFailure> {
  const limit = transcriptMaxRetries();
  let attempt = 0;

  while (true) {
    if (clock.now() < blockedUntil) return blockedFailure();

    let result: T | TranscriptFailure;
    try {
      result = await run();
    } catch (error) {
      const timedOut =
        error instanceof Error &&
        (error.name === "AbortError" || error.name === "TimeoutError" || /timeout/i.test(error.message));
      result = {
        ok: false,
        code: timedOut ? "timeout" : "temporary",
        message: transcriptErrorMessage(timedOut ? "timeout" : "temporary"),
      };
    }

    if (result.ok) return result;

    if (result.code === "blocked") {
      blockedUntil = clock.now() + transcriptBlockCooldownMs();
      return withMessage({ ...result, code: "blocked", message: transcriptErrorMessage("blocked") });
    }

    if (!isRetryableTranscriptError(result.code) || attempt >= limit) {
      return withMessage(result);
    }

    const retryAfter = result.retryAfterMs;
    if (result.code === "rate_limited" && retryAfter !== undefined && retryAfter > 15_000) {
      return withMessage(result);
    }

    const wait =
      result.code === "rate_limited" && retryAfter !== undefined
        ? retryAfter
        : backoffWithJitter(attempt, clock.random);
    if (wait > 15_000) return withMessage(result);

    attempt += 1;
    await clock.sleep(wait);
  }
}

function enqueue<T>(task: () => Promise<T>): Promise<T> {
  const run = tail.then(async () => {
    const elapsed = lastNetworkAt === null ? null : clock.now() - lastNetworkAt;
    const wait = elapsed === null ? 0 : transcriptMinIntervalMs() - elapsed;
    if (wait > 0) await clock.sleep(wait);
    lastNetworkAt = clock.now();
    return task();
  });
  tail = run.then(
    () => undefined,
    () => undefined,
  );
  return run;
}

export async function runTranscriptFetch<T extends { ok: true } | TranscriptFailure>(
  key: string,
  run: () => Promise<T>,
): Promise<T | TranscriptFailure> {
  if (clock.now() < blockedUntil) return blockedFailure();

  const existing = inflight.get(key);
  if (existing) return existing as Promise<T | TranscriptFailure>;

  const promise = enqueue(() => executeWithPolicy(run)).finally(() => {
    if (inflight.get(key) === promise) inflight.delete(key);
  });
  inflight.set(key, promise as Promise<TranscriptFailure | { ok: true }>);
  return promise;
}
