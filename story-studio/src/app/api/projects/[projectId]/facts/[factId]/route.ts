import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { z } from "zod";

const updateSchema = z.object({
  neutralStatement: z.string().optional(),
  disabled: z.boolean().optional(),
  userPinned: z.boolean().optional(),
  userEdited: z.boolean().optional(),
  editorNotes: z.string().optional(),
});

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ projectId: string; factId: string }> },
) {
  const { factId } = await params;
  const body = updateSchema.parse(await request.json());

  const data = {
    ...body,
    userEdited: body.neutralStatement !== undefined ? true : body.userEdited,
  };

  const fact = await prisma.factPackItem.update({
    where: { id: factId },
    data,
  });

  return NextResponse.json(fact);
}
