import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function POST(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;

  await prisma.project.update({
    where: { id: projectId },
    data: { exportOverride: true },
  });

  const report = await prisma.originalityReport.findFirst({
    where: { projectId },
    orderBy: { createdAt: "desc" },
  });

  if (report) {
    await prisma.originalityReport.update({
      where: { id: report.id },
      data: { exportOverride: true },
    });
  }

  return NextResponse.json({
    ok: true,
    message: "Export override enabled. This does not constitute legal copyright clearance.",
  });
}
