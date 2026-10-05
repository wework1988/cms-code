import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function POST(_: Request, { params }: { params: Promise<{ projectId: string; planId: string }> }) {
  const { projectId, planId } = await params;

  await prisma.narrativePlan.updateMany({ where: { projectId }, data: { isSelected: false } });
  await prisma.narrativePlan.update({ where: { id: planId }, data: { isSelected: true } });
  await prisma.project.update({ where: { id: projectId }, data: { selectedPlanId: planId } });

  return NextResponse.json({ ok: true });
}
