import type { NarrativeTreatment } from "@/lib/schemas";

export function buildFallbackTreatments(
  facts: Array<{ factId: string; neutralStatement: string }>,
  count = 1,
): NarrativeTreatment[] {
  if (facts.length === 0) {
    return [
      {
        centralQuestion: "What is the core story here?",
        openingApproach: "Open with a direct question",
        narrativeLens: "explanatory",
        diffExplanation: "Local fallback plan — LLM narrative response was invalid.",
        beats: [
          {
            beatNumber: 1,
            purpose: "hook",
            shortDescription: "Introduce the central question",
            claimIds: [],
            narrativeRole: "opening",
          },
        ],
      },
    ];
  }

  const lenses = ["timeline", "institution", "human-consequence"];
  const openings = ["Question-led opening", "Consequence-first opening", "Context-first opening"];

  return Array.from({ length: Math.min(count, 3) }, (_, index) => {
    const beats = facts.map((fact, i) => ({
      beatNumber: i + 1,
      purpose: i === 0 ? "hook" : i === facts.length - 1 ? "close" : "develop",
      shortDescription: fact.neutralStatement.slice(0, 140),
      claimIds: [fact.factId],
      narrativeRole:
        i === 0 ? "opening" : i === facts.length - 1 ? "closing" : "development",
      expectedDurationSeconds: 45,
    }));

    return {
      centralQuestion: `इन तथ्यों से कौन-सी मूल कहानी बनती है? (Treatment ${index + 1})`,
      openingApproach: openings[index] ?? openings[0],
      narrativeLens: lenses[index] ?? lenses[0],
      diffExplanation: "Local fallback plan — generated from Fact Bank when LLM response was invalid.",
      beats,
    };
  });
}
