import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { execSync } from "child_process";
import { getTestPrisma, resetTestDb } from "@/lib/__tests__/test-db";
import { loadDemoFixture } from "@/lib/fixtures/demo";

describe("demo project creation", () => {
  beforeAll(() => {
    execSync("npx prisma db push --skip-generate", { stdio: "ignore" });
  });

  beforeEach(async () => {
    await resetTestDb();
  });

  it("creates claims and fingerprints with actual source IDs", async () => {
    const { createProjectWithSources, runFullPipeline } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    const fixture = loadDemoFixture();

    const project = await createProjectWithSources({
      title: "Demo test",
      isDemo: true,
      sources: fixture.demoSources,
    });

    await runFullPipeline(project.id, true);

    const sources = await prisma.source.findMany({ where: { projectId: project.id }, orderBy: { createdAt: "asc" } });
    expect(sources).toHaveLength(2);

    const claims = await prisma.claim.findMany({ where: { projectId: project.id } });
    expect(claims.length).toBeGreaterThan(0);
    for (const claim of claims) {
      expect(sources.some((s) => s.id === claim.sourceId)).toBe(true);
    }

    const fingerprints = await prisma.narrativeFingerprint.findMany({ where: { projectId: project.id } });
    expect(fingerprints).toHaveLength(2);
    for (const fp of fingerprints) {
      expect(sources.some((s) => s.id === fp.sourceId)).toBe(true);
    }
  });
});
