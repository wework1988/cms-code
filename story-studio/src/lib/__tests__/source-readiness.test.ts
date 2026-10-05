import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { execSync } from "child_process";
import { getTestPrisma, resetTestDb } from "@/lib/__tests__/test-db";
import { assertAllSourcesHaveTranscripts, MissingTranscriptError } from "@/lib/pipeline/source-readiness";

describe("source readiness", () => {
  beforeAll(() => {
    execSync("npx prisma db push --skip-generate", { stdio: "ignore" });
  });

  beforeEach(async () => {
    await resetTestDb();
  });

  it("rejects URL-only YouTube sources until transcript is pasted", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();

    const project = await createProjectWithSources({
      title: "URL only",
      sources: [
        {
          kind: "youtube",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        },
      ],
    });

    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    expect(source.url).toContain("youtube.com");
    expect(source.rawTranscript).toBeNull();
    expect(source.transcriptStatus).toBe("needs_transcript");

    await expect(assertAllSourcesHaveTranscripts(project.id)).rejects.toBeInstanceOf(MissingTranscriptError);
  });

  it("allows pipeline when transcript is pasted", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");

    const project = await createProjectWithSources({
      title: "With transcript",
      sources: [
        {
          kind: "youtube",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          transcript: "[00:01] Pasted transcript content for testing.",
        },
      ],
    });

    await expect(assertAllSourcesHaveTranscripts(project.id)).resolves.toBeUndefined();
  });
});
