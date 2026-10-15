import { prisma } from "@/lib/db";
import type { CaptionKind, TranscriptSegment } from "@/lib/transcript/types";

export type CachedCaption = {
  videoId: string;
  language: string;
  languageCode: string;
  captionKind: CaptionKind;
  text: string;
  segments: TranscriptSegment[];
};

function cacheKey(videoId: string, language: string, captionKind: string): string {
  return `${videoId}|${language}|${captionKind}`;
}

export async function readCaptionCache(videoId: string, language: string): Promise<CachedCaption | null> {
  const rows = await prisma.publicCaptionCache.findMany({
    where: { videoId, language },
  });
  const row = rows.find((entry) => entry.captionKind === "manual") ?? rows.find((entry) => entry.captionKind === "generated");
  if (!row) return null;
  let segments: TranscriptSegment[] = [];
  try {
    const parsed = JSON.parse(row.segmentsJson) as TranscriptSegment[];
    if (Array.isArray(parsed)) segments = parsed;
  } catch {
    segments = [];
  }
  return {
    videoId: row.videoId,
    language: row.language,
    languageCode: row.language,
    captionKind: row.captionKind === "generated" ? "generated" : "manual",
    text: row.text,
    segments,
  };
}

export async function writeCaptionCache(entry: CachedCaption): Promise<void> {
  const key = cacheKey(entry.videoId, entry.language, entry.captionKind);
  const segmentsJson = JSON.stringify(entry.segments);
  await prisma.publicCaptionCache.upsert({
    where: { cacheKey: key },
    create: {
      cacheKey: key,
      videoId: entry.videoId,
      language: entry.language,
      captionKind: entry.captionKind,
      text: entry.text,
      segmentsJson,
    },
    update: {
      text: entry.text,
      segmentsJson,
      captionKind: entry.captionKind,
    },
  });
}
