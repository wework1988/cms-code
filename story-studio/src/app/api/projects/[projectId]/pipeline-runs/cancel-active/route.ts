import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

/** Marks any in-progress pipeline run as failed so generation can be retried. */
export async function POST(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const result = await prisma.pipelineRun.updateMany({
    where: { projectId, status: "running" },
    data: {
      status: "failed",
      errorMessage: "Cancelled manually. You can run generation again.",
      finishedAt: new Date(),
    },
  });
  if (result.count > 0) {
    await prisma.project.update({
      where: { id: projectId },
      data: {
        errorMessage: "Script generation was cancelled. Use Generate script to try again.",
      },
    });
  }
  return NextResponse.json({ ok: true, cancelled: result.count });
}
