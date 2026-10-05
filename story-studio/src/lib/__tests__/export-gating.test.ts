import { beforeEach, describe, expect, it } from "vitest";
import { getTestPrisma, resetTestDb } from "@/lib/__tests__/test-db";
import { buildNarrationExport } from "@/lib/narration/sanitize";

describe("export gating", () => {
  beforeEach(async () => {
    await resetTestDb();
  });

  it("blocks export when status is BLOCK without override", async () => {
    const prisma = getTestPrisma();
    const project = await prisma.project.create({ data: { title: "Export test" } });

    await prisma.scriptVersion.create({
      data: {
        projectId: project.id,
        versionNumber: 1,
        content: "Test script",
        charCount: 11,
        isCurrent: true,
      },
    });

    await prisma.originalityReport.create({
      data: {
        projectId: project.id,
        overallStatus: "block",
        phraseOverlap: "block",
        hookSimilarity: "block",
        orderSimilarity: "block",
        recommendedAction: "Re-plan",
        exportBlocked: true,
      },
    });

    const loaded = await prisma.project.findUniqueOrThrow({ where: { id: project.id } });
    const report = await prisma.originalityReport.findFirst({ where: { projectId: project.id } });

    const blocked =
      report?.overallStatus === "block" &&
      report.exportBlocked &&
      !loaded.exportOverride &&
      !report.exportOverride;

    expect(blocked).toBe(true);

    await prisma.project.update({ where: { id: project.id }, data: { exportOverride: true } });
    const after = await prisma.project.findUniqueOrThrow({ where: { id: project.id } });
    expect(after.exportOverride).toBe(true);
  });

  it("keeps txt/md narration exports free of appended reports", () => {
    const exported = buildNarrationExport("पूरी कहानी।\n\n---\n*Editorial draft — not legal clearance.*");
    expect(exported).toBe("पूरी कहानी।");
    expect(exported).not.toContain("Editorial");
    expect(exported).not.toContain("#");
  });
});
