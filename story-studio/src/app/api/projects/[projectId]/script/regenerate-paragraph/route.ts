import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { getLLMProvider, isLLMConfigured } from "@/lib/llm/provider";
import { assembleNarration, countCharacters, isInLengthRange, lengthRange, resolveTargetCharCount, formatLengthMissMessage } from "@/lib/narration/count";
import { sanitizeNarration } from "@/lib/narration/sanitize";
import { estimateDurationSeconds } from "@/lib/utils";
import { resolveCtaConfig } from "@/lib/cta/config";
import { z } from "zod";

const schema = z.object({
  paragraphIndex: z.number(),
  instruction: z.string().optional(),
});

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await params;
  if (!isLLMConfigured()) {
    return NextResponse.json({ error: "LLM not configured" }, { status: 400 });
  }

  const body = schema.parse(await request.json());
  const project = await prisma.project.findUniqueOrThrow({
    where: { id: projectId },
    include: { promptProfile: true, channelStyle: true },
  });
  const script = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
    include: { paragraphs: { orderBy: { paragraphIndex: "asc" } } },
  });
  if (!script) return NextResponse.json({ error: "No script" }, { status: 404 });

  const paragraph = script.paragraphs.find((p) => p.paragraphIndex === body.paragraphIndex);
  if (!paragraph) return NextResponse.json({ error: "Paragraph not found" }, { status: 404 });

  const llm = getLLMProvider();
  const cta = resolveCtaConfig({
    targetCharCount: project.targetCharCount,
    projectChoice: project.ctaPreference,
    projectChannelName: project.ctaChannelName,
    projectClosingWording: project.ctaClosingWording,
    promptProfile: project.promptProfile,
    channelStyle: project.channelStyle,
  });
  const role = paragraph.paragraphRole ?? "narrative";
  const ctaInstruction =
    role === "cta_mid" || role === "cta_closing"
      ? `This paragraph is a ${role === "cta_closing" ? "closing" : "mid-story"} CTA. Keep it as natural spoken Hindi CTA aligned to mode ${cta.mode}.`
      : "Keep this as narrative paragraph only (no CTA labels or editorial sections).";
  const rewritten = sanitizeNarration(
    await llm.generateText(
      `Rewrite this Hindi documentary paragraph. ${ctaInstruction} Keep only spoken narration. Do not add reports, titles, or fact IDs in the text.\n\n${paragraph.paragraphText}\n\n${body.instruction ?? ""}`,
      "Return only the rewritten Devanagari Hindi paragraph.",
    ),
  );

  const nextParagraphs = script.paragraphs.map((p) =>
    p.paragraphIndex === body.paragraphIndex ? { ...p, paragraphText: rewritten } : p,
  );
  const newContent = assembleNarration(nextParagraphs.map((p) => ({ text: p.paragraphText })));
  const charCount = countCharacters(newContent);
  const range = lengthRange(resolveTargetCharCount(project.targetCharCount));
  const inRange = isInLengthRange(charCount, range);

  await prisma.scriptVersion.updateMany({ where: { projectId }, data: { isCurrent: false } });
  const versionNumber = (await prisma.scriptVersion.count({ where: { projectId } })) + 1;
  const version = await prisma.scriptVersion.create({
    data: {
      projectId,
      versionNumber,
      content: newContent,
      charCount,
      estDurationSec: estimateDurationSeconds(charCount),
      isCurrent: true,
      changeNote: `Regenerated paragraph ${body.paragraphIndex + 1}`,
    },
  });

  for (const p of nextParagraphs) {
    await prisma.scriptParagraphTrace.create({
      data: {
        scriptVersionId: version.id,
        paragraphIndex: p.paragraphIndex,
        paragraphText: p.paragraphText,
        factIds: p.factIds,
        paragraphRole: p.paragraphRole ?? "narrative",
      },
    });
  }

  await prisma.project.update({
    where: { id: projectId },
    data: {
      lengthStatus: inRange ? "ready" : "target_not_reached",
      errorMessage: inRange ? null : formatLengthMissMessage(charCount, range.target),
    },
  });

  return NextResponse.json({ version, paragraph: rewritten });
}
