import { z } from "zod";
import { NARRATIVE_APPROACH_OPTIONS, OPENING_HOOK_OPTIONS } from "@/lib/story-settings/options";
import {
  finalizeBeatFields,
  finalizeFingerprintFields,
  finalizeTreatmentFields,
  normalizeClaimsPayload,
  normalizeFactPackPayload,
  normalizeFingerprintPayload,
  normalizeNarrativePlansPayload,
  normalizeScriptPayload,
  coerceString,
} from "@/lib/pipeline/normalize-llm";

export const claimTypeSchema = z.enum([
  "event",
  "date",
  "number",
  "quote",
  "allegation",
  "interpretation",
  "background",
]);

export const claimSchema = z.object({
  id: z.string(),
  sourceId: z.string(),
  neutralClaim: z.string(),
  claimType: claimTypeSchema,
  peoplePlacesDatesNumbers: z.string().optional(),
  timestampStart: z.number().nullable().optional(),
  timestampEnd: z.number().nullable().optional(),
  supportExcerpt: z.string(),
  sourceCertainty: z.enum(["explicit", "ambiguous"]),
  storyRelevance: z.enum(["high", "medium", "low"]),
  requiredByUser: z.boolean().default(false),
});

export const claimsResponseSchema = z.preprocess(
  normalizeClaimsPayload,
  z.object({
    claims: z.array(claimSchema).max(15),
  }),
);

const fingerprintFieldsSchema = z.preprocess(
  (raw) => finalizeFingerprintFields(normalizeFingerprintPayload(raw)),
  z.object({
    openingType: z.string(),
    openingFunction: z.string(),
    presentationOrder: z.array(z.string()),
    dominantNarrativeLens: z.string(),
    turningPointType: z.string(),
    recurringDevices: z.array(z.string()),
    distinctiveMetaphorsOrPhrases: z.array(z.string()),
    endingFunction: z.string(),
    titleAndThumbnailPattern: z.string(),
  }),
);

export const fingerprintSchema = fingerprintFieldsSchema.and(
  z.object({ sourceId: z.string().optional() }),
);

export const fingerprintResponseSchema = fingerprintFieldsSchema;

export const factPackItemSchema = z.object({
  factId: z.string(),
  neutralStatement: z.string(),
  sourceClaimIds: z.array(z.string()),
  sourceCount: z.number(),
  peoplePlacesDatesNumbers: z.string().optional(),
  storyImportance: z.enum(["high", "medium", "low"]),
  userPinned: z.boolean().default(false),
  editorNotes: z.string().optional(),
});

export const factPackResponseSchema = z.preprocess(
  normalizeFactPackPayload,
  z.object({
    facts: z.array(factPackItemSchema),
  }),
);

