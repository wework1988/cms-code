import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { runPipelineStage } from "@/lib/pipeline/runner";

/** Prepare the external-writer handoff without invoking planning or narration. */
export async function POST(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  try {
    const project = await prisma.project.findUnique({
      where: { id: projectId },
      select: {
        sources: { select: { title: true, rawTranscript: true } },
        _count: { select: { factPackItems: true } },
      },
    });
    if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });

    // Reuse prepared facts, including the user's edits and disabled selections.
    if (project._count.factPackItems > 0) {
      return NextResponse.json({ ok: true, factCount: project._count.factPackItems });
    }
    if (project.sources.length === 0) {
      return NextResponse.json({ error: "Add and save source transcripts first." }, { status: 400 });
    }
    const missing = project.sources.filter((source) => !source.rawTranscript?.trim());
    if (missing.length > 0) {
      return NextResponse.json(
        { error: `Save a transcript for every source first. Missing: ${missing.map((s) => s.title).join(", ")}.` },
        { status: 400 },
      );
    }

    await runPipelineStage(projectId, "normalize_sources");
    await runPipelineStage(projectId, "extract_claims");
    await runPipelineStage(projectId, "merge_fact_pack");

    const factCount = await prisma.factPackItem.count({ where: { projectId } });
    if (factCount === 0) {
      return NextResponse.json(
        { error: "No fact bullets were extracted. Check your source transcripts and try again." },
        { status: 422 },
      );
    }
    return NextResponse.json({ ok: true, factCount });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Fact preparation failed" },
      { status: 500 },
    );
  }
}
