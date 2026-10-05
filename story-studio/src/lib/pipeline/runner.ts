import type { PromptProfile } from "@prisma/client";
import { prisma } from "@/lib/db";
import { getLLMProvider, isLLMConfigured } from "@/lib/llm/provider";
import { analyzeOriginality, mapPresentationOrderToFactIds } from "@/lib/originality/analyzer";
import { structuralOverlapScore } from "@/lib/originality/structural";
import { buildNarrationStyleContext, buildPromptProfileContext, SYSTEM_ISOLATION_RULES } from "@/lib/prompts/profile";
import {
  buildClaimExtractorPrompt,
  buildFactPackMergePrompt,
  buildFingerprintPrompt,
  buildNarrativePlannerPrompt,
  CLAIM_EXTRACTOR_SYSTEM,
  FINGERPRINT_SYSTEM,
  NARRATIVE_PLANNER_SYSTEM,
} from "@/lib/prompts";
import { buildFallbackTreatments } from "@/lib/pipeline/fallback-plans";
import { parseNarrativePlansLenient } from "@/lib/pipeline/normalize-llm";
import { parseJsonSafe } from "@/lib/llm/json";
import {
  claimsResponseSchema,
  factPackResponseSchema,
  fingerprintResponseSchema,
  type Claim,
} from "@/lib/schemas";
import { hashTranscript, normalizeTranscript } from "@/lib/transcript/normalize";
import { assertAllSourcesHaveTranscripts } from "@/lib/pipeline/source-readiness";
import { normalizeYouTubeUrl } from "@/lib/youtube/normalize";
import { loadDemoFixture } from "@/lib/fixtures/demo";
import { mergeClaimsToFactPack, mergeWithPreservedFacts } from "@/lib/pipeline/merge-facts";
import { persistTranscriptSegments } from "@/lib/pipeline/segments";
import {
  sanitizeClaimsFromLlm,
  validateBeatFactIds,
  validateFactIds,
} from "@/lib/pipeline/validate-ids";
import {
  assembleNarration,
  countCharacters,
  formatLengthMissMessage,
  isInLengthRange,
  lengthRange,
  resolveTargetCharCount,
} from "@/lib/narration/count";
import { generateNarration, type NarrationDraft } from "@/lib/narration/engine";
import { estimateDurationSeconds } from "@/lib/utils";
import { resolveCtaConfig } from "@/lib/cta/config";
import { legacyGoalToNarrativeApproach } from "@/lib/story-settings/options";

export type PipelineStage =
  | "normalize_sources"
  | "extract_claims"
  | "merge_fact_pack"
  | "generate_plans"
  | "generate_script"
  | "originality_qa";

const STAGE_TO_STATUS: Record<string, string> = {
  normalize_sources: "sources_ready",
  extract_claims: "claims_ready",
  merge_fact_pack: "fact_pack_ready",
  generate_plans: "narrative_plan_ready",
  generate_script: "script_generated",
  originality_qa: "originality_review_ready",
};

const MAX_REPLAN_LOOPS = 2;
const RUN_STALE_AFTER_MS = Math.max(300_000, Number(process.env.PIPELINE_RUN_STALE_MS ?? 1_200_000));

