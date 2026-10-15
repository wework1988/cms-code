export const TRANSCRIPT_LANGUAGES = ["hi", "en"] as const;

export type TranscriptLanguage = (typeof TRANSCRIPT_LANGUAGES)[number];

export type CaptionKind = "manual" | "generated";

export type AvailableLanguage = {
  languageCode: string;
  language: string;
  captionKind: CaptionKind;
};

export type TranscriptErrorCode =
  | "blocked"
  | "rate_limited"
  | "no_captions"
  | "unavailable"
  | "language_unavailable"
  | "timeout"
  | "temporary"
  | "provider_unavailable"
  | "provider_config"
  | "invalid_url"
  | "replace_required"
  | "stale"
  | "not_found"
  | "output_too_large";

export type TranscriptSegment = {
  text: string;
  start: number;
  duration: number;
};

/** Shape returned by the official OAuth caption fetcher. */
export interface TranscriptResult {
  text: string;
  language?: string;
  segments?: Array<{ startSec: number; duration: number; text: string }>;
}

export type TranscriptFailure = {
  ok: false;
  code: TranscriptErrorCode;
  message: string;
  retryAfterMs?: number;
  availableLanguages?: AvailableLanguage[];
};

export type TranscriptSuccess = {
  ok: true;
  text: string;
  language: string;
  languageCode: string;
  captionKind: CaptionKind;
  segments: Array<{ startSec: number; duration: number; text: string }>;
  fromCache: boolean;
};

export function isRetryableTranscriptError(code: TranscriptErrorCode): boolean {
  return code === "rate_limited" || code === "timeout" || code === "temporary";
}

export function transcriptErrorMessage(
  code: TranscriptErrorCode,
  availableLanguages?: AvailableLanguage[],
): string {
  switch (code) {
    case "blocked":
      return "YouTube blocked transcript requests from this network. Automatic retries are paused. Paste the transcript manually. The URL and any saved transcript were left unchanged.";
    case "rate_limited":
      return "YouTube rate-limited transcript requests. Wait before trying again, or paste the transcript manually. The saved transcript was left unchanged.";
    case "no_captions":
      return "No captions are available for this video. Paste the transcript manually.";
    case "unavailable":
      return "This video is unavailable. Check the URL or paste the transcript manually.";
    case "language_unavailable": {
      const listed = (availableLanguages ?? [])
        .map((language) => `${language.language} (${language.captionKind === "manual" ? "human" : "automatic"})`)
        .join(", ");
      return listed
        ? `The requested language is not available. Available captions: ${listed}. Choose one of those languages or paste the transcript manually.`
        : "The requested language is not available. Paste the transcript manually.";
    }
    case "timeout":
      return "The transcript request timed out. Paste the transcript manually or try again later.";
    case "temporary":
      return "The transcript request failed temporarily. Paste the transcript manually or try again later.";
    case "provider_unavailable":
      return "Transcript fetching is unavailable because Python or youtube-transcript-api is not installed. Paste the transcript manually. Setup: python3 -m pip install -r scripts/requirements-transcript.txt";
    case "provider_config":
      return "Transcript proxy settings are incomplete, so no request was sent. Paste the transcript manually or correct the server configuration.";
    case "invalid_url":
      return "Enter a valid YouTube video URL. Other links are not fetched.";
    case "replace_required":
      return "This source already has a transcript. Fetching again replaces it only when you confirm.";
    case "stale":
      return "The transcript was edited while the fetch was running, so the fetched text was not saved.";
    case "not_found":
      return "Source not found in this project.";
    case "output_too_large":
      return "The caption payload was larger than the allowed size and was not saved. Paste a shorter transcript manually.";
    default:
      return "The transcript could not be fetched. Paste it manually.";
  }
}

export function statusForTranscriptError(code: TranscriptErrorCode): number {
  switch (code) {
    case "not_found":
      return 404;
    case "replace_required":
    case "stale":
      return 409;
    case "invalid_url":
    case "language_unavailable":
    case "no_captions":
    case "unavailable":
    case "output_too_large":
      return 422;
    case "rate_limited":
      return 429;
    case "blocked":
    case "provider_unavailable":
    case "provider_config":
      return 503;
    case "timeout":
    case "temporary":
      return 504;
    default:
      return 500;
  }
}

export function captionKindLabel(kind?: string | null): string | null {
  if (kind === "manual") return "human captions";
  if (kind === "generated") return "automatic captions";
  return null;
}

export function languageLabel(code?: string | null, fallback?: string | null): string {
  const value = (code ?? "").toLowerCase();
  if (value.startsWith("hi") || fallback?.toLowerCase() === "hindi") return "Hindi";
  if (value.startsWith("en") || fallback?.toLowerCase() === "english") return "English";
  return fallback?.trim() || code || "Unknown language";
}
