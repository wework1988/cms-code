import { spawn } from "child_process";
import path from "path";
import { z } from "zod";
import {
  transcriptErrorMessage,
  type AvailableLanguage,
  type CaptionKind,
  type TranscriptErrorCode,
  type TranscriptFailure,
  type TranscriptSegment,
} from "@/lib/transcript/types";

const availableLanguageSchema = z.object({
  languageCode: z.string().min(1).max(32),
  language: z.string().min(1).max(80),
  captionKind: z.enum(["manual", "generated"]),
});

const helperSuccessSchema = z.object({
  ok: z.literal(true),
  language: z.string().min(1).max(80),
  languageCode: z.string().min(1).max(32),
  captionKind: z.enum(["manual", "generated"]),
  segments: z
    .array(
      z.object({
        text: z.string(),
        start: z.number().finite(),
        duration: z.number().finite(),
      }),
    )
    .max(20000),
});

const helperFailureSchema = z.object({
  ok: z.literal(false),
  code: z.string(),
  retryAfterMs: z.number().int().nonnegative().optional(),
  availableLanguages: z.array(availableLanguageSchema).optional(),
});

const KNOWN_CODES = new Set<TranscriptErrorCode>([
  "blocked",
  "rate_limited",
  "no_captions",
  "unavailable",
  "language_unavailable",
  "timeout",
  "temporary",
  "provider_unavailable",
  "provider_config",
  "invalid_url",
  "output_too_large",
]);

export type ProxyConfig =
  | { mode: "off" }
  | { mode: "webshare" }
  | { mode: "generic" }
  | { mode: "invalid" };

export function readProxyMode(): ProxyConfig {
  const mode = (process.env.YOUTUBE_TRANSCRIPT_PROXY ?? "off").trim().toLowerCase();
  if (mode === "" || mode === "off" || mode === "false" || mode === "0") return { mode: "off" };
  if (mode === "webshare") {
    const username = process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_USERNAME?.trim() ?? "";
    const password = process.env.YOUTUBE_TRANSCRIPT_WEBSHARE_PASSWORD?.trim() ?? "";
    if (!username || !password) return { mode: "invalid" };
    return { mode: "webshare" };
  }
  if (mode === "generic") {
    const httpUrl = process.env.YOUTUBE_TRANSCRIPT_HTTP_PROXY?.trim() ?? "";
    const httpsUrl = process.env.YOUTUBE_TRANSCRIPT_HTTPS_PROXY?.trim() ?? "";
    const allowed = (value: string) => value.startsWith("http://") || value.startsWith("https://");
    if ((!httpUrl && !httpsUrl) || (httpUrl && !allowed(httpUrl)) || (httpsUrl && !allowed(httpsUrl))) {
      return { mode: "invalid" };
    }
    return { mode: "generic" };
  }
  return { mode: "invalid" };
}

function failure(code: TranscriptErrorCode, extra?: Partial<TranscriptFailure>): TranscriptFailure {
  return {
    ok: false,
    code,
    message: transcriptErrorMessage(code, extra?.availableLanguages),
    ...extra,
  };
}

function pythonBinary(): string | null {
  const bin = process.env.YOUTUBE_TRANSCRIPT_PYTHON?.trim() || "python3";
  if (!/^[A-Za-z0-9_./+-]+$/.test(bin)) return null;
  return bin;
}

function helperPath(): string {
  return path.join(process.cwd(), "scripts", "fetch_public_captions.py");
}

function timeoutMs(): number {
  const value = Number(process.env.YOUTUBE_TRANSCRIPT_TIMEOUT_MS ?? "25000");
  if (!Number.isFinite(value) || value < 1000) return 25000;
  return Math.min(value, 120000);
}

function maxOutputBytes(): number {
  const value = Number(process.env.YOUTUBE_TRANSCRIPT_MAX_OUTPUT_BYTES ?? "1500000");
  if (!Number.isFinite(value) || value < 1000) return 1_500_000;
  return Math.min(value, 5_000_000);
}

export async function runPythonTranscript(input: {
  videoId: string;
  language: "hi" | "en";
}): Promise<
  | {
      ok: true;
      language: string;
      languageCode: string;
      captionKind: CaptionKind;
      segments: TranscriptSegment[];
    }
  | TranscriptFailure
> {
  if (!/^[a-zA-Z0-9_-]{11}$/.test(input.videoId)) return failure("invalid_url");
  if (readProxyMode().mode === "invalid") return failure("provider_config");

  const bin = pythonBinary();
  if (!bin) return failure("provider_config");

  const stdoutLimit = maxOutputBytes();

  return new Promise((resolve) => {
    let settled = false;
    const finish = (result: Awaited<ReturnType<typeof runPythonTranscript>>) => {
      if (settled) return;
      settled = true;
      resolve(result);
    };

    const signal = AbortSignal.timeout(timeoutMs());
    let child;
    try {
      child = spawn(bin, [helperPath()], {
        shell: false,
        stdio: ["pipe", "pipe", "pipe"],
        signal,
      });
    } catch {
      finish(failure("provider_unavailable"));
      return;
    }

    const stdout: Buffer[] = [];
    let stdoutBytes = 0;
    let stderr = "";

    child.stdout?.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length;
      if (stdoutBytes > stdoutLimit) {
        child.kill();
        finish(failure("output_too_large"));
        return;
      }
      stdout.push(chunk);
    });

    child.stderr?.on("data", (chunk: Buffer) => {
      if (stderr.length < 2000) stderr += chunk.toString("utf8");
    });

    child.on("error", (error: NodeJS.ErrnoException) => {
      if (error.code === "ENOENT") finish(failure("provider_unavailable"));
      else if (error.name === "AbortError" || error.name === "TimeoutError") finish(failure("timeout"));
      else finish(failure("provider_unavailable"));
    });

    child.on("close", () => {
      if (signal.aborted) {
        finish(failure("timeout"));
        return;
      }
      if (stderr.includes("ModuleNotFoundError") || stderr.includes("No module named")) {
        finish(failure("provider_unavailable"));
        return;
      }
      const raw = Buffer.concat(stdout).toString("utf8").trim();
      if (!raw) {
        finish(failure("provider_unavailable"));
        return;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(raw);
      } catch {
        finish(failure("temporary"));
        return;
      }
      const success = helperSuccessSchema.safeParse(parsed);
      if (success.success) {
        finish({
          ok: true,
          language: success.data.language,
          languageCode: success.data.languageCode,
          captionKind: success.data.captionKind,
          segments: success.data.segments,
        });
        return;
      }
      const failed = helperFailureSchema.safeParse(parsed);
      if (!failed.success) {
        finish(failure("temporary"));
        return;
      }
      const code = KNOWN_CODES.has(failed.data.code as TranscriptErrorCode)
        ? (failed.data.code as TranscriptErrorCode)
        : "temporary";
      const available = failed.data.availableLanguages as AvailableLanguage[] | undefined;
      finish(
        failure(code, {
          availableLanguages: available,
          retryAfterMs: failed.data.retryAfterMs,
        }),
      );
    });

    child.stdin?.write(JSON.stringify({ videoId: input.videoId, language: input.language }));
    child.stdin?.end();
  });
}