export async function runPipelineStage(projectId: string, stage: PipelineStage): Promise<void> {
  const staleBefore = new Date(Date.now() - RUN_STALE_AFTER_MS);
  await prisma.pipelineRun.updateMany({
    where: {
      projectId,
      status: "running",
      startedAt: { lt: staleBefore },
    },
    data: {
      status: "failed",
      errorMessage: "Run marked failed automatically because it exceeded the maximum runtime.",
      finishedAt: new Date(),
    },
  });

  const activeRun = await prisma.pipelineRun.findFirst({
    where: { projectId, status: "running" },
    select: { id: true, stage: true, startedAt: true },
  });
  if (activeRun) {
    throw new Error(
      `A ${activeRun.stage} run is already in progress for this project. Please wait for it to finish.`,
    );
  }

  const run = await prisma.pipelineRun.create({
    data: { projectId, stage, status: "running" },
  });

  try {
    let scriptResult: GenerateScriptResult | null = null;
    switch (stage) {
      case "normalize_sources":
        await normalizeSources(projectId);
        break;
      case "extract_claims":
        await extractClaims(projectId, run.id);
        break;
      case "merge_fact_pack":
        await mergeFactPack(projectId, run.id);
        break;
      case "generate_plans":
        await generatePlans(projectId, true, run.id);
        break;
      case "generate_script":
        scriptResult = await generateScript(projectId, undefined, run.id);
        break;
      case "originality_qa":
        await runOriginalityQA(projectId);
        break;
    }

    await prisma.pipelineRun.update({
      where: { id: run.id },
      data: { status: "complete", finishedAt: new Date() },
    });

    const lengthMiss = scriptResult && !scriptResult.inRange;
    await prisma.project.update({
      where: { id: projectId },
      data: {
        status: STAGE_TO_STATUS[stage] ?? "draft",
        ...(stage === "generate_script" && scriptResult
          ? {
              errorMessage: lengthMiss
                ? scriptResult.message ?? formatLengthMissMessage(scriptResult.charCount, scriptResult.target)
                : null,
              lengthStatus: scriptResult.status,
            }
          : stage === "originality_qa"
            ? {}
            : { errorMessage: null }),
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown pipeline error";
    const staged = `${stage}: ${message}`;
    await prisma.pipelineRun.update({
      where: { id: run.id },
      data: { status: "failed", errorMessage: staged, finishedAt: new Date() },
    });
    await prisma.project.update({
      where: { id: projectId },
      data: { errorMessage: staged },
    });
    throw error;
  }
}

export async function runFullPipeline(projectId: string, autoSelectPlan = true): Promise<void> {
  await runPipelineStage(projectId, "normalize_sources");
  await assertAllSourcesHaveTranscripts(projectId);
  await runPipelineStage(projectId, "extract_claims");
  await runPipelineStage(projectId, "merge_fact_pack");
  await runPipelineStage(projectId, "generate_plans");

  if (autoSelectPlan) {
    await autoSelectLowestOverlapPlan(projectId);
  }

  await runPipelineStage(projectId, "generate_script");

  let loops = 0;
  while (loops < MAX_REPLAN_LOOPS) {
    await runOriginalityQA(projectId);
    const report = await prisma.originalityReport.findFirst({
      where: { projectId },
      orderBy: { createdAt: "desc" },
    });
    if (report?.overallStatus !== "block") break;

    loops++;
    await generatePlans(projectId);
    await autoSelectLowestOverlapPlan(projectId);
    await runPipelineStage(projectId, "generate_script");
  }

  const project = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });
  const script = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
  });
  const range = lengthRange(resolveTargetCharCount(project.targetCharCount));
  const actual = countCharacters(script?.content ?? "");
  const inRange = isInLengthRange(actual, range);

  await prisma.project.update({
    where: { id: projectId },
    data: inRange
      ? { status: "complete", errorMessage: null, lengthStatus: "ready" }
      : {
          status: "script_generated",
          errorMessage: formatLengthMissMessage(actual, range.target),
          lengthStatus: "target_not_reached",
        },
  });
}

export async function regenerateFromSavedSettings(
  projectId: string,
  scope: "script_only" | "plan_and_script" = "script_only",
): Promise<void> {
  if (scope === "plan_and_script") {
    await runPipelineStage(projectId, "generate_plans");
    await autoSelectLowestOverlapPlan(projectId);
  } else {
    const selected = await prisma.narrativePlan.findFirst({
      where: { projectId, isSelected: true },
      select: { id: true },
    });
    if (!selected) {
      await autoSelectLowestOverlapPlan(projectId);
    }
  }

  await runPipelineStage(projectId, "generate_script");
  await runPipelineStage(projectId, "originality_qa");

  const project = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });
  const script = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
  });
  const range = lengthRange(resolveTargetCharCount(project.targetCharCount));
  const actual = countCharacters(script?.content ?? "");
  const inRange = isInLengthRange(actual, range);

  await prisma.project.update({
    where: { id: projectId },
    data: inRange
      ? { status: "complete", errorMessage: null, lengthStatus: "ready" }
      : {
          status: "script_generated",
          errorMessage: formatLengthMissMessage(actual, range.target),
          lengthStatus: "target_not_reached",
        },
  });
}

async function normalizeSources(projectId: string): Promise<void> {
  const sources = await prisma.source.findMany({ where: { projectId }, orderBy: { createdAt: "asc" } });

  for (const source of sources) {
    if (source.rawTranscript?.trim()) {
      const normalized = normalizeTranscript(source.rawTranscript);
      await prisma.source.update({
        where: { id: source.id },
        data: {
          rawTranscript: normalized,
          normalizedHash: hashTranscript(normalized),
          transcriptStatus: "transcript_ready",
        },
      });
      await persistTranscriptSegments(source.id, normalized);
    } else {
      await prisma.source.update({
        where: { id: source.id },
        data: { transcriptStatus: "needs_transcript" },
      });
    }
  }
}

async function seedDemoClaimsAndFingerprints(
  projectId: string,
  sources: Array<{ id: string }>,
): Promise<void> {
  const sourceIds = sources.map((s) => s.id) as [string, string];
  const fixture = loadDemoFixture(sourceIds);

  await prisma.claim.deleteMany({ where: { projectId } });
  await prisma.narrativeFingerprint.deleteMany({ where: { projectId } });

  for (const claim of fixture.claims) {
    await prisma.claim.create({
      data: {
        id: claim.id,
        projectId,
        sourceId: claim.sourceId,
        neutralClaim: claim.neutralClaim,
        claimType: claim.claimType,
        peoplePlacesDatesNumbers: claim.peoplePlacesDatesNumbers,
        timestampStart: claim.timestampStart ?? null,
        timestampEnd: claim.timestampEnd ?? null,
        supportExcerpt: claim.supportExcerpt,
        sourceCertainty: claim.sourceCertainty,
        storyRelevance: claim.storyRelevance,
        requiredByUser: claim.requiredByUser,
      },
    });
  }

  for (const fp of fixture.fingerprints) {
    await prisma.narrativeFingerprint.create({
      data: {
        projectId,
        sourceId: fp.sourceId,
        openingType: fp.openingType,
        openingFunction: fp.openingFunction,
        presentationOrder: JSON.stringify(fp.presentationOrder),
        presentationOrderFactIds: JSON.stringify(fp.presentationOrderFactIds ?? []),
        dominantNarrativeLens: fp.dominantNarrativeLens,
        turningPointType: fp.turningPointType,
        recurringDevices: JSON.stringify(fp.recurringDevices),
        distinctiveMetaphorsOrPhrases: JSON.stringify(fp.distinctiveMetaphorsOrPhrases),
        endingFunction: fp.endingFunction,
        titleAndThumbnailPattern: fp.titleAndThumbnailPattern,
      },
    });
  }
}

