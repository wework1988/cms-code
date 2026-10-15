import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { fetchPublicCaptionForSource } from "@/lib/transcript/fetch-source";
import { statusForTranscriptError, type TranscriptLanguage } from "@/lib/transcript/types";

export const runtime = "nodejs";

const bodySchema = z.object({
  language: z.enum(["hi", "en"]).optional(),
  replace: z.boolean().optional(),
  refresh: z.boolean().optional(),
  url: z.string().optional(),
});

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectId: string; sourceId: string }> },
) {
  const { projectId, sourceId } = await params;
  const body = bodySchema.parse(await request.json().catch(() => ({})));
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    select: { outputLanguage: true },
  });
  if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const language: TranscriptLanguage =
    body.language ?? (project.outputLanguage?.toLowerCase().startsWith("en") ? "en" : "hi");

  try {
    const result = await fetchPublicCaptionForSource({
      projectId,
      sourceId,
      language,
      replace: body.replace,
      refresh: body.refresh,
      url: body.url,
    });

    if (!result.ok) {
      return NextResponse.json(
        { error: result.message, code: result.code, availableLanguages: result.availableLanguages ?? [] },
        { status: statusForTranscriptError(result.code) },
      );
    }

    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Transcript fetch failed";
    return NextResponse.json({ error: message, code: "temporary" }, { status: 500 });
  }
}
