import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { countCharacters, isInLengthRange, lengthRange, resolveTargetCharCount, formatLengthMissMessage, assembleNarration, splitNarrationParagraphs } from "@/lib/narration/count";
import { estimateDurationSeconds } from "@/lib/utils";
import { z } from "zod";

const saveSchema = z.object({
  content: z.string(),
  changeNote: z.string().optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await params;
  const body = saveSchema.parse(await request.json());
  const project = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });
  const range = lengthRange(resolveTargetCharCount(project.targetCharCount));
  const narration = body.content.trim();
  const charCount = countCharacters(narration);
  const inRange = isInLengthRange(charCount, range);
  const parts = splitNarrationParagraphs(narration);

  await prisma.scriptVersion.updateMany({
    where: { projectId },
    data: { isCurrent: false },
  });

  const previous = await prisma.scriptVersion.findFirst({
    where: { projectId },
    orderBy: { versionNumber: "desc" },
    include: { paragraphs: { orderBy: { paragraphIndex: "asc" } } },
  });

  const versionNumber = (await prisma.scriptVersion.count({ where: { projectId } })) + 1;
  const version = await prisma.scriptVersion.create({
    data: {
      projectId,
      versionNumber,
      content: narration,
      charCount,
      estDurationSec: estimateDurationSeconds(charCount),
      isCurrent: true,
      changeNote: body.changeNote ?? "Manual edit",
    },
  });

  for (let i = 0; i < parts.length; i++) {
    await prisma.scriptParagraphTrace.create({
      data: {
        scriptVersionId: version.id,
        paragraphIndex: i,
        paragraphText: parts[i],
        factIds: previous?.paragraphs[i]?.factIds ?? "[]",
        paragraphRole: previous?.paragraphs[i]?.paragraphRole ?? "narrative",
      },
    });
  }

  await prisma.project.update({
    where: { id: projectId },
    data: {
      status: "script_generated",
      lengthStatus: inRange ? "ready" : "target_not_reached",
      errorMessage: inRange ? null : formatLengthMissMessage(charCount, range.target),
    },
  });

  return NextResponse.json({
    ...version,
    assembledMatches: assembleNarration(parts.map((text) => ({ text }))) === narration,
  });
}

export async function GET(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const versions = await prisma.scriptVersion.findMany({
    where: { projectId },
    orderBy: { versionNumber: "desc" },
  });
  return NextResponse.json(versions);
}