async function extractClaims(projectId: string, runId?: string): Promise<void> {
  const project = await prisma.project.findUniqueOrThrow({
    where: { id: projectId },
    include: { sources: { orderBy: { createdAt: "asc" } } },
  });

  if (!project.isDemo) {
    await assertAllSourcesHaveTranscripts(projectId);
  }

  if (project.isDemo) {
    await seedDemoClaimsAndFingerprints(projectId, project.sources);
    return;
  }

  if (!isLLMConfigured()) {
    throw new Error("LLM API key required for claim extraction. Configure DEEPSEEK_API_KEY or OPENAI_API_KEY.");
  }

  const llm = getLLMProvider();
  await prisma.claim.deleteMany({ where: { projectId } });
  await prisma.narrativeFingerprint.deleteMany({ where: { projectId } });

  for (const source of project.sources) {
    if (!source.rawTranscript) continue;

    const claimsResult = await llm.generateStructured(
      buildClaimExtractorPrompt(source.id, source.rawTranscript),
      claimsResponseSchema,
      CLAIM_EXTRACTOR_SYSTEM,
      { trace: { runId, stage: "extract_claims", callId: `claims:${source.id}`, attempt: 1 } },
    );

    const sanitized = sanitizeClaimsFromLlm(
      claimsResult.claims.map(({ id, sourceId, ...rest }) => {
        void id;
        void sourceId;
        return rest;
      }),
      source.id,
    );

    for (const claim of sanitized) {
      await prisma.claim.create({
        data: {
          id: claim.id,
          projectId,
          sourceId: source.id,
          neutralClaim: claim.neutralClaim,
          claimType: claim.claimType,
          peoplePlacesDatesNumbers: claim.peoplePlacesDatesNumbers,
          timestampStart: claim.timestampStart ?? null,
          timestampEnd: claim.timestampEnd ?? null,
          supportExcerpt: claim.supportExcerpt,
          sourceCertainty: claim.sourceCertainty,
          storyRelevance: claim.storyRelevance,
          requiredByUser: claim.requiredByUser,
        },
      });
    }

    let fpRaw;
    try {
      fpRaw = await llm.generateStructured(
        buildFingerprintPrompt(source.rawTranscript),
        fingerprintResponseSchema,
        FINGERPRINT_SYSTEM,
        { trace: { runId, stage: "extract_claims", callId: `fingerprint:${source.id}`, attempt: 1 } },
      );
    } catch (error) {
      console.warn("Fingerprint LLM failed, using safe defaults:", error);
      fpRaw = fingerprintResponseSchema.parse({});
    }

    const claims = await prisma.claim.findMany({ where: { sourceId: source.id } });
    const factPackPreview = mergeClaimsToFactPack(
      claims.map((c) => ({
        ...c,
        claimType: c.claimType as Claim["claimType"],
        sourceCertainty: c.sourceCertainty as Claim["sourceCertainty"],
        storyRelevance: c.storyRelevance as Claim["storyRelevance"],
        peoplePlacesDatesNumbers: c.peoplePlacesDatesNumbers ?? undefined,
      })),
    );

    const presentationOrderFactIds = mapPresentationOrderToFactIds(
      fpRaw.presentationOrder,
      claims.map((c) => ({ id: c.id, neutralClaim: c.neutralClaim, sourceId: c.sourceId })),
      factPackPreview.map((f) => ({ factId: f.factId, sourceClaimIds: JSON.stringify(f.sourceClaimIds) })),
    );

    await prisma.narrativeFingerprint.create({
      data: {
        projectId,
        sourceId: source.id,
        openingType: fpRaw.openingType,
        openingFunction: fpRaw.openingFunction,
        presentationOrder: JSON.stringify(fpRaw.presentationOrder),
        presentationOrderFactIds: JSON.stringify(presentationOrderFactIds),
        dominantNarrativeLens: fpRaw.dominantNarrativeLens,
        turningPointType: fpRaw.turningPointType,
        recurringDevices: JSON.stringify(fpRaw.recurringDevices),
        distinctiveMetaphorsOrPhrases: JSON.stringify(fpRaw.distinctiveMetaphorsOrPhrases),
        endingFunction: fpRaw.endingFunction,
        titleAndThumbnailPattern: fpRaw.titleAndThumbnailPattern,
      },
    });

    await prisma.source.update({
      where: { id: source.id },
      data: { transcriptStatus: "extraction_complete" },
    });
  }
}

