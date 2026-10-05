import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { runFullPipeline } from "@/lib/pipeline/runner";

export async function POST(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  try {
    await runFullPipeline(projectId, true);
    const project = await prisma.project.findUnique({ where: { id: projectId } });
    return NextResponse.json({
      ok: true,
      projectId,
      lengthStatus: project?.lengthStatus ?? null,
      errorMessage: project?.errorMessage ?? null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Pipeline failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
