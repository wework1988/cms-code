import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { z } from "zod";

const profileSchema = z.object({
  name: z.string().min(1),
  genre: z.string().optional(),
  styleInstructions: z.string().min(1),
  targetLanguage: z.string().default("hi"),
  audience: z.string().optional(),
  pacingNotes: z.string().optional(),
  ctaNotes: z.string().optional(),
  titleNotes: z.string().optional(),
  thumbnailNotes: z.string().optional(),
  visualNotes: z.string().optional(),
  preferredVocab: z.string().optional(),
  bannedPhrases: z.string().optional(),
});

export async function GET() {
  const profiles = await prisma.promptProfile.findMany({ orderBy: { updatedAt: "desc" } });
  return NextResponse.json(profiles);
}

export async function POST(request: Request) {
  const body = profileSchema.parse(await request.json());
  const profile = await prisma.promptProfile.create({ data: body });
  return NextResponse.json(profile);
}