async function mergeFactPack(projectId: string, runId?: string): Promise<void> {
  const claims = await prisma.claim.findMany({ where: { projectId, disabled: false } });
  const existing = await prisma.factPackItem.findMany({ where: { projectId } });
  const validClaimIds = new Set(claims.map((c) => c.id));

  const claimObjects: Claim[] = claims.map((c) => ({
    id: c.id,
    sourceId: c.sourceId,
    neutralClaim: c.neutralClaim,
    claimType: c.claimType as Claim["claimType"],
    peoplePlacesDatesNumbers: c.peoplePlacesDatesNumbers ?? undefined,
    timestampStart: c.timestampStart,
    timestampEnd: c.timestampEnd,
    supportExcerpt: c.supportExcerpt,
    sourceCertainty: c.sourceCertainty as Claim["sourceCertainty"],
    storyRelevance: c.storyRelevance as Claim["storyRelevance"],
    requiredByUser: c.requiredByUser,
  }));

  let facts = mergeClaimsToFactPack(claimObjects);

  if (isLLMConfigured() && claims.length > 0 && facts.length <= 25) {
    try {
      const llm = getLLMProvider();
      const merged = await llm.generateStructured(
        buildFactPackMergePrompt(facts),
        factPackResponseSchema,
        "Merge duplicate facts. Never discard userPinned facts. Return factId values exactly as provided.",
        { maxTokens: 4096, trace: { runId, stage: "merge_fact_pack", callId: "fact-pack-merge", attempt: 1 } },
      );
      if (merged.facts.length > 0) {
        const validFactIds = new Set(facts.map((f) => f.factId));
        facts = merged.facts.map((f, i) => ({
          ...f,
          factId: validFactIds.has(f.factId) ? f.factId : facts[i]?.factId ?? f.factId,
          sourceClaimIds: f.sourceClaimIds.filter((id) => validClaimIds.has(id)),
        }));
      }
    } catch (error) {
      console.warn("Fact pack LLM merge failed, using deterministic merge:", error);
    }
  }

  const mergedFacts = mergeWithPreservedFacts(facts, existing, validClaimIds);

  await prisma.factPackItem.deleteMany({
    where: {
      projectId,
      userPinned: false,
      userEdited: false,
    },
  });

  const remaining = await prisma.factPackItem.findMany({ where: { projectId } });
  const remainingIds = new Set(remaining.map((f) => f.factId));

  for (const fact of mergedFacts) {
    if (remainingIds.has(fact.factId)) continue;
    await prisma.factPackItem.create({
      data: {
        projectId,
        factId: fact.factId,
        neutralStatement: fact.neutralStatement,
        sourceClaimIds: JSON.stringify(fact.sourceClaimIds),
        sourceCount: fact.sourceCount,
        peoplePlacesDatesNumbers: fact.peoplePlacesDatesNumbers,
        storyImportance: fact.storyImportance,
        userPinned: fact.userPinned,
        userEdited: fact.userEdited,
        disabled: fact.disabled,
        editorNotes: fact.editorNotes,
      },
    });
  }
}

async function generatePlans(projectId: string, preserveEdited = true, runId?: string): Promise<void> {
  const project = await prisma.project.findUniqueOrThrow({
    where: { id: projectId },
    include: { promptProfile: true },
  });
  const facts = await prisma.factPackItem.findMany({ where: { projectId, disabled: false } });
  const fingerprints = await prisma.narrativeFingerprint.findMany({ where: { projectId } });
  const validFactIds = new Set(facts.map((f) => f.factId));

  if (project.isDemo) {
    const sources = await prisma.source.findMany({ where: { projectId }, orderBy: { createdAt: "asc" } });
    const fixture = loadDemoFixture(sources.map((s) => s.id) as [string, string]);
    if (!preserveEdited) {
      await prisma.narrativePlan.deleteMany({ where: { projectId, isEdited: false } });
    } else {
      await prisma.narrativePlan.deleteMany({ where: { projectId, isEdited: false } });
    }
    for (let i = 0; i < fixture.treatments.length; i++) {
      const t = fixture.treatments[i];
      const plan = await prisma.narrativePlan.create({
        data: {
          projectId,
          treatmentIndex: i,
          centralQuestion: t.centralQuestion,
          openingApproach: t.openingApproach,
          narrativeLens: t.narrativeLens,
          diffExplanation: t.diffExplanation,
          isRecommended: i === 0,
        },
      });
      for (const beat of t.beats) {
        await prisma.narrativeBeat.create({
          data: {
            planId: plan.id,
            beatNumber: beat.beatNumber,
            purpose: beat.purpose,
            shortDescription: beat.shortDescription,
            claimIds: JSON.stringify(validateFactIds(beat.claimIds, validFactIds)),
            narrativeRole: beat.narrativeRole,
            proposedVisualIdea: beat.proposedVisualIdea,
            expectedDurationSeconds: beat.expectedDurationSeconds,
          },
        });
      }
    }
    return;
  }

  const treatments = await resolveNarrativeTreatments(project, facts, fingerprints, validFactIds, runId);
  await persistNarrativePlans(projectId, treatments, validFactIds);
}

