import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { buildExternalWriterBrief } from "@/lib/external-writer-brief";

export async function GET(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    include: {
      promptProfile: {
        select: {
          name: true,
          genre: true,
          styleInstructions: true,
          audience: true,
          pacingNotes: true,
          ctaNotes: true,
          preferredVocab: true,
          bannedPhrases: true,
        },
      },
      factPackItems: {
        where: { disabled: false },
        select: { neutralStatement: true, storyImportance: true },
      },
    },
  });

  if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });

  if (!project.factPackItems.some((fact) => fact.neutralStatement.trim())) {
    return NextResponse.json(
      { error: "No enabled fact bullets yet. Generate fact bullets, then review and enable the ones to include in your master prompt." },
      { status: 409 },
    );
  }

  return NextResponse.json({
    prompt: buildExternalWriterBrief({
      title: project.title,
      topic: project.topic,
      outputLanguage: project.outputLanguage,
      targetCharCount: project.targetCharCount,
      audience: project.audience,
      genre: project.genre,
      tone: project.tone,
      mustCoverPoints: project.mustCoverPoints,
      narrativeGoal: project.narrativeGoal,
      narrativeApproachCustom: project.narrativeApproachCustom,
      openingHook: project.openingHook,
      openingHookCustom: project.openingHookCustom,
      ctaPreference: project.ctaPreference,
      ctaChannelName: project.ctaChannelName,
      ctaClosingWording: project.ctaClosingWording,
      promptProfile: project.promptProfile,
      facts: project.factPackItems,
    }),
  });
}
