import { NextResponse } from "next/server";
import { loadDemoFixture } from "@/lib/fixtures/demo";
import { createProjectWithSources, runFullPipeline } from "@/lib/pipeline/runner";

export async function POST() {
  try {
    const fixture = loadDemoFixture();
    const project = await createProjectWithSources({
      title: "Demo — East India Company",
      topic: "How a trading company became a political power",
      outputLanguage: "hi",
      targetCharCount: 6000,
      narrativeGoal: "recommend",
      isDemo: true,
      sources: fixture.demoSources,
    });

    await runFullPipeline(project.id, true);

    return NextResponse.json({ id: project.id });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to create demo";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
