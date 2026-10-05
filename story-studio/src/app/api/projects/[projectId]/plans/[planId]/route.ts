import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { validateFactIds } from "@/lib/pipeline/validate-ids";
import { z } from "zod";

const updateSchema = z.object({
  centralQuestion: z.string().optional(),
  openingApproach: z.string().optional(),
  narrativeLens: z.string().optional(),
  diffExplanation: z.string().optional(),
  beats: z
    .array(
      z.object({
        beatNumber: z.number(),
        purpose: z.string(),
        shortDescription: z.string(),
        claimIds: z.array(z.string()),
        narrativeRole: z.string(),
        proposedVisualIdea: z.string().optional(),
        expectedDurationSeconds: z.number().optional(),
      }),
    )
    .optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string; planId: string }> },
) {
  const { projectId, planId } = await params;
  const body = updateSchema.parse(await request.json());

  const facts = await prisma.factPackItem.findMany({ where: { projectId, disabled: false } });
  const validFactIds = new Set(facts.map((f) => f.factId));

  const plan = await prisma.narrativePlan.update({
    where: { id: planId },
    data: {
      centralQuestion: body.centralQuestion,
      openingApproach: body.openingApproach,
      narrativeLens: body.narrativeLens,
      diffExplanation: body.diffExplanation,
      isEdited: true,
    },
  });

  if (body.beats) {
    await prisma.narrativeBeat.deleteMany({ where: { planId } });
    for (const beat of body.beats) {
      await prisma.narrativeBeat.create({
        data: {
          planId,
          beatNumber: beat.beatNumber,
          purpose: beat.purpose,
          shortDescription: beat.shortDescription,
          claimIds: JSON.stringify(validateFactIds(beat.claimIds, validFactIds)),
          narrativeRole: beat.narrativeRole,
          proposedVisualIdea: beat.proposedVisualIdea,
          expectedDurationSeconds: beat.expectedDurationSeconds,
        },
      });
    }
  }

  return NextResponse.json(plan);
}
