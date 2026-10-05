import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { z } from "zod";

const updateSchema = z.object({
  name: z.string().min(1).optional(),
  genre: z.string().optional(),
  styleInstructions: z.string().min(1).optional(),
  targetLanguage: z.string().optional(),
  audience: z.string().optional(),
  pacingNotes: z.string().optional(),
  ctaNotes: z.string().optional(),
  titleNotes: z.string().optional(),
  thumbnailNotes: z.string().optional(),
  visualNotes: z.string().optional(),
  preferredVocab: z.string().optional(),
  bannedPhrases: z.string().optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await params;
  const body = updateSchema.parse(await request.json());
  const profile = await prisma.promptProfile.update({
    where: { id: profileId },
    data: { ...body, version: { increment: 1 } },
  });
  return NextResponse.json(profile);
}

export async function DELETE(
  _: Request,
  { params }: { params: Promise<{ profileId: string }> },
) {
  const { profileId } = await params;
  await prisma.promptProfile.delete({ where: { id: profileId } });
  return NextResponse.json({ ok: true });
}