function selectFactsForPlanning(
  facts: Array<{
    factId: string;
    neutralStatement: string;
    storyImportance: string;
    sourceClaimIds?: string;
    sourceCount?: number;
  }>,
  limit = 45,
) {
  const rank = { high: 3, medium: 2, low: 1 } as const;
  const sorted = [...facts].sort((a, b) => {
    const ra = rank[a.storyImportance as keyof typeof rank] ?? 1;
    const rb = rank[b.storyImportance as keyof typeof rank] ?? 1;
    const ca = a.sourceCount ?? 0;
    const cb = b.sourceCount ?? 0;
    return rb - ra || cb - ca;
  });

  const selected: typeof sorted = [];
  const seenClaims = new Set<string>();
  for (const fact of sorted) {
    if (selected.length >= limit) break;
    const ids = fact.sourceClaimIds ? (JSON.parse(fact.sourceClaimIds) as string[]) : [];
    const addsCoverage = ids.some((id) => !seenClaims.has(id));
    if (addsCoverage || selected.length < Math.min(limit, 15)) {
      selected.push(fact);
      for (const id of ids) seenClaims.add(id);
    }
  }
  if (selected.length < Math.min(sorted.length, limit)) {
    for (const fact of sorted) {
      if (selected.length >= limit) break;
      if (selected.some((s) => s.factId === fact.factId)) continue;
      selected.push(fact);
    }
  }
  return selected;
}

async function resolveNarrativeTreatments(
  project: {
    title: string;
    topic: string | null;
    outputLanguage: string;
    audience: string | null;
    genre: string | null;
    tone: string | null;
    mustCoverPoints: string | null;
    narrativeGoal: string | null;
    openingHook: string | null;
    openingHookCustom: string | null;
    narrativeApproachCustom: string | null;
    promptProfile: PromptProfile | null;
  },
  facts: Array<{ factId: string; neutralStatement: string; storyImportance: string }>,
  fingerprints: Array<{
    openingType: string;
    dominantNarrativeLens: string;
    endingFunction: string;
    presentationOrderFactIds: string | null;
  }>,
  validFactIds: Set<string>,
  runId?: string,
) {
  const approach = legacyGoalToNarrativeApproach(project.narrativeGoal);
  const treatmentCount = approach === "auto" ? 3 : 1;
  const fallback = () =>
    buildFallbackTreatments(
      facts.map((f) => ({ factId: f.factId, neutralStatement: f.neutralStatement })),
      treatmentCount,
    );

  if (!isLLMConfigured()) return fallback();

  try {
    const llm = getLLMProvider();
    const profileContext = buildPromptProfileContext(project.promptProfile);
    const selectedFacts = selectFactsForPlanning(facts);
    const rawContent = await llm.generateText(
      buildNarrativePlannerPrompt({
        count: treatmentCount,
        facts: selectedFacts.map((f) => ({
          factId: f.factId,
          statement: f.neutralStatement,
          importance: f.storyImportance,
        })),
        validFactIds: [...validFactIds],
        fingerprints: fingerprints.map((fp) => ({
          openingType: fp.openingType,
          lens: fp.dominantNarrativeLens,
          endingFunction: fp.endingFunction,
          presentationOrderFactIds: fp.presentationOrderFactIds,
        })),
        promptProfile: profileContext,
        projectBrief: {
          title: project.title,
          topic: project.topic,
          outputLanguage: project.outputLanguage,
          audience: project.audience,
          genre: project.genre,
          tone: project.tone,
          mustCoverPoints: project.mustCoverPoints,
        },
        narrativePreferences: {
          approach,
          approachCustom: project.narrativeApproachCustom ?? undefined,
          openingHook: project.openingHook ?? "auto",
          openingHookCustom: project.openingHookCustom ?? undefined,
        },
      }),
      `${NARRATIVE_PLANNER_SYSTEM}\n\n${SYSTEM_ISOLATION_RULES}\n\nReturn one valid JSON object only. Each treatment must include centralQuestion, openingApproach, narrativeLens, diffExplanation, and beats (array of objects or strings).`,
      {
        maxTokens: 8192,
        jsonMode: true,
        trace: { runId, stage: "generate_plans", callId: "narrative_planner", attempt: 1 },
      },
    );
    return parseNarrativePlansLenient(parseJsonSafe(rawContent)).treatments;
  } catch (error) {
    console.warn("Narrative planner LLM failed, using fallback plan:", error);
    return fallback();
  }
}

