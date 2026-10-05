import type { Claim, FactPackItem } from "@/lib/schemas";

/** Server assigns all claim IDs — never trust LLM-returned IDs or sourceIds. */
export function sanitizeClaimsFromLlm(
  rawClaims: Omit<Claim, "id" | "sourceId">[],
  sourceId: string,
): Claim[] {
  return rawClaims.map((claim, index) => ({
    ...claim,
    id: `${sourceId}-claim-${String(index + 1).padStart(2, "0")}`,
    sourceId,
    requiredByUser: claim.requiredByUser ?? false,
  }));
}

export function validateFactIds(factIds: string[], validFactIds: Set<string>): string[] {
  const validated = factIds.filter((id) => validFactIds.has(id));
  if (validated.length === 0 && factIds.length > 0) {
    throw new Error(`Invalid fact IDs from model: ${factIds.join(", ")}`);
  }
  return validated;
}

export function validateBeatFactIds<T extends { claimIds: string[] }>(
  beats: T[],
  validFactIds: Set<string>,
): T[] {
  return beats.map((beat) => ({
    ...beat,
    claimIds: beat.claimIds.filter((id) => {
      if (!validFactIds.has(id)) {
        console.warn(`Dropping invalid fact ID from beat: ${id}`);
        return false;
      }
      return true;
    }),
  }));
}

export function assignFactIds(facts: Omit<FactPackItem, "factId">[], startIndex = 1): FactPackItem[] {
  return facts.map((fact, i) => ({
    ...fact,
    factId: `fact-${String(startIndex + i).padStart(3, "0")}`,
  }));
}

export function validateSourceClaimIds(
  sourceClaimIds: string[],
  validClaimIds: Set<string>,
): string[] {
  return sourceClaimIds.filter((id) => validClaimIds.has(id));
}
