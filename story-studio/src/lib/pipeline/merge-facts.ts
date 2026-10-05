import type { Claim, FactPackItem } from "@/lib/schemas";
import { assignFactIds, validateSourceClaimIds } from "@/lib/pipeline/validate-ids";

function normalizeClaimText(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function mergeClaimsToFactPack(claims: Claim[]): FactPackItem[] {
  const active = claims.filter((c) => !("disabled" in c) || !(c as Claim & { disabled?: boolean }).disabled);
  const groups = new Map<string, Claim[]>();

  for (const claim of active) {
    const key = normalizeClaimText(claim.neutralClaim);
    const bucket = groups.get(key) ?? [];
    bucket.push(claim);
    groups.set(key, bucket);
  }

  const facts: Omit<FactPackItem, "factId">[] = [];

  for (const group of groups.values()) {
    const pinned = group.some((c) => c.requiredByUser);
    const relevanceRank = { high: 3, medium: 2, low: 1 } as const;
    const best = [...group].sort(
      (a, b) => relevanceRank[b.storyRelevance] - relevanceRank[a.storyRelevance],
    )[0];

    facts.push({
      neutralStatement: best.neutralClaim,
      sourceClaimIds: group.map((c) => c.id),
      sourceCount: new Set(group.map((c) => c.sourceId)).size,
      peoplePlacesDatesNumbers: best.peoplePlacesDatesNumbers,
      storyImportance: best.storyRelevance,
      userPinned: pinned,
      editorNotes: undefined,
    });
  }

  const sorted = facts.sort((a, b) => {
    const rank = { high: 3, medium: 2, low: 1 } as const;
    return rank[b.storyImportance] - rank[a.storyImportance];
  });

  return assignFactIds(sorted);
}

export interface PreservedFact {
  id: string;
  factId: string;
  neutralStatement: string;
  sourceClaimIds: string;
  sourceCount: number;
  peoplePlacesDatesNumbers: string | null;
  storyImportance: string;
  userPinned: boolean;
  userEdited: boolean;
  disabled: boolean;
  editorNotes: string | null;
}

/** Merge new facts while preserving user-pinned, user-edited, and disabled states. */
export function mergeWithPreservedFacts(
  newFacts: FactPackItem[],
  existing: PreservedFact[],
  validClaimIds: Set<string>,
): Array<{
  factId: string;
  neutralStatement: string;
  sourceClaimIds: string[];
  sourceCount: number;
  peoplePlacesDatesNumbers?: string;
  storyImportance: "high" | "medium" | "low";
  userPinned: boolean;
  userEdited: boolean;
  disabled: boolean;
  editorNotes?: string;
}> {
  const preserved = existing.filter((f) => f.userPinned || f.userEdited);
  const preservedKeys = new Set(preserved.map((f) => normalizeClaimText(f.neutralStatement)));
  const preservedFactIds = new Set(preserved.map((f) => f.factId));

  const merged = newFacts
    .filter((f) => !preservedKeys.has(normalizeClaimText(f.neutralStatement)))
    .filter((f) => !preservedFactIds.has(f.factId))
    .map((f) => ({
      factId: f.factId,
      neutralStatement: f.neutralStatement,
      sourceClaimIds: validateSourceClaimIds(f.sourceClaimIds, validClaimIds),
      sourceCount: f.sourceCount,
      peoplePlacesDatesNumbers: f.peoplePlacesDatesNumbers,
      storyImportance: f.storyImportance,
      userPinned: f.userPinned,
      userEdited: false,
      disabled: false,
      editorNotes: f.editorNotes,
    }));

  const preservedMapped = preserved.map((f) => ({
    factId: f.factId,
    neutralStatement: f.neutralStatement,
    sourceClaimIds: validateSourceClaimIds(JSON.parse(f.sourceClaimIds) as string[], validClaimIds),
    sourceCount: f.sourceCount,
    peoplePlacesDatesNumbers: f.peoplePlacesDatesNumbers ?? undefined,
    storyImportance: f.storyImportance as "high" | "medium" | "low",
    userPinned: f.userPinned,
    userEdited: f.userEdited,
    disabled: f.disabled,
    editorNotes: f.editorNotes ?? undefined,
  }));

  return [...preservedMapped, ...merged];
}
