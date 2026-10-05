import { describe, expect, it } from "vitest";
import { buildFallbackTreatments } from "@/lib/pipeline/fallback-plans";
import { narrativePlansResponseSchema } from "@/lib/schemas";
import { normalizeNarrativePlansPayload, parseNarrativePlansLenient } from "@/lib/pipeline/normalize-llm";

describe("narrative plan fallbacks", () => {
  it("builds treatments from fact pack", () => {
    const treatments = buildFallbackTreatments([
      { factId: "fact-1", neutralStatement: "East India Company was founded in 1600." },
      { factId: "fact-2", neutralStatement: "It received a royal charter." },
    ]);

    expect(treatments).toHaveLength(1);
    expect(treatments[0].beats.length).toBe(2);
    expect(treatments[0].beats[0].claimIds).toEqual(["fact-1"]);
  });

  it("parses string beat arrays like common LLM responses", () => {
    const parsed = parseNarrativePlansLenient({
      treatments: [
        {
          centralQuestion: "How did the official narrative shift?",
          beats: [
            "Hook: Pose the central question",
            "Context: Explain the institution",
            "Turn: Introduce the contradiction",
            "Close: Leave the case open",
          ],
        },
      ],
    });

    expect(parsed.treatments[0].openingApproach).toBe("Fresh contextual opening");
    expect(parsed.treatments[0].beats[0].purpose).toBe("hook");
    expect(parsed.treatments[0].beats[0].shortDescription).toContain("Pose the central question");
  });

  it("fills missing treatment fields from partial LLM payloads", () => {
    const parsed = parseNarrativePlansLenient({
      treatments: [
        {
          centralQuestion: "Why did it matter?",
          beats: [{ shortDescription: "Open", claimIds: ["f1"] }],
        },
      ],
    });

    expect(parsed.treatments[0].openingApproach).toBe("Fresh contextual opening");
    expect(parsed.treatments[0].narrativeLens).toBe("explanatory");
    expect(parsed.treatments[0].beats[0].claimIds).toEqual(["f1"]);
  });

  it("normalizes snake_case and single-treatment payloads", () => {
    const parsed = narrativePlansResponseSchema.parse(
      normalizeNarrativePlansPayload({
        central_question: "Why did it matter?",
        opening_approach: "Question hook",
        narrative_lens: "timeline",
        diffExplanation: "Different order",
        beats: [{ purpose: "hook", short_description: "Open", claim_ids: ["f1"] }],
      }),
    );

    expect(parsed.treatments).toHaveLength(1);
    expect(parsed.treatments[0].centralQuestion).toBe("Why did it matter?");
    expect(parsed.treatments[0].beats[0].claimIds).toEqual(["f1"]);
  });
});
