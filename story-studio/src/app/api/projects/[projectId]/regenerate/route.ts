import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { regenerateFromSavedSettings } from "@/lib/pipeline/runner";
import { z } from "zod";

const bodySchema = z.object({
  scope: z.enum(["script_only", "plan_and_script"]).default("script_only"),
});

export async function POST(request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const parsed = bodySchema.safeParse(await request.json().catch(() => ({})));
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid regenerate request." }, { status: 400 });
  }

  try {
    await regenerateFromSavedSettings(projectId, parsed.data.scope);
    const project = await prisma.project.findUnique({ where: { id: projectId } });
    return NextResponse.json({
      ok: true,
      lengthStatus: project?.lengthStatus ?? null,
      errorMessage: project?.errorMessage ?? null,
      status: project?.status ?? null,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Regeneration failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
