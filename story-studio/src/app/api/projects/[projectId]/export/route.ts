import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { buildNarrationExport } from "@/lib/narration/sanitize";

export async function GET(request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const { searchParams } = new URL(request.url);
  const format = searchParams.get("format") ?? "txt";

  const project = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });
  const script = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
  });

  if (!script) return NextResponse.json({ error: "No script" }, { status: 404 });

  const report = await prisma.originalityReport.findFirst({
    where: { projectId },
    orderBy: { createdAt: "desc" },
  });

  const blocked =
    report?.overallStatus === "block" &&
    report.exportBlocked &&
    !project.exportOverride &&
    !report.exportOverride;

  if (blocked) {
    return NextResponse.json(
      {
        error: "Export blocked by editorial originality review (BLOCK status).",
        recommendedAction: report.recommendedAction,
        hint: "Re-plan narrative structure or POST /export/override to proceed with explicit acknowledgment.",
        disclaimer: "Override does not constitute legal copyright clearance.",
      },
      { status: 403 },
    );
  }

  const filename = `${project.title.replace(/\s+/g, "-").toLowerCase()}.${format}`;
  const body = buildNarrationExport(script.content);

  return new NextResponse(body, {
    headers: {
      "Content-Type": format === "md" ? "text/markdown; charset=utf-8" : "text/plain; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
