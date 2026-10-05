import { describe, expect, it } from "vitest";
import { analyzeOriginality } from "@/lib/originality/analyzer";

const fingerprint = {
  sourceId: "src-1",
  openingType: "dramatic battle hook",
  openingFunction: "high_stakes",
  presentationOrder: ["plassey", "charter", "monopoly"],
  presentationOrderFactIds: '["fact-001","fact-002","fact-003"]',
  dominantNarrativeLens: "military chronology",
  turningPointType: "battle",
  endingFunction: "legacy question",
  recurringDevices: ["countdown timer"],
  distinctiveMetaphorsOrPhrases: '["company army seized control"]',
};

describe("all-source structural comparison", () => {
  it("compares plan and script against every fingerprint", () => {
    const sourceText =
      "The dramatic battle hook opens with Plassey. The company army seized control through military chronology and a countdown timer.";
    const script =
      "The dramatic battle hook opens with Plassey. The company army seized control through military chronology and a countdown timer. Extra framing.";

    const result = analyzeOriginality({
      script,
      plan: {
        openingApproach: "dramatic battle hook",
        narrativeLens: "military chronology",
        beats: [
          { shortDescription: "plassey battle", claimIds: '["fact-001"]' },
          { shortDescription: "charter context", claimIds: '["fact-002"]' },
          { shortDescription: "monopoly build", claimIds: '["fact-003"]' },
        ],
      },
      fingerprints: [fingerprint, { ...fingerprint, sourceId: "src-2" }],
      sources: [
        { id: "src-1", rawTranscript: sourceText },
        { id: "src-2", rawTranscript: sourceText },
      ],
      factPack: [
        { factId: "fact-001", neutralStatement: "Plassey 1757", sourceClaimIds: "[]" },
        { factId: "fact-002", neutralStatement: "Charter 1600", sourceClaimIds: "[]" },
        { factId: "fact-003", neutralStatement: "Monopoly aim", sourceClaimIds: "[]" },
      ],
    });

    expect(["warn", "block"]).toContain(result.overallStatus);
    expect(result.findings.length).toBeGreaterThan(0);
  });

  it("passes when structure is intentionally different", () => {
    const result = analyzeOriginality({
      script: "एक अनुमति पत्र से शुरू होने वाली अलग institutional कहानी।",
      plan: {
        openingApproach: "institutional comparison",
        narrativeLens: "system analysis",
        beats: [{ shortDescription: "modern corporation frame", claimIds: '["fact-004"]' }],
      },
      fingerprints: [fingerprint],
      sources: [{ id: "src-1", rawTranscript: "Battle of Plassey 1757 dramatic opening." }],
      factPack: [{ factId: "fact-004", neutralStatement: "Institutional drift", sourceClaimIds: "[]" }],
    });

    expect(result.overallStatus).toBe("pass");
  });
});
