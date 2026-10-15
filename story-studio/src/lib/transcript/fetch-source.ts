import { prisma } from "@/lib/db";
import { commitSourceTranscript } from "@/lib/transcript/commit";
import { getTranscriptProvider } from "@/lib/transcript/provider";
import {
  captionKindLabel,
  languageLabel,
  transcriptErrorMessage,
  type AvailableLanguage,
  type TranscriptErrorCode,
  type TranscriptLanguage,
} from "@/lib/transcript/types";
import { parseYouTubeVideoUrl } from "@/lib/youtube/normalize";

export type FetchSourceResult =
  | {
      ok: true;
      transcriptOrigin: "public_caption";
      language: string;
      captionKind: string | null;
      fromCache: boolean;
      charCount: number;
      message: string;
    }
  | {
      ok: false;
      code: TranscriptErrorCode;
      message: string;
      availableLanguages?: AvailableLanguage[];
    };

function successMessage(language: string, captionKind: string | null, fromCache: boolean): string {
  const kind = captionKindLabel(captionKind);
  const name = languageLabel(language);
  const how = fromCache ? "Reused saved" : "Fetched";
  return kind ? `${how} ${name} ${kind}.` : `${how} ${name} captions.`;
}

export async function fetchPublicCaptionForSource(input: {
  projectId: string;
  sourceId: string;
  language: TranscriptLanguage;
  replace?: boolean;
  refresh?: boolean;
  url?: string;
}): Promise<FetchSourceResult> {
  const source = await prisma.source.findFirst({
    where: { id: input.sourceId, projectId: input.projectId },
  });
  if (!source) return { ok: false, code: "not_found", message: transcriptErrorMessage("not_found") };

  if (input.url !== undefined) {
    const trimmed = input.url.trim();
    if (!trimmed) {
      await prisma.source.update({
        where: { id: source.id },
        data: { url: null, videoId: null },
      });
    } else {
      const parsed = parseYouTubeVideoUrl(trimmed);
      if (!parsed) return { ok: false, code: "invalid_url", message: transcriptErrorMessage("invalid_url") };
      await prisma.source.update({
        where: { id: source.id },
        data: { url: parsed.canonicalUrl, videoId: parsed.videoId, kind: "youtube" },
      });
    }
  }

  const current = await prisma.source.findFirst({
    where: { id: source.id, projectId: input.projectId },
  });
  if (!current?.videoId) return { ok: false, code: "invalid_url", message: transcriptErrorMessage("invalid_url") };

  const samePublicCaption =
    current.transcriptOrigin === "public_caption" &&
    current.language === input.language &&
    Boolean(current.rawTranscript?.trim());

  if (!input.refresh && samePublicCaption) {
    return {
      ok: true,
      transcriptOrigin: "public_caption",
      language: current.language ?? input.language,
      captionKind: current.captionKind,
      fromCache: true,
      charCount: current.rawTranscript?.length ?? 0,
      message: successMessage(current.language ?? input.language, current.captionKind, true),
    };
  }

  if (current.rawTranscript?.trim() && !input.replace) {
    return { ok: false, code: "replace_required", message: transcriptErrorMessage("replace_required") };
  }

  const expectedRevision = current.transcriptRevision;
  const fetched = await getTranscriptProvider().fetchTranscript({
    videoId: current.videoId,
    language: input.language,
    refresh: input.refresh,
  });

  if (!fetched.ok) {
    return {
      ok: false,
      code: fetched.code,
      message: fetched.message,
      availableLanguages: fetched.availableLanguages,
    };
  }

  const saved = await commitSourceTranscript({
    projectId: input.projectId,
    sourceId: current.id,
    text: fetched.text,
    origin: "public_caption",
    language: input.language,
    captionKind: fetched.captionKind,
    segments: fetched.segments,
    expectedRevision,
  });

  if (!saved.ok) {
    return { ok: false, code: saved.code, message: saved.message };
  }

  return {
    ok: true,
    transcriptOrigin: "public_caption",
    language: input.language,
    captionKind: fetched.captionKind,
    fromCache: fetched.fromCache,
    charCount: saved.normalized.length,
    message: successMessage(input.language, fetched.captionKind, fetched.fromCache),
  };
}

export async function fetchMissingPublicCaptions(input: {
  projectId: string;
  language: TranscriptLanguage;
}): Promise<
  | { ok: false; code: "not_found"; message: string }
  | { ok: true; stopped: boolean; results: Array<{ sourceId: string; title: string } & FetchSourceResult> }
> {
  const project = await prisma.project.findUnique({
    where: { id: input.projectId },
    include: { sources: { orderBy: { createdAt: "asc" } } },
  });
  if (!project) return { ok: false, code: "not_found", message: transcriptErrorMessage("not_found") };

  const results: Array<{ sourceId: string; title: string } & FetchSourceResult> = [];
  let stopped = false;

  for (const source of project.sources) {
    if (source.rawTranscript?.trim()) continue;
    const language = source.language === "en" || source.language === "hi" ? source.language : input.language;
    const result = await fetchPublicCaptionForSource({
      projectId: input.projectId,
      sourceId: source.id,
      language,
      replace: false,
      refresh: false,
    });
    results.push({ sourceId: source.id, title: source.title, ...result });
    if (!result.ok && (result.code === "blocked" || result.code === "rate_limited" || result.code === "provider_unavailable" || result.code === "provider_config")) {
      stopped = true;
      break;
    }
  }

  return { ok: true, stopped, results };
}

export function shouldReusePreparedFacts(input: {
  factCount: number;
  sources: Array<{ rawTranscript?: string | null; claimCount?: number }>;
}): boolean {
  if (input.factCount <= 0) return false;
  const stale = input.sources.some((source) => Boolean(source.rawTranscript?.trim()) && source.claimCount === 0);
  return !stale;
}
