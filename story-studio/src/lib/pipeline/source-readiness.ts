import { prisma } from "@/lib/db";

export class MissingTranscriptError extends Error {
  constructor(
    public missingSources: Array<{ id: string; title: string; url?: string | null }>,
  ) {
    const names = missingSources.map((s) => s.title).join(", ");
    super(
      `Generation blocked: paste a transcript for all sources before running the pipeline. Missing: ${names}. YouTube URLs are kept as references only.`,
    );
    this.name = "MissingTranscriptError";
  }
}

export async function assertAllSourcesHaveTranscripts(projectId: string): Promise<void> {
  const sources = await prisma.source.findMany({ where: { projectId } });
  const missing = sources.filter((s) => !s.rawTranscript?.trim());

  if (missing.length > 0) {
    throw new MissingTranscriptError(
      missing.map((s) => ({ id: s.id, title: s.title, url: s.url })),
    );
  }
}

export async function getSourcesMissingTranscripts(projectId: string) {
  const sources = await prisma.source.findMany({ where: { projectId } });
  return sources.filter((s) => !s.rawTranscript?.trim());
}
