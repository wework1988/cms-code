import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { hashTranscript, normalizeTranscript } from "@/lib/transcript/normalize";
import { persistTranscriptSegments } from "@/lib/pipeline/segments";
import { z } from "zod";

const updateSchema = z.object({
  title: z.string().optional(),
  rawTranscript: z.string().optional(),
  sourceLabel: z.string().optional(),
  language: z.string().optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string; sourceId: string }> },
) {
  const { sourceId } = await params;
  const body = updateSchema.parse(await request.json());

  const data: Record<string, unknown> = { ...body };
  if (body.rawTranscript !== undefined) {
    const normalized = normalizeTranscript(body.rawTranscript);
    data.rawTranscript = normalized;
    data.normalizedHash = hashTranscript(normalized);
    data.transcriptStatus = normalized ? "transcript_ready" : "needs_transcript";
    data.transcriptOrigin = normalized ? "manual" : null;
  }

  const source = await prisma.source.update({ where: { id: sourceId }, data });

  if (body.rawTranscript) {
    await persistTranscriptSegments(sourceId, normalizeTranscript(body.rawTranscript));
  }

  return NextResponse.json(source);
}
