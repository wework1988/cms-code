import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { commitSourceTranscript } from "@/lib/transcript/commit";
import { fetchOfficialYouTubeCaptions } from "@/lib/youtube/official-captions";
import { isYouTubeOAuthConfigured } from "@/lib/youtube/oauth";

const bodySchema = z.object({ replace: z.boolean().optional() }).partial();

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectId: string; sourceId: string }> },
) {
  const { projectId, sourceId } = await params;
  const body = bodySchema.parse(await request.json().catch(() => ({})));

  if (!isYouTubeOAuthConfigured()) {
    return NextResponse.json(
      { error: "Official YouTube captions require OAuth configuration. This does not download captions for arbitrary videos." },
      { status: 503 },
    );
  }

  const source = await prisma.source.findFirst({ where: { id: sourceId, projectId } });
  if (!source) return NextResponse.json({ error: "Source not found in this project." }, { status: 404 });

  if (!source.videoId) {
    return NextResponse.json(
      { error: "Official captions can only be fetched for a source with a valid YouTube video ID." },
      { status: 400 },
    );
  }

  if (source.rawTranscript?.trim() && !body.replace) {
    return NextResponse.json(
      { error: "This source already has a transcript. Confirm replacement before fetching official captions." },
      { status: 409 },
    );
  }

  try {
    const result = await fetchOfficialYouTubeCaptions(source.videoId);
    const saved = await commitSourceTranscript({
      projectId,
      sourceId,
      text: result.text,
      origin: "official_oauth",
      language: result.language ?? source.language,
      captionKind: null,
      segments: result.segments,
      expectedRevision: source.transcriptRevision,
    });
    if (!saved.ok) {
      return NextResponse.json({ error: saved.message, code: saved.code }, { status: saved.code === "stale" ? 409 : 404 });
    }

    return NextResponse.json({
      ok: true,
      transcriptOrigin: "official_oauth",
      charCount: saved.normalized.length,
      message: "Official captions fetched for a video on your connected channel. This does not fetch arbitrary videos.",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to fetch official captions";
    return NextResponse.json({ error: message }, { status: 403 });
  }
}
