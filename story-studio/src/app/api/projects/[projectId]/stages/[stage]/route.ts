import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { runPipelineStage, type PipelineStage } from "@/lib/pipeline/runner";

const VALID_STAGES = new Set<PipelineStage>([
  "normalize_sources",
  "extract_claims",
  "merge_fact_pack",
  "generate_plans",
  "generate_script",
  "originality_qa",
]);

export async function POST(_: Request, { params }: { params: Promise<{ projectId: string; stage: string }> }) {
  const { projectId, stage } = await params;
  if (!VALID_STAGES.has(stage as PipelineStage)) {
    return NextResponse.json({ error: "Invalid stage" }, { status: 400 });
  }

  try {
    await runPipelineStage(projectId, stage as PipelineStage);
    const project = await prisma.project.findUnique({ where: { id: projectId } });
    return NextResponse.json({
      ok: true,
      lengthStatus: project?.lengthStatus ?? null,
      errorMessage: project?.errorMessage ?? null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Stage failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
