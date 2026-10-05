import { lexicalOverlapScore } from "@/lib/originality/lexical";
import { compareEndings, compareOpenings, semanticSimilarity } from "@/lib/originality/semantic";
import { structuralOverlapScore, type FingerprintLike } from "@/lib/originality/structural";

export type OriginalityVerdict = "pass" | "warn" | "block";

export interface OriginalityFindingResult {
  category: string;
  severity: "low" | "medium" | "high";
  explanation: string;
  affectedSection: string;
  remedy?: string;
  sourceId?: string;
}

export interface OriginalityAnalysisResult {
  overallStatus: OriginalityVerdict;
  phraseOverlap: OriginalityVerdict;
  hookSimilarity: OriginalityVerdict;
  orderSimilarity: OriginalityVerdict;
  metaphorWarnings: string[];
  unsupportedClaims: string[];
  recommendedAction: string;
  exportBlocked: boolean;
  findings: OriginalityFindingResult[];
}

function toVerdict(score: number, warnAt: number, blockAt: number): OriginalityVerdict {
  if (score >= blockAt) return "block";
  if (score >= warnAt) return "warn";
  return "pass";
}

function worstVerdict(...statuses: OriginalityVerdict[]): OriginalityVerdict {
  if (statuses.includes("block")) return "block";
  if (statuses.includes("warn")) return "warn";
  return "pass";
}

function parseJsonArray(value: string | null | undefined): string[] {
  if (!value) return [];
  try {
    return JSON.parse(value) as string[];
  } catch {
    return [];
  }
}

export function mapPresentationOrderToFactIds(
  presentationOrder: string[],
  claims: Array<{ id: string; neutralClaim: string; sourceId: string }>,
  factPack: Array<{ factId: string; sourceClaimIds: string }>,
): string[] {
  const claimToFact = new Map<string, string>();
  for (const fact of factPack) {
    const claimIds = parseJsonArray(fact.sourceClaimIds);
    for (const cid of claimIds) claimToFact.set(cid, fact.factId);
  }

  return presentationOrder
    .map((cluster) => {
      const clusterLower = cluster.toLowerCase();
      for (const claim of claims) {
        if (claim.neutralClaim.toLowerCase().includes(clusterLower) || clusterLower.includes(claim.neutralClaim.slice(0, 20).toLowerCase())) {
          return claimToFact.get(claim.id) ?? null;
        }
      }
      return null;
    })
    .filter((id): id is string => Boolean(id));
}

function orderedFactSequenceSimilarity(planFactIds: string[], sourceFactIds: string[]): number {
  if (planFactIds.length === 0 || sourceFactIds.length === 0) return 0;
  const setA = planFactIds.join(",");
  const setB = sourceFactIds.join(",");
  if (setA === setB) return 1;
  let matches = 0;
  const minLen = Math.min(planFactIds.length, sourceFactIds.length);
  for (let i = 0; i < minLen; i++) {
    if (planFactIds[i] === sourceFactIds[i]) matches++;
  }
  return matches / Math.max(planFactIds.length, sourceFactIds.length);
}

