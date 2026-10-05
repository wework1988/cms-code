import { describe, expect, it } from "vitest";
import { mergeClaimsToFactPack } from "@/lib/pipeline/merge-facts";
import type { Claim } from "@/lib/schemas";

const baseClaim = (overrides: Partial<Claim>): Claim => ({
  id: "c1",
  sourceId: "s1",
  neutralClaim: "Test claim",
  claimType: "event",
  supportExcerpt: "excerpt",
  sourceCertainty: "explicit",
  storyRelevance: "high",
  requiredByUser: false,
  ...overrides,
});

describe("mergeClaimsToFactPack", () => {
  it("merges duplicate neutral claims and preserves traceability", () => {
    const facts = mergeClaimsToFactPack([
      baseClaim({ id: "c1", sourceId: "s1", neutralClaim: "Battle happened in 1757" }),
      baseClaim({ id: "c2", sourceId: "s2", neutralClaim: "battle happened in 1757" }),
    ]);

    expect(facts).toHaveLength(1);
    expect(facts[0].sourceClaimIds).toEqual(["c1", "c2"]);
    expect(facts[0].sourceCount).toBe(2);
  });

  it("never drops user-pinned claims during merge grouping", () => {
    const facts = mergeClaimsToFactPack([
      baseClaim({ id: "c1", neutralClaim: "Pinned fact", requiredByUser: true }),
    ]);
    expect(facts[0].userPinned).toBe(true);
  });
});