async function persistNarrativePlans(
  projectId: string,
  treatments: Array<{
    centralQuestion: string;
    openingApproach: string;
    narrativeLens: string;
    diffExplanation: string;
    beats: Array<{
      beatNumber: number;
      purpose: string;
      shortDescription: string;
      claimIds: string[];
      narrativeRole: string;
      proposedVisualIdea?: string;
      expectedDurationSeconds?: number;
    }>;
  }>,
  validFactIds: Set<string>,
): Promise<void> {
  await prisma.narrativePlan.deleteMany({ where: { projectId, isEdited: false } });

  for (let i = 0; i < treatments.length; i++) {
    const t = treatments[i];
    const validatedBeats = validateBeatFactIds(t.beats, validFactIds);
    const plan = await prisma.narrativePlan.create({
      data: {
        projectId,
        treatmentIndex: i,
        centralQuestion: t.centralQuestion,
        openingApproach: t.openingApproach,
        narrativeLens: t.narrativeLens,
        diffExplanation: t.diffExplanation,
        isRecommended: i === 0,
      },
    });
    for (const beat of validatedBeats) {
      await prisma.narrativeBeat.create({
        data: {
          planId: plan.id,
          beatNumber: beat.beatNumber,
          purpose: beat.purpose,
          shortDescription: beat.shortDescription,
          claimIds: JSON.stringify(beat.claimIds),
          narrativeRole: beat.narrativeRole,
          proposedVisualIdea: beat.proposedVisualIdea,
          expectedDurationSeconds: beat.expectedDurationSeconds,
        },
      });
    }
  }
}

function parseFingerprint(fp: {
  sourceId: string;
  openingType: string;
  openingFunction: string;
  presentationOrder: string;
  presentationOrderFactIds: string | null;
  dominantNarrativeLens: string;
  turningPointType: string;
  endingFunction: string;
  recurringDevices: string;
  distinctiveMetaphorsOrPhrases: string;
}) {
  return {
    sourceId: fp.sourceId,
    openingType: fp.openingType,
    openingFunction: fp.openingFunction,
    presentationOrder: JSON.parse(fp.presentationOrder) as string[],
    presentationOrderFactIds: fp.presentationOrderFactIds,
    dominantNarrativeLens: fp.dominantNarrativeLens,
    turningPointType: fp.turningPointType,
    endingFunction: fp.endingFunction,
    recurringDevices: JSON.parse(fp.recurringDevices) as string[],
    distinctiveMetaphorsOrPhrases: fp.distinctiveMetaphorsOrPhrases,
  };
}

async function autoSelectLowestOverlapPlan(projectId: string): Promise<void> {
  const plans = await prisma.narrativePlan.findMany({
    where: { projectId },
    include: { beats: true },
  });
  const fingerprints = await prisma.narrativeFingerprint.findMany({ where: { projectId } });
  if (plans.length === 0 || fingerprints.length === 0) return;

  let bestPlan = plans[0];
  let bestScore = Infinity;

  for (const plan of plans) {
    let planMax = 0;
    for (const fp of fingerprints) {
      const fingerprint = parseFingerprint(fp);
      const score = structuralOverlapScore(
        {
          openingApproach: plan.openingApproach,
          narrativeLens: plan.narrativeLens,
          beats: plan.beats.map((b) => ({ shortDescription: b.shortDescription })),
        },
        fingerprint,
      );
      planMax = Math.max(planMax, score);
    }
    if (planMax < bestScore) {
      bestScore = planMax;
      bestPlan = plan;
    }
  }

  await prisma.narrativePlan.updateMany({ where: { projectId }, data: { isSelected: false } });
  await prisma.narrativePlan.update({ where: { id: bestPlan.id }, data: { isSelected: true } });
  await prisma.project.update({ where: { id: projectId }, data: { selectedPlanId: bestPlan.id } });
}

export type GenerateScriptResult = {
  charCount: number;
  target: number;
  inRange: boolean;
  status: NarrationDraft["status"];
  message?: string;
};

