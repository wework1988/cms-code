import { prisma } from "@/lib/db";
import { persistTranscriptSegments } from "@/lib/pipeline/segments";
import { hashTranscript, normalizeTranscript } from "@/lib/transcript/normalize";
import { transcriptErrorMessage, type TranscriptErrorCode } from "@/lib/transcript/types";

export async function invalidateDerivativesForSource(projectId: string, sourceId: string): Promise<void> {
  const claims = await prisma.claim.findMany({ where: { sourceId }, select: { id: true } });
  const claimIds = new Set(claims.map((claim) => claim.id));
  await prisma.claim.deleteMany({ where: { sourceId } });
  await prisma.narrativeFingerprint.deleteMany({ where: { sourceId } });
  if (claimIds.size === 0) return;

  const facts = await prisma.factPackItem.findMany({ where: { projectId } });
  for (const fact of facts) {
    let ids: string[] = [];
    try {
      const parsed = JSON.parse(fact.sourceClaimIds) as unknown;
      if (Array.isArray(parsed)) ids = parsed.filter((id): id is string => typeof id === "string");
    } catch {
      ids = [];
    }
    if (!ids.some((id) => claimIds.has(id))) continue;
    const remaining = ids.filter((id) => !claimIds.has(id));
    if (fact.userPinned || fact.userEdited) {
      await prisma.factPackItem.update({
        where: { id: fact.id },
        data: {
          disabled: true,
          sourceClaimIds: JSON.stringify(remaining),
          editorNotes: "Disabled because the source transcript changed. Review before enabling.",
        },
      });
    } else {
      await prisma.factPackItem.delete({ where: { id: fact.id } });
    }
  }
}

export async function commitSourceTranscript(input: {
  projectId: string;
  sourceId: string;
  text: string;
  origin: "manual" | "official_oauth" | "public_caption" | null;
  language?: string | null;
  captionKind?: string | null;
  segments?: Array<{ startSec: number; duration: number; text: string }>;
  expectedRevision?: number;
}): Promise<
  | { ok: true; normalized: string }
  | { ok: false; code: Extract<TranscriptErrorCode, "not_found" | "stale">; message: string }
> {
  const current = await prisma.source.findFirst({
    where: { id: input.sourceId, projectId: input.projectId },
  });
  if (!current) return { ok: false, code: "not_found", message: transcriptErrorMessage("not_found") };
  if (input.expectedRevision !== undefined && current.transcriptRevision !== input.expectedRevision) {
    return { ok: false, code: "stale", message: transcriptErrorMessage("stale") };
  }

  const normalized = normalizeTranscript(input.text);
  const nextHash = normalized ? hashTranscript(normalized) : null;
  const hashChanged = current.normalizedHash !== nextHash;
  const captionKind =
    input.origin === "public_caption"
      ? input.captionKind ?? null
      : input.origin === "manual"
        ? null
        : input.captionKind === undefined
          ? current.captionKind
          : input.captionKind;

  await prisma.source.update({
    where: { id: current.id },
    data: {
      rawTranscript: normalized || null,
      normalizedHash: nextHash,
      transcriptStatus: normalized ? "transcript_ready" : "needs_transcript",
      transcriptOrigin: normalized ? input.origin : null,
      language: input.language === undefined ? current.language : input.language,
      captionKind,
      transcriptRevision: { increment: 1 },
    },
  });

  if (normalized) {
    await persistTranscriptSegments(current.id, normalized, input.segments);
  } else {
    await prisma.transcriptSegment.deleteMany({ where: { sourceId: current.id } });
  }

  if (hashChanged) await invalidateDerivativesForSource(input.projectId, current.id);
  return { ok: true, normalized };
}
