import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { hashTranscript, normalizeTranscript } from "@/lib/transcript/normalize";
import { persistTranscriptSegments } from "@/lib/pipeline/segments";
import { fetchOfficialYouTubeCaptions } from "@/lib/youtube/official-captions";
import { isYouTubeOAuthConfigured } from "@/lib/youtube/oauth";

export async function POST(
  _: Request,
  { params }: { params: Promise<{ projectId: string; sourceId: string }> },
) {
  const { sourceId } = await params;

  if (!isYouTubeOAuthConfigured()) {
    return NextResponse.json(
      { error: "Official YouTube captions require OAuth configuration." },
      { status: 503 },
    );
  }

  const source = await prisma.source.findUniqueOrThrow({ where: { id: sourceId } });

  if (source.kind !== "youtube" || !source.videoId) {
    return NextResponse.json(
      { error: "Official captions can only be fetched for YouTube reference sources with a valid video ID." },
      { status: 400 },
    );
  }

  try {
    const result = await fetchOfficialYouTubeCaptions(source.videoId);
    const normalized = normalizeTranscript(result.text);

    await prisma.source.update({
      where: { id: sourceId },
      data: {
        rawTranscript: normalized,
        normalizedHash: hashTranscript(normalized),
        transcriptStatus: "transcript_ready",
        transcriptOrigin: "official_oauth",
      },
    });

    await persistTranscriptSegments(sourceId, normalized, result.segments);

    return NextResponse.json({
      ok: true,
      transcriptOrigin: "official_oauth",
      charCount: normalized.length,
      message: "Official captions fetched for owned/authorized video only.",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to fetch official captions";
    return NextResponse.json({ error: message }, { status: 403 });
  }
}
