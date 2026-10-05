import type { PromptProfile } from "@prisma/client";
import { stripExtraDeliverableInstructions } from "@/lib/narration/sanitize";

/** Editable voice/delivery layer — isolation rules stay in system prompts. */
export function buildPromptProfileContext(profile: PromptProfile | null): Record<string, unknown> {
  if (!profile) return {};

  return {
    profileName: profile.name,
    genre: profile.genre,
    styleInstructions: profile.styleInstructions,
    targetLanguage: profile.targetLanguage,
    audience: profile.audience,
    pacingNotes: profile.pacingNotes,
    ctaNotes: profile.ctaNotes,
    titleNotes: profile.titleNotes,
    thumbnailNotes: profile.thumbnailNotes,
    visualNotes: profile.visualNotes,
    preferredVocab: profile.preferredVocab,
    bannedPhrases: profile.bannedPhrases,
  };
}

/** Style-only context for narration. Drops extra deliverables and profile length instructions. */
export function buildNarrationStyleContext(profile: PromptProfile | null): Record<string, unknown> {
  if (!profile) {
    return { outputMode: "narration_only" };
  }

  return {
    profileName: profile.name,
    genre: profile.genre,
    styleInstructions: stripExtraDeliverableInstructions(profile.styleInstructions),
    targetLanguage: profile.targetLanguage,
    audience: profile.audience,
    pacingNotes: profile.pacingNotes,
    ctaNotes: profile.ctaNotes,
    preferredVocab: profile.preferredVocab,
    bannedPhrases: profile.bannedPhrases,
    outputMode: "narration_only",
    lengthAuthority:
      "Use the application's targetCharCount only. Ignore any profile word-count, duration, title, thumbnail, or extra-section instructions.",
  };
}

export const SYSTEM_ISOLATION_RULES = `
NON-EDITABLE RULES (always enforced):
- Never use raw transcript wording, source hooks, source order, source analogies, or source endings.
- Never invent facts, quotes, motives, dates, numbers, or causation absent from the Fact Pack.
- This is an editorial originality workflow, not legal copyright clearance.
`.trim();
