import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { execSync } from "child_process";
import { getTestPrisma, resetTestDb } from "@/lib/__tests__/test-db";
import { buildPromptProfileContext } from "@/lib/prompts/profile";

describe("full pipeline with pasted transcripts", () => {
  beforeAll(() => {
    execSync("npx prisma db push --skip-generate", { stdio: "ignore" });
  });

  beforeEach(async () => {
    await resetTestDb();
  });

  it("persists transcript segments with timestamps", async () => {
    const { createProjectWithSources, runFullPipeline } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();

    const project = await createProjectWithSources({
      title: "Pipeline test",
      isDemo: true,
      sources: [
        {
          kind: "pasted",
          title: "Source A",
          transcript: "[00:12] First segment about the charter.\n[01:30] Second segment about trade.",
        },
        {
          kind: "pasted",
          title: "Source B",
          transcript: "[02:05] Battle of Plassey mentioned here.",
        },
      ],
    });

    await runFullPipeline(project.id, true);

    const segments = await prisma.transcriptSegment.findMany({
      where: { source: { projectId: project.id } },
      orderBy: { orderIndex: "asc" },
    });

    expect(segments.length).toBeGreaterThan(0);
    expect(segments.some((s) => s.startSec !== null)).toBe(true);
  });

  it("stores prompt profile on project and builds context", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();

    const profile = await prisma.promptProfile.create({
      data: {
        name: "Test Profile",
        genre: "History",
        styleInstructions: "Use calm explanatory Hindi.",
      },
    });

    const project = await createProjectWithSources({
      title: "Profile test",
      promptProfileId: profile.id,
      isDemo: true,
      sources: [
        { kind: "pasted", title: "S1", transcript: "[00:01] Test transcript content." },
        { kind: "pasted", title: "S2", transcript: "[00:02] Another transcript segment." },
      ],
    });

    const loaded = await prisma.project.findUniqueOrThrow({
      where: { id: project.id },
      include: { promptProfile: true },
    });

    expect(loaded.promptProfileId).toBe(profile.id);
    const ctx = buildPromptProfileContext(loaded.promptProfile);
    expect(ctx.styleInstructions).toContain("calm explanatory Hindi");
  });
});
