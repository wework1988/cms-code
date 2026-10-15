import { normalizeTranscript } from "@/lib/transcript/normalize";
import { runPythonTranscript } from "@/lib/transcript/python-runner";
import { readCaptionCache, writeCaptionCache, type CachedCaption } from "@/lib/transcript/cache";
import { runTranscriptFetch } from "@/lib/transcript/gate";
import {
  transcriptErrorMessage,
  type TranscriptFailure,
  type TranscriptLanguage,
  type TranscriptSuccess,
} from "@/lib/transcript/types";

export type { TranscriptResult } from "@/lib/transcript/types";

export interface TranscriptFetchInput {
  videoId: string;
  language: TranscriptLanguage;
  refresh?: boolean;
}

export interface TranscriptProvider {
  fetchTranscript(input: TranscriptFetchInput): Promise<TranscriptSuccess | TranscriptFailure>;
}

type NetworkResult =
  | {
      ok: true;
      language: string;
      languageCode: string;
      captionKind: "manual" | "generated";
      segments: Array<{ text: string; start: number; duration: number }>;
    }
  | TranscriptFailure;

function successFromCache(cached: CachedCaption): TranscriptSuccess {
  return {
    ok: true,
    text: cached.text,
    language: cached.language,
    languageCode: cached.languageCode,
    captionKind: cached.captionKind,
    segments: cached.segments.map((segment) => ({
      startSec: segment.start,
      duration: segment.duration,
      text: segment.text,
    })),
    fromCache: true,
  };
}

function successFromNetwork(
  videoId: string,
  language: string,
  result: Extract<NetworkResult, { ok: true }>,
): TranscriptSuccess {
  const text = normalizeTranscript(result.segments.map((segment) => segment.text).join("\n"));
  return {
    ok: true,
    text,
    language: result.language || language,
    languageCode: result.languageCode || language,
    captionKind: result.captionKind,
    segments: result.segments.map((segment) => ({
      startSec: segment.start,
      duration: segment.duration,
      text: segment.text,
    })),
    fromCache: false,
  };
}

export function createTranscriptProvider(deps: {
  network: (input: { videoId: string; language: TranscriptLanguage }) => Promise<NetworkResult>;
  readCache?: (videoId: string, language: string) => Promise<CachedCaption | null>;
  writeCache?: (entry: CachedCaption) => Promise<void>;
}): TranscriptProvider {
  const readCache = deps.readCache ?? readCaptionCache;
  const writeCache = deps.writeCache ?? writeCaptionCache;

  return {
    async fetchTranscript({ videoId, language, refresh }) {
      if (!/^[a-zA-Z0-9_-]{11}$/.test(videoId)) {
        return { ok: false, code: "invalid_url", message: transcriptErrorMessage("invalid_url") };
      }

      if (!refresh) {
        const cached = await readCache(videoId, language);
        if (cached?.text.trim()) return successFromCache(cached);
      }

      const result = await runTranscriptFetch(`${videoId}|${language}`, () => deps.network({ videoId, language }));
      if (!result.ok) return result;

      const success = successFromNetwork(videoId, language, result);
      if (!success.text.trim()) {
        return { ok: false, code: "no_captions", message: transcriptErrorMessage("no_captions") };
      }

      await writeCache({
        videoId,
        language,
        languageCode: language,
        captionKind: success.captionKind,
        text: success.text,
        segments: success.segments.map((segment) => ({
          text: segment.text,
          start: segment.startSec,
          duration: segment.duration,
        })),
      });
      return success;
    },
  };
}

const defaultProvider = createTranscriptProvider({ network: runPythonTranscript });
let activeProvider: TranscriptProvider = defaultProvider;

/** Manual paste stays available even when this provider can fetch public captions. */
export function isManualTranscriptMode(): boolean {
  return true;
}

export function getTranscriptProvider(): TranscriptProvider {
  return activeProvider;
}

export function setTranscriptProviderForTests(provider: TranscriptProvider | null): void {
  activeProvider = provider ?? createTranscriptProvider({ network: runPythonTranscript });
}
