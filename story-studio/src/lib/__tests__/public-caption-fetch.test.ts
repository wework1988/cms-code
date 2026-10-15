import { beforeAll, beforeEach, describe, expect, it } from "vitest";
import { execSync } from "child_process";
import { getTestPrisma, resetTestDb } from "@/lib/__tests__/test-db";
import { assertAllSourcesHaveTranscripts } from "@/lib/pipeline/source-readiness";
import { resetTranscriptGateForTests } from "@/lib/transcript/gate";
import { fetchPublicCaptionForSource } from "@/lib/transcript/fetch-source";
import { hashTranscript } from "@/lib/transcript/normalize";
import { createTranscriptProvider, setTranscriptProviderForTests } from "@/lib/transcript/provider";
import { POST } from "@/app/api/projects/[projectId]/sources/[sourceId]/fetch-transcript/route";

const fetched = {
  ok: true as const,
  language: "Hindi",
  languageCode: "hi",
  captionKind: "manual" as const,
  segments: [{ text: "Fetched public caption", start: 1.5, duration: 2 }],
};

describe("public caption saving", () => {
  beforeAll(() => {
    execSync("npx prisma db push --skip-generate", { stdio: "ignore" });
  });

  beforeEach(async () => {
    await resetTestDb();
    resetTranscriptGateForTests();
    process.env.YOUTUBE_TRANSCRIPT_MIN_INTERVAL_MS = "0";
    process.env.YOUTUBE_TRANSCRIPT_PROXY = "off";
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => fetched,
      }),
    );
  });

  it("saves a fetched transcript and marks the source ready", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    const project = await createProjectWithSources({
      title: "Fetched",
      sources: [{ kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });

    const result = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
    });

    expect(result).toMatchObject({
      ok: true,
      transcriptOrigin: "public_caption",
      language: "hi",
      captionKind: "manual",
      fromCache: false,
    });
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(saved.rawTranscript).toContain("Fetched public caption");
    expect(saved.transcriptStatus).toBe("transcript_ready");
    expect(saved.normalizedHash).toBe(hashTranscript(saved.rawTranscript ?? ""));
    const segments = await prisma.transcriptSegment.findMany({ where: { sourceId: source.id } });
    expect(segments[0]).toMatchObject({ startSec: 1.5, text: "Fetched public caption" });
    await expect(assertAllSourcesHaveTranscripts(project.id)).resolves.toBeUndefined();
  });

  it("reuses the caption cache for another source of the same video", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    let calls = 0;
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => {
          calls += 1;
          return fetched;
        },
      }),
    );
    const project = await createProjectWithSources({
      title: "Cached",
      sources: [
        { kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", title: "First" },
        { kind: "youtube", url: "https://youtu.be/dQw4w9WgXcQ", title: "Second" },
      ],
    });
    const sources = await prisma.source.findMany({ where: { projectId: project.id }, orderBy: { createdAt: "asc" } });

    await fetchPublicCaptionForSource({ projectId: project.id, sourceId: sources[0].id, language: "hi" });
    const second = await fetchPublicCaptionForSource({ projectId: project.id, sourceId: sources[1].id, language: "hi" });
    const refreshed = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: sources[0].id,
      language: "hi",
      replace: true,
      refresh: true,
    });

    expect(second).toMatchObject({ ok: true, fromCache: true });
    expect(refreshed).toMatchObject({ ok: true, fromCache: false });
    expect(calls).toBe(2);
  });

  it("keeps a manual transcript until replacement is confirmed", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    let calls = 0;
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => {
          calls += 1;
          return fetched;
        },
      }),
    );
    const project = await createProjectWithSources({
      title: "Manual",
      sources: [
        {
          kind: "youtube",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          transcript: "Pasted by hand",
        },
      ],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    const result = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
    });
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(result).toMatchObject({ ok: false, code: "replace_required" });
    expect(calls).toBe(0);
    expect(saved.rawTranscript).toBe("Pasted by hand");
    expect(saved.transcriptOrigin).toBe("manual");
  });

  it("does not save a fetch that finishes after the transcript was edited", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    const project = await createProjectWithSources({
      title: "Race",
      sources: [{ kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => {
          const edited = "Edited while fetching";
          await prisma.source.update({
            where: { id: source.id },
            data: {
              rawTranscript: edited,
              normalizedHash: hashTranscript(edited),
              transcriptOrigin: "manual",
              transcriptStatus: "transcript_ready",
              transcriptRevision: { increment: 1 },
            },
          });
          return fetched;
        },
      }),
    );

    const result = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
      replace: true,
    });
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(result).toMatchObject({ ok: false, code: "stale" });
    expect(saved.rawTranscript).toBe("Edited while fetching");
    expect(saved.transcriptOrigin).toBe("manual");
  });

  it("leaves the transcript empty when the requested language is unavailable", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => ({
          ok: false,
          code: "language_unavailable",
          message: "The requested language is not available. Available captions: English (automatic). Choose one of those languages or paste the transcript manually.",
          availableLanguages: [{ languageCode: "en", language: "English", captionKind: "generated" }],
        }),
      }),
    );
    const project = await createProjectWithSources({
      title: "Language",
      sources: [{ kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    const result = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
    });
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(result).toMatchObject({
      ok: false,
      code: "language_unavailable",
      availableLanguages: [{ languageCode: "en", captionKind: "generated" }],
    });
    expect(saved.rawTranscript).toBeNull();
  });

  it("stops after an IP block and keeps the existing URL and transcript", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    let calls = 0;
    setTranscriptProviderForTests(
      createTranscriptProvider({
        network: async () => {
          calls += 1;
          return { ok: false, code: "blocked", message: "" };
        },
      }),
    );
    const project = await createProjectWithSources({
      title: "Blocked",
      sources: [{ kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", transcript: "Keep me" }],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    const first = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
      replace: true,
    });
    const second = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
      replace: true,
    });
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(first).toMatchObject({ ok: false, code: "blocked" });
    expect(first.ok ? "" : first.message).toContain("Paste the transcript manually");
    expect(second).toMatchObject({ ok: false, code: "blocked" });
    expect(calls).toBe(1);
    expect(saved.url).toContain("youtube.com/watch?v=dQw4w9WgXcQ");
    expect(saved.rawTranscript).toBe("Keep me");
    expect(saved.transcriptOrigin).toBe("manual");
  });

  it("rejects a source that belongs to another project", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    const project = await createProjectWithSources({
      title: "Owner",
      sources: [{ kind: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }],
    });
    const other = await createProjectWithSources({
      title: "Other",
      sources: [{ kind: "pasted", transcript: "Other transcript" }],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    const response = await POST(new Request("http://localhost/fetch", { method: "POST", body: JSON.stringify({ language: "hi" }) }), {
      params: Promise.resolve({ projectId: other.id, sourceId: source.id }),
    });
    expect(response.status).toBe(404);
    const saved = await prisma.source.findFirstOrThrow({ where: { id: source.id } });
    expect(saved.rawTranscript).toBeNull();
  });

  it("disables old fact pointers after the transcript text changes", async () => {
    const { createProjectWithSources } = await import("@/lib/pipeline/runner");
    const prisma = getTestPrisma();
    const project = await createProjectWithSources({
      title: "Facts",
      sources: [
        {
          kind: "youtube",
          url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
          transcript: "Original pasted transcript",
        },
      ],
    });
    const source = await prisma.source.findFirstOrThrow({ where: { projectId: project.id } });
    const claim = await prisma.claim.create({
      data: {
        projectId: project.id,
        sourceId: source.id,
        neutralClaim: "Old claim",
        claimType: "event",
        supportExcerpt: "Original pasted transcript",
        sourceCertainty: "medium",
        storyRelevance: "high",
      },
    });
    await prisma.factPackItem.create({
      data: {
        projectId: project.id,
        factId: "fact-001",
        neutralStatement: "Old claim",
        sourceClaimIds: JSON.stringify([claim.id]),
        sourceCount: 1,
        storyImportance: "high",
      },
    });
    await prisma.factPackItem.create({
      data: {
        projectId: project.id,
        factId: "fact-002",
        neutralStatement: "Pinned old claim",
        sourceClaimIds: JSON.stringify([claim.id]),
        sourceCount: 1,
        storyImportance: "high",
        userPinned: true,
      },
    });

    const result = await fetchPublicCaptionForSource({
      projectId: project.id,
      sourceId: source.id,
      language: "hi",
      replace: true,
    });
    expect(result.ok).toBe(true);
    expect(await prisma.claim.count({ where: { sourceId: source.id } })).toBe(0);
    expect(await prisma.factPackItem.findFirst({ where: { factId: "fact-001" } })).toBeNull();
    const pinned = await prisma.factPackItem.findFirstOrThrow({ where: { factId: "fact-002" } });
    expect(pinned.disabled).toBe(true);
  });
});