export const narrativeBeatSchema = z.preprocess(
  (raw) => finalizeBeatFields((raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>, 0),
  z.object({
    beatNumber: z.number(),
    purpose: z.string().default("develop"),
    shortDescription: z.string().default("Story beat"),
    claimIds: z.array(z.string()).default([]),
    narrativeRole: z.string().default("development"),
    proposedVisualIdea: z.string().optional(),
    expectedDurationSeconds: z.number().optional(),
  }),
);

export const narrativeTreatmentSchema = z.preprocess(
  (raw) =>
    finalizeTreatmentFields((raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>, 0),
  z.object({
    centralQuestion: z.string().default("Treatment"),
    openingApproach: z.string().default("Fresh contextual opening"),
    narrativeLens: z.string().default("explanatory"),
    diffExplanation: z.string().default("Distinct from source storytelling patterns."),
    beats: z.array(narrativeBeatSchema).min(1).max(12),
  }),
);

export const narrativePlansResponseSchema = z.preprocess(
  normalizeNarrativePlansPayload,
  z.object({
    treatments: z.array(narrativeTreatmentSchema).min(1).max(3),
  }),
);

export const scriptParagraphSchema = z.object({
  paragraphIndex: z.number(),
  text: z.string(),
  factIds: z.array(z.string()),
});

export const scriptResponseSchema = z.preprocess(
  (raw) => {
    const normalized = normalizeScriptPayload(raw);
    const paragraphs = Array.isArray(normalized.paragraphs)
      ? normalized.paragraphs.map((p, i) => {
          const row = (p && typeof p === "object" ? p : {}) as Record<string, unknown>;
          return {
            paragraphIndex: typeof row.paragraphIndex === "number" ? row.paragraphIndex : i,
            text: coerceString(row.text ?? row.paragraphText ?? row.content, ""),
            factIds: Array.isArray(row.factIds)
              ? row.factIds.map(String)
              : Array.isArray(row.fact_ids)
                ? row.fact_ids.map(String)
                : [],
          };
        })
      : [];
    return {
      narration: coerceString(normalized.narration, ""),
      paragraphs,
    };
  },
  z.object({
    narration: z.string().min(1),
    paragraphs: z.array(scriptParagraphSchema),
  }),
);

export const originalityFindingSchema = z.object({
  category: z.string(),
  severity: z.enum(["low", "medium", "high"]),
  explanation: z.string(),
  affectedSection: z.string(),
  remedy: z.string().optional(),
});

export const originalityVerdictSchema = z.enum(["pass", "warn", "block"]);

export const originalityResponseSchema = z.object({
  overallStatus: originalityVerdictSchema,
  phraseOverlap: originalityVerdictSchema,
  hookSimilarity: originalityVerdictSchema,
  orderSimilarity: originalityVerdictSchema,
  metaphorWarnings: z.array(z.string()),
  unsupportedClaims: z.array(z.string()),
  recommendedAction: z.string(),
  findings: z.array(originalityFindingSchema),
});

export const createProjectSchema = z.object({
  title: z.string().min(1),
  topic: z.string().optional(),
  outputLanguage: z.string().default("hi"),
  targetDurationMin: z.number().optional(),
  targetCharCount: z.number().int().min(1000).max(50000).optional(),
  audience: z.string().optional(),
  genre: z.string().optional(),
  tone: z.string().optional(),
  mustCoverPoints: z.string().optional(),
  openingHook: z.enum(OPENING_HOOK_OPTIONS.map((o) => o.value) as [string, ...string[]]).optional(),
  openingHookCustom: z.string().optional(),
  ctaPreference: z
    .enum(["closing_only", "one_mid_and_closing", "two_mid_and_closing"])
    .optional(),
  ctaChannelName: z.string().optional(),
  ctaClosingWording: z.string().optional(),
  narrativeGoal: z
    .enum(NARRATIVE_APPROACH_OPTIONS.map((o) => o.value) as [string, ...string[]])
    .default("auto"),
  narrativeApproachCustom: z.string().optional(),
  channelStyleId: z.string().optional(),
  promptProfileId: z.string().optional(),
  sources: z
    .array(
      z.object({
        kind: z.enum(["youtube", "pasted"]),
        title: z.string().optional(),
        url: z.string().optional(),
        transcript: z.string().optional(),
        sourceLabel: z.string().optional(),
        language: z.string().optional(),
      }),
    )
    .min(1)
    .max(5),
});

export const updateProjectSettingsSchema = z.object({
  title: z.string().min(1).optional(),
  topic: z.string().nullable().optional(),
  outputLanguage: z.string().nullable().optional(),
  targetCharCount: z.number().int().min(1000).max(50000).nullable().optional(),
  audience: z.string().nullable().optional(),
  genre: z.string().nullable().optional(),
  tone: z.string().nullable().optional(),
  mustCoverPoints: z.string().nullable().optional(),
  openingHook: z
    .enum(OPENING_HOOK_OPTIONS.map((o) => o.value) as [string, ...string[]])
    .nullable()
    .optional(),
  openingHookCustom: z.string().nullable().optional(),
  ctaPreference: z
    .enum(["closing_only", "one_mid_and_closing", "two_mid_and_closing"])
    .nullable()
    .optional(),
  ctaChannelName: z.string().nullable().optional(),
  ctaClosingWording: z.string().nullable().optional(),
  narrativeGoal: z
    .enum(NARRATIVE_APPROACH_OPTIONS.map((o) => o.value) as [string, ...string[]])
    .nullable()
    .optional(),
  narrativeApproachCustom: z.string().nullable().optional(),
  channelStyleId: z.string().nullable().optional(),
  promptProfileId: z.string().nullable().optional(),
});

export type Claim = z.infer<typeof claimSchema>;
export type FactPackItem = z.infer<typeof factPackItemSchema>;
export type NarrativeTreatment = z.infer<typeof narrativeTreatmentSchema>;
export type ScriptResponse = z.infer<typeof scriptResponseSchema>;
export type OriginalityResponse = z.infer<typeof originalityResponseSchema>;
