import { NextResponse } from "next/server";
import { z } from "zod";
import { prisma } from "@/lib/db";
import { fetchMissingPublicCaptions } from "@/lib/transcript/fetch-source";
import type { TranscriptLanguage } from "@/lib/transcript/types";

export const runtime = "nodejs";

const bodySchema = z.object({
  language: z.enum(["hi", "en"]).optional(),
});

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await params;
  const body = bodySchema.parse(await request.json().catch(() => ({})));
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    select: { outputLanguage: true },
  });
  if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });

  const language: TranscriptLanguage = body.language ?? (project.outputLanguage?.toLowerCase().startsWith("en") ? "en" : "hi");
  const result = await fetchMissingPublicCaptions({ projectId, language });
  if (!result.ok) return NextResponse.json({ error: result.message }, { status: 404 });

  return NextResponse.json({
    ok: true,
    stopped: result.stopped,
    results: result.results.map((item) =>
      item.ok
        ? item
        : { sourceId: item.sourceId, title: item.title, ok: false, code: item.code, error: item.message, availableLanguages: item.availableLanguages ?? [] },
    ),
  });
}
