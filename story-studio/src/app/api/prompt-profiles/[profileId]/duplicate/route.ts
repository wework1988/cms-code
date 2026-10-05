import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function POST(_: Request, { params }: { params: Promise<{ profileId: string }> }) {
  const { profileId } = await params;
  const source = await prisma.promptProfile.findUniqueOrThrow({ where: { id: profileId } });

  const profile = await prisma.promptProfile.create({
    data: {
      name: `${source.name} (copy)`,
      genre: source.genre,
      styleInstructions: source.styleInstructions,
      targetLanguage: source.targetLanguage,
      audience: source.audience,
      pacingNotes: source.pacingNotes,
      ctaNotes: source.ctaNotes,
      titleNotes: source.titleNotes,
      thumbnailNotes: source.thumbnailNotes,
      visualNotes: source.visualNotes,
      preferredVocab: source.preferredVocab,
      bannedPhrases: source.bannedPhrases,
      version: 1,
    },
  });

  return NextResponse.json(profile);
}