export async function generateScript(
  projectId: string,
  changeNote?: string,
  runId?: string,
): Promise<GenerateScriptResult> {
  const project = await prisma.project.findUniqueOrThrow({
    where: { id: projectId },
    include: { channelStyle: true, promptProfile: true },
  });
  const currentBeforeGeneration = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
    select: { id: true },
  });

  const selectedPlan = await prisma.narrativePlan.findFirst({
    where: { projectId, isSelected: true },
    include: { beats: { orderBy: { beatNumber: "asc" } } },
  });
  if (!selectedPlan) throw new Error("Select a narrative plan before generating the script.");

  const facts = await prisma.factPackItem.findMany({ where: { projectId, disabled: false } });
  const fingerprints = await prisma.narrativeFingerprint.findMany({ where: { projectId } });
  const validFactIds = new Set(facts.map((f) => f.factId));
  const range = lengthRange(resolveTargetCharCount(project.targetCharCount));
  const cta = resolveCtaConfig({
    targetCharCount: project.targetCharCount,
    projectChoice: project.ctaPreference,
    projectChannelName: project.ctaChannelName,
    projectClosingWording: project.ctaClosingWording,
    promptProfile: project.promptProfile,
    channelStyle: project.channelStyle,
  });

  const avoidanceRules = fingerprints.flatMap((fp) => [
    `Avoid opening type: ${fp.openingType}`,
    `Avoid lens: ${fp.dominantNarrativeLens}`,
    `Avoid ending: ${fp.endingFunction}`,
    `Avoid devices: ${fp.recurringDevices}`,
  ]);

  let draft: NarrationDraft;

  if (project.isDemo) {
    const fixture = loadDemoFixture();
    const paragraphs = fixture.script.paragraphs.map((p, i) => ({
      paragraphIndex: i,
      text: p.text,
      factIds: validateFactIds(p.factIds, validFactIds),
    }));
    const narration = assembleNarration(paragraphs);
    const charCount = countCharacters(narration);
    const inRange = isInLengthRange(charCount, range);
    draft = {
      paragraphs,
      narration,
      charCount,
      target: range.target,
      min: range.min,
      max: range.max,
      status: inRange ? "ready" : "target_not_reached",
      truncatedOutput: false,
      message: inRange ? undefined : formatLengthMissMessage(charCount, range.target),
    };
  } else {
    if (!isLLMConfigured()) throw new Error("LLM API key required for script generation.");

    const llm = getLLMProvider();
    draft = await generateNarration(
      {
        targetCharCount: project.targetCharCount,
        brief: {
          title: project.title,
          topic: project.topic,
          audience: project.audience,
          tone: project.tone,
          genre: project.genre,
          openingHook: project.openingHook ?? "auto",
          openingHookCustom: project.openingHookCustom,
          narrativeApproach: legacyGoalToNarrativeApproach(project.narrativeGoal),
          narrativeApproachCustom: project.narrativeApproachCustom,
          targetCharCount: range.target,
          mustCoverPoints: project.mustCoverPoints,
        },
        style: buildNarrationStyleContext(project.promptProfile),
        beats: selectedPlan.beats.map((b) => ({
          beatNumber: b.beatNumber,
          purpose: b.purpose,
          shortDescription: b.shortDescription,
          claimIds: JSON.parse(b.claimIds) as string[],
          narrativeRole: b.narrativeRole,
        })),
        facts: facts.map((f) => ({
          factId: f.factId,
          neutralStatement: f.neutralStatement,
          storyImportance: f.storyImportance,
        })),
        avoidanceRules,
        validFactIds,
        cta,
        channelStyle: project.channelStyle ?? undefined,
        narrativePreferences: {
          approach: legacyGoalToNarrativeApproach(project.narrativeGoal),
          approachCustom: project.narrativeApproachCustom ?? undefined,
          openingHook: project.openingHook ?? "auto",
          openingHookCustom: project.openingHookCustom ?? undefined,
        },
        onProgress: async (message) => {
          if (!runId) return;
          await prisma.pipelineRun.update({
            where: { id: runId },
            data: { errorMessage: message },
          });
        },
      },
      (args) =>
        llm.complete({
          ...args,
          trace: {
            runId,
            stage: args.trace?.stage ?? "script_write",
            callId: args.trace?.callId,
            chunkId: args.trace?.chunkId,
            attempt: args.trace?.attempt,
          },
        }),
    );
  }

  const currentBeforePersist = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
    select: { id: true },
  });
  if (currentBeforePersist?.id !== currentBeforeGeneration?.id) {
    throw new Error(
      "A newer script version was saved while generation was running. This run was discarded to protect your latest changes.",
    );
  }
  if (countCharacters(draft.narration.trim()) === 0) {
    throw new Error(
      "Generation produced no narration text (0 characters), likely due to output-token truncation before visible content. No script was overwritten. Retry generation with the same settings, or reduce the target length per run and regenerate.",
    );
  }
  await persistNarrationDraft(projectId, draft, changeNote ?? "Generated");

  return {
    charCount: draft.charCount,
    target: draft.target,
    inRange: draft.status === "ready",
    status: draft.status,
    message: draft.message,
  };
}

async function persistNarrationDraft(
  projectId: string,
  draft: NarrationDraft,
  changeNote: string,
): Promise<void> {
  await prisma.scriptVersion.updateMany({
    where: { projectId },
    data: { isCurrent: false },
  });

  const versionNumber = (await prisma.scriptVersion.count({ where: { projectId } })) + 1;
  const charCount = countCharacters(draft.narration);

  const scriptVersion = await prisma.scriptVersion.create({
    data: {
      projectId,
      versionNumber,
      content: draft.narration,
      charCount,
      estDurationSec: estimateDurationSeconds(charCount),
      isCurrent: true,
      changeNote:
        draft.status === "target_not_reached"
          ? `${changeNote} — ${formatLengthMissMessage(charCount, draft.target)}`
          : draft.message
            ? `${changeNote} — ${draft.message}`
            : changeNote,
    },
  });

  for (const p of draft.paragraphs) {
    await prisma.scriptParagraphTrace.create({
      data: {
        scriptVersionId: scriptVersion.id,
        paragraphIndex: p.paragraphIndex,
        paragraphText: p.text,
        factIds: JSON.stringify(p.factIds),
        paragraphRole: p.paragraphRole ?? "narrative",
      },
    });
  }

  await prisma.project.update({
    where: { id: projectId },
    data: {
      lengthStatus: draft.status,
      errorMessage:
        draft.status === "target_not_reached"
          ? draft.message ?? formatLengthMissMessage(charCount, draft.target)
          : null,
    },
  });
}