export function analyzeOriginality(input: {
  script: string;
  plan: {
    openingApproach: string;
    narrativeLens: string;
    beats: Array<{ shortDescription: string; claimIds: string }>;
  } | null;
  fingerprints: Array<
    FingerprintLike & {
      sourceId: string;
      presentationOrderFactIds?: string | null;
      distinctiveMetaphorsOrPhrases?: string;
    }
  >;
  sources: Array<{ id: string; rawTranscript: string | null }>;
  factPack: Array<{ factId: string; neutralStatement: string; sourceClaimIds: string }>;
  paragraphFactIds?: string[][];
}): OriginalityAnalysisResult {
  const findings: OriginalityFindingResult[] = [];
  const metaphorWarnings: string[] = [];
  let phraseOverlap: OriginalityVerdict = "pass";
  let hookSimilarity: OriginalityVerdict = "pass";
  let orderSimilarity: OriginalityVerdict = "pass";

  const combinedSource = input.sources.map((s) => s.rawTranscript ?? "").join("\n");
  const lexical = lexicalOverlapScore(combinedSource, input.script);
  phraseOverlap = lexical.status;
  if (phraseOverlap !== "pass") {
    findings.push({
      category: "phrase_overlap",
      severity: phraseOverlap === "block" ? "high" : "medium",
      explanation: `Unusual shared phrases detected (${lexical.sharedPhrases.slice(0, 3).join("; ")})`,
      affectedSection: "Script body",
      remedy: phraseOverlap === "block" ? "Re-plan narrative structure before rewriting wording" : "Rewrite flagged sections",
    });
  }

  const openingSemantic = input.sources.reduce((max, s) => {
    if (!s.rawTranscript) return max;
    return Math.max(max, compareOpenings(input.script, s.rawTranscript));
  }, 0);
  hookSimilarity = toVerdict(openingSemantic, 0.25, 0.45);
  if (hookSimilarity !== "pass") {
    findings.push({
      category: "hook_similarity",
      severity: hookSimilarity === "block" ? "high" : "medium",
      explanation: "Opening section is semantically close to a source opening (EN/HI/Hinglish paraphrase detected).",
      affectedSection: "Opening paragraphs",
      remedy: "Re-plan with a different opening type before rewriting",
    });
  }

  const endingSemantic = input.sources.reduce((max, s) => {
    if (!s.rawTranscript) return max;
    return Math.max(max, compareEndings(input.script, s.rawTranscript));
  }, 0);
  if (endingSemantic >= 0.35) {
    findings.push({
      category: "ending_similarity",
      severity: endingSemantic >= 0.5 ? "high" : "medium",
      explanation: "Closing section resembles a source ending pattern.",
      affectedSection: "Closing paragraphs",
      remedy: endingSemantic >= 0.5 ? "Re-plan ending function" : "Rewrite closing beat",
    });
    if (endingSemantic >= 0.5) orderSimilarity = worstVerdict(orderSimilarity, "block");
    else orderSimilarity = worstVerdict(orderSimilarity, "warn");
  }

  if (input.plan) {
    const planFactOrder = input.plan.beats.flatMap((b) => parseJsonArray(b.claimIds));

    for (const fp of input.fingerprints) {
      const structural = structuralOverlapScore(
        {
          openingApproach: input.plan.openingApproach,
          narrativeLens: input.plan.narrativeLens,
          beats: input.plan.beats.map((b) => ({ shortDescription: b.shortDescription })),
        },
        fp,
      );

      const sourceFactOrder = parseJsonArray(fp.presentationOrderFactIds ?? undefined);
      const orderSim = orderedFactSequenceSimilarity(planFactOrder, sourceFactOrder);
      const structVerdict = toVerdict(structural, 0.35, 0.55);
      const orderVerdict = toVerdict(orderSim, 0.5, 0.75);
      orderSimilarity = worstVerdict(orderSimilarity, structVerdict, orderVerdict);

      if (structVerdict !== "pass" || orderVerdict !== "pass") {
        findings.push({
          category: "structural_overlap",
          severity: structVerdict === "block" || orderVerdict === "block" ? "high" : "medium",
          explanation: `Plan overlaps with source ${fp.sourceId}: lens/opening/order similarity.`,
          affectedSection: "Narrative plan",
          remedy: "Select or create a plan with different opening, lens, and fact sequence",
          sourceId: fp.sourceId,
        });
      }

      for (const device of fp.recurringDevices) {
        if (semanticSimilarity(input.script, device) > 0.4) {
          findings.push({
            category: "recurring_device",
            severity: "medium",
            explanation: `Script may reuse source rhetorical device: "${device}"`,
            affectedSection: "Script body",
            remedy: "Rewrite affected section with different rhetorical approach",
            sourceId: fp.sourceId,
          });
          hookSimilarity = worstVerdict(hookSimilarity, "warn");
        }
      }

      const metaphors = parseJsonArray(fp.distinctiveMetaphorsOrPhrases);
      for (const metaphor of metaphors) {
        if (semanticSimilarity(input.script, metaphor) > 0.35) {
          metaphorWarnings.push(metaphor);
          findings.push({
            category: "metaphor",
            severity: "medium",
            explanation: `Possible reuse of source metaphor/device: "${metaphor}"`,
            affectedSection: "Script body",
            remedy: "Replace with original analogy",
            sourceId: fp.sourceId,
          });
        }
      }
    }
  }

  for (const fp of input.fingerprints) {
    const source = input.sources.find((s) => s.id === fp.sourceId);
    if (!source?.rawTranscript) continue;
    const lensSim = semanticSimilarity(input.script.slice(0, 800), fp.dominantNarrativeLens);
    if (lensSim > 0.5) {
      hookSimilarity = worstVerdict(hookSimilarity, "warn");
    }
  }

  const overallStatus = worstVerdict(phraseOverlap, hookSimilarity, orderSimilarity);
  const exportBlocked = overallStatus === "block";

  let recommendedAction =
    "Pass — editorial originality check only, not legal clearance or copyright safety.";
  if (overallStatus === "block") {
    recommendedAction =
      "BLOCK — create a new narrative plan with different opening, lens, and fact sequence before rewriting wording.";
  } else if (overallStatus === "warn") {
    recommendedAction = "WARN — targeted rewrite of flagged sections recommended.";
  }

  return {
    overallStatus,
    phraseOverlap,
    hookSimilarity,
    orderSimilarity,
    metaphorWarnings,
    unsupportedClaims: [],
    recommendedAction,
    exportBlocked,
    findings,
  };
}
