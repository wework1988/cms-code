import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  findProject: vi.fn(),
  countFacts: vi.fn(),
  runStage: vi.fn(),
}));

vi.mock("@/lib/db", () => ({
  prisma: { project: { findUnique: mocks.findProject }, factPackItem: { count: mocks.countFacts } },
}));
vi.mock("@/lib/pipeline/runner", () => ({ runPipelineStage: mocks.runStage }));

import { POST } from "@/app/api/projects/[projectId]/prepare-facts/route";
import { GET } from "@/app/api/projects/[projectId]/external-writer-brief/route";

const context = () => ({ params: Promise.resolve({ projectId: "test-story" }) });
const request = () => new Request("http://localhost/api/projects/test-story/prepare-facts", { method: "POST" });

beforeEach(() => {
  vi.resetAllMocks();
  mocks.findProject.mockResolvedValue({
    sources: [{ title: "Source A", rawTranscript: "Source material" }],
    _count: { factPackItems: 0 },
  });
  mocks.countFacts.mockResolvedValue(4);
  mocks.runStage.mockResolvedValue(undefined);
});

describe("facts-only preparation", () => {
  it("stops at fact_pack_ready without invoking planning, narration, or QA", async () => {
    const response = await POST(request(), context());
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ ok: true, factCount: 4 });
    expect(mocks.runStage.mock.calls).toEqual([
      ["test-story", "normalize_sources"],
      ["test-story", "extract_claims"],
      ["test-story", "merge_fact_pack"],
    ]);
  });

  it("leaves existing fact selections and edits untouched", async () => {
    mocks.findProject.mockResolvedValue({ sources: [], _count: { factPackItems: 5 } });
    const response = await POST(request(), context());
    expect(await response.json()).toEqual({ ok: true, factCount: 5 });
    expect(mocks.runStage).not.toHaveBeenCalled();
  });

  it.each([
    { sources: [] },
    { sources: [{ title: "Missing transcript", rawTranscript: "  " }] },
  ])(
    "rejects incomplete sources before running any pipeline stage: $sources",
    async ({ sources }) => {
      mocks.findProject.mockResolvedValue({ sources, _count: { factPackItems: 0 } });
      const response = await POST(request(), context());
      expect(response.status).toBe(400);
      expect(mocks.runStage).not.toHaveBeenCalled();
    },
  );

  it("does not merge or write a story after extraction fails", async () => {
    mocks.runStage.mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error("Extraction failed"));
    const response = await POST(request(), context());
    expect(response.status).toBe(500);
    expect(await response.json()).toEqual({ error: "Extraction failed" });
    expect(mocks.runStage).toHaveBeenCalledTimes(2);
    expect(mocks.countFacts).not.toHaveBeenCalled();
  });

  it("reports zero extracted facts as a failure", async () => {
    mocks.countFacts.mockResolvedValue(0);
    const response = await POST(request(), context());
    expect(response.status).toBe(422);
  });

  it("returns 404 without running anything for a missing project", async () => {
    mocks.findProject.mockResolvedValue(null);
    expect((await POST(request(), context())).status).toBe(404);
    expect(mocks.runStage).not.toHaveBeenCalled();
  });
});

describe("master prompt prerequisites", () => {
  it("does not return a prompt when no enabled facts exist", async () => {
    mocks.findProject.mockResolvedValue({ factPackItems: [] });
    const response = await GET(new Request("http://localhost"), context());
    expect(response.status).toBe(409);
    expect(await response.json()).not.toHaveProperty("prompt");
  });

  it("copies prepared bullets without running generation", async () => {
    mocks.findProject.mockResolvedValue({
      title: "Story", factPackItems: [{ neutralStatement: "A neutral claim." }],
      ctaPreference: "two_mid_and_closing",
      ctaChannelName: "User channel",
      ctaClosingWording: "Invite a comment about the central question.",
    });
    const response = await GET(new Request("http://localhost"), context());
    expect(response.status).toBe(200);
    const { prompt } = await response.json();
    expect(prompt).toContain("A neutral claim.");
    expect(prompt).toContain("Include exactly 2 mid-story CTAs");
    expect(prompt).toContain("Channel name supplied by the user: User channel");
    expect(prompt).toContain("User-supplied closing wording preference: Invite a comment about the central question.");
    expect(mocks.runStage).not.toHaveBeenCalled();
  });
});