async function runOriginalityQA(projectId: string): Promise<void> {
  const project = await prisma.project.findUniqueOrThrow({
    where: { id: projectId },
    include: { sources: true },
  });
  const script = await prisma.scriptVersion.findFirst({
    where: { projectId, isCurrent: true },
    include: { paragraphs: true },
  });
  if (!script) throw new Error("No script to review.");

  const selectedPlan = await prisma.narrativePlan.findFirst({
    where: { projectId, isSelected: true },
    include: { beats: true },
  });
  const fingerprints = await prisma.narrativeFingerprint.findMany({ where: { projectId } });
  const factPack = await prisma.factPackItem.findMany({ where: { projectId } });

  const qa = project.isDemo
    ? loadDemoFixture().originality
    : analyzeOriginality({
        script: script.content,
        plan: selectedPlan
          ? {
              openingApproach: selectedPlan.openingApproach,
              narrativeLens: selectedPlan.narrativeLens,
              beats: selectedPlan.beats.map((b) => ({
                shortDescription: b.shortDescription,
                claimIds: b.claimIds,
              })),
            }
          : null,
        fingerprints: fingerprints.map(parseFingerprint),
        sources: project.sources,
        factPack: factPack.map((f) => ({
          factId: f.factId,
          neutralStatement: f.neutralStatement,
          sourceClaimIds: f.sourceClaimIds,
        })),
        paragraphFactIds: script.paragraphs.map((p) => JSON.parse(p.factIds) as string[]),
      });

  const report = await prisma.originalityReport.create({
    data: {
      projectId,
      overallStatus: qa.overallStatus,
      phraseOverlap: qa.phraseOverlap,
      hookSimilarity: qa.hookSimilarity,
      orderSimilarity: qa.orderSimilarity,
      metaphorWarnings: JSON.stringify(qa.metaphorWarnings),
      unsupportedClaims: JSON.stringify(qa.unsupportedClaims),
      recommendedAction: qa.recommendedAction,
      exportBlocked: qa.exportBlocked,
    },
  });

  for (const finding of qa.findings) {
    await prisma.originalityFinding.create({
      data: {
        reportId: report.id,
        category: finding.category,
        severity: finding.severity,
        explanation: finding.explanation,
        affectedSection: finding.affectedSection,
        remedy: finding.remedy,
      },
    });
  }
}

export async function createProjectWithSources(input: {
  title: string;
  topic?: string;
  outputLanguage?: string;
  targetDurationMin?: number;
  targetCharCount?: number;
  audience?: string;
  genre?: string;
  tone?: string;
  mustCoverPoints?: string;
  openingHook?: string;
  openingHookCustom?: string;
  ctaPreference?: string;
  ctaChannelName?: string;
  ctaClosingWording?: string;
  narrativeGoal?: string;
  narrativeApproachCustom?: string;
  channelStyleId?: string;
  promptProfileId?: string;
  sources: Array<{
    kind: "youtube" | "pasted";
    title?: string;
    url?: string;
    transcript?: string;
    sourceLabel?: string;
    language?: string;
  }>;
  isDemo?: boolean;
}) {
  const project = await prisma.project.create({
    data: {
      title: input.title,
      topic: input.topic,
      outputLanguage: input.outputLanguage ?? "hi",
      targetDurationMin: input.targetDurationMin,
      targetCharCount: input.targetCharCount ?? 6000,
      audience: input.audience,
      genre: input.genre,
      tone: input.tone,
      mustCoverPoints: input.mustCoverPoints,
      openingHook: input.openingHook ?? "auto",
      openingHookCustom: input.openingHookCustom,
      ctaPreference: input.ctaPreference ?? "one_mid_and_closing",
      ctaChannelName: input.ctaChannelName,
      ctaClosingWording: input.ctaClosingWording,
      narrativeGoal: input.narrativeGoal ?? "auto",
      narrativeApproachCustom: input.narrativeApproachCustom,
      channelStyleId: input.channelStyleId,
      promptProfileId: input.promptProfileId,
      isDemo: input.isDemo ?? false,
    },
  });

  for (const src of input.sources) {
    let videoId: string | null = null;
    let url = src.url ?? null;
    if (src.kind === "youtube" && src.url) {
      const normalized = normalizeYouTubeUrl(src.url);
      videoId = normalized?.videoId ?? null;
      url = normalized?.canonicalUrl ?? src.url;
    }

    await prisma.source.create({
      data: {
        projectId: project.id,
        kind: src.kind,
        title: src.title ?? (videoId ? `YouTube ${videoId}` : "Pasted transcript"),
        url,
        videoId,
        sourceLabel: src.sourceLabel,
        language: src.language,
        rawTranscript: src.transcript?.trim() ? src.transcript.trim() : null,
        transcriptOrigin: src.transcript?.trim() ? "manual" : null,
        transcriptStatus: src.transcript?.trim() ? "transcript_ready" : "needs_transcript",
      },
    });
  }

  return project;
}
