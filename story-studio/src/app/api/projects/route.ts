import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { createProjectSchema } from "@/lib/schemas";
import { createProjectWithSources } from "@/lib/pipeline/runner";

export async function GET() {
  const projects = await prisma.project.findMany({
    orderBy: { updatedAt: "desc" },
    include: {
      sources: true,
      scriptVersions: { where: { isCurrent: true }, take: 1 },
    },
  });

  return NextResponse.json(
    projects.map((p) => ({
      id: p.id,
      title: p.title,
      status: p.status,
      sourceCount: p.sources.length,
      updatedAt: p.updatedAt,
      scriptLength: p.scriptVersions[0]?.charCount ?? 0,
      isDemo: p.isDemo,
    })),
  );
}

export async function POST(request: Request) {
  try {
    const body = createProjectSchema.parse(await request.json());
    const project = await createProjectWithSources(body);
    return NextResponse.json({ id: project.id });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
