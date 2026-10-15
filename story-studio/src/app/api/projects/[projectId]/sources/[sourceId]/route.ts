import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { commitSourceTranscript } from "@/lib/transcript/commit";
import { normalizeTranscript } from "@/lib/transcript/normalize";
import { parseYouTubeVideoUrl } from "@/lib/youtube/normalize";

const updateSchema = z.object({
  title: z.string().optional(),
  rawTranscript: z.string().optional(),
  sourceLabel: z.string().optional(),
  language: z.string().optional(),
  url: z.string().optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string; sourceId: string }> },
) {
  const { projectId, sourceId } = await params;
  const body = updateSchema.parse(await request.json());
  const source = await prisma.source.findFirst({ where: { id: sourceId, projectId } });
  if (!source) return NextResponse.json({ error: "Source not found in this project." }, { status: 404 });

  if (body.url !== undefined) {
    const trimmed = body.url.trim();
    if (!trimmed) {
      await prisma.source.update({
        where: { id: source.id },
        data: { url: null, videoId: null },
      });
    } else {
      const parsed = parseYouTubeVideoUrl(trimmed);
      if (!parsed) {
        return NextResponse.json({ error: "Enter a valid YouTube video URL. Other links are not fetched." }, { status: 422 });
      }
      await prisma.source.update({
        where: { id: source.id },
        data: { url: parsed.canonicalUrl, videoId: parsed.videoId, kind: "youtube" },
      });
    }
  }

  const metadata: { title?: string; sourceLabel?: string; language?: string } = {};
  if (body.title !== undefined) metadata.title = body.title;
  if (body.sourceLabel !== undefined) metadata.sourceLabel = body.sourceLabel;
  if (body.language !== undefined && body.rawTranscript === undefined) metadata.language = body.language;
  if (Object.keys(metadata).length > 0) {
    await prisma.source.update({ where: { id: source.id }, data: metadata });
  }

  if (body.rawTranscript !== undefined) {
    const normalized = normalizeTranscript(body.rawTranscript);
    const saved = await commitSourceTranscript({
      projectId,
      sourceId,
      text: normalized,
      origin: normalized ? "manual" : null,
      language: body.language,
    });
    if (!saved.ok) return NextResponse.json({ error: saved.message }, { status: saved.code === "not_found" ? 404 : 409 });
  }

  const updated = await prisma.source.findFirst({ where: { id: source.id, projectId } });
  return NextResponse.json(updated);
}
