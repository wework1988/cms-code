import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { runPipelineStage, generateScript } from "@/lib/pipeline/runner";
import { z } from "zod";

const schema = z.object({
  action: z.enum(["rewrite", "replan"]),
  findingCategories: z.array(z.string()).optional(),
});

export async function POST(
  request: Request,
  { params }: { params: Promise<{ projectId: string }> },
) {
  const { projectId } = await params;
  const body = schema.parse(await request.json());

  if (body.action === "replan") {
    await runPipelineStage(projectId, "generate_plans");
    return NextResponse.json({ ok: true, action: "replan" });
  }

  await generateScript(projectId, `Targeted rewrite: ${body.findingCategories?.join(", ") ?? "flagged sections"}`);
  await runPipelineStage(projectId, "originality_qa");
  const project = await prisma.project.findUnique({ where: { id: projectId } });
  return NextResponse.json({
    ok: true,
    action: "rewrite",
    lengthStatus: project?.lengthStatus ?? null,
    errorMessage: project?.errorMessage ?? null,
  });
}
