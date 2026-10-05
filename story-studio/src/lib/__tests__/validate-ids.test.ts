import { describe, expect, it } from "vitest";
import { sanitizeClaimsFromLlm, validateFactIds } from "@/lib/pipeline/validate-ids";

describe("server-side ID validation", () => {
  it("assigns server-side claim IDs and ignores LLM sourceId", () => {
    const claims = sanitizeClaimsFromLlm(
      [
        {
          neutralClaim: "Test claim",
          claimType: "event",
          supportExcerpt: "excerpt",
          sourceCertainty: "explicit",
          storyRelevance: "high",
          requiredByUser: false,
        },
      ],
      "real-source-id",
    );

    expect(claims[0].sourceId).toBe("real-source-id");
    expect(claims[0].id).toMatch(/^real-source-id-claim-/);
  });

  it("filters invalid fact IDs", () => {
    const valid = new Set(["fact-001", "fact-002"]);
    expect(validateFactIds(["fact-001", "fake-fact"], valid)).toEqual(["fact-001"]);
  });
});
