export const GENRE_OPTIONS = [
  { value: "general_documentary", label: "General documentary" },
  { value: "biography", label: "Biography" },
  { value: "history", label: "History" },
  { value: "intelligence_espionage", label: "Intelligence / espionage" },
  { value: "crime_investigation", label: "Crime / investigation" },
  { value: "science_technology", label: "Science / technology" },
  { value: "economics_geopolitics", label: "Economics / geopolitics" },
  { value: "custom", label: "Custom" },
] as const;

export type StoryGenreOption = (typeof GENRE_OPTIONS)[number]["value"];

export const NARRATIVE_APPROACH_OPTIONS = [
  {
    value: "auto",
    label: "Auto",
    help: "Choose the narrative structure best suited to the supplied points.",
  },
  {
    value: "question_driven",
    label: "Question-driven",
    help: "Organize the story around one central question and progressively answer it.",
  },
  {
    value: "mystery_investigation",
    label: "Mystery / investigation",
    help: "Start with an unknown and reveal source-supported explanations step by step.",
  },
  {
    value: "chronological",
    label: "Chronological",
    help: "Follow events in time order with clear cause-and-effect transitions.",
  },
  {
    value: "outcome_first_rewind",
    label: "Outcome-first / rewind",
    help: "Open with a supported outcome, then explicitly rewind to show how it happened.",
  },
  {
    value: "character_led",
    label: "Character-led",
    help: "Track key choices, constraints and consequences around a central person.",
  },
  {
    value: "cause_effect_explainer",
    label: "Cause-and-effect explainer",
    help: "Explain mechanisms and sequences that produce the final outcome.",
  },
  {
    value: "contrast_paradox",
    label: "Contrast / paradox",
    help: "Explore an apparent contradiction and explain the underlying causes.",
  },
  {
    value: "custom",
    label: "Custom",
    help: "Provide your own narrative structure instructions.",
  },
] as const;

export type NarrativeApproachOption = (typeof NARRATIVE_APPROACH_OPTIONS)[number]["value"];

export const OPENING_HOOK_OPTIONS = [
  { value: "auto", label: "Auto — match narrative approach" },
  { value: "central_question", label: "A central question" },
  { value: "surprising_fact", label: "A surprising source-supported fact" },
  { value: "apparent_contradiction", label: "An apparent contradiction" },
  { value: "moment_of_action", label: "A source-supported moment of action" },
  { value: "outcome_first", label: "Outcome-first" },
  { value: "custom", label: "Custom opening instructions" },
] as const;

export type OpeningHookOption = (typeof OPENING_HOOK_OPTIONS)[number]["value"];

export function isKnownGenre(value: string | null | undefined): value is Exclude<StoryGenreOption, "custom"> {
  if (!value) return false;
  return GENRE_OPTIONS.some((g) => g.value !== "custom" && g.value === value);
}

export function narrativeApproachToLegacyGoal(value: NarrativeApproachOption): string {
  if (value === "auto") return "recommend";
  return value;
}

export function legacyGoalToNarrativeApproach(value: string | null | undefined): NarrativeApproachOption {
  if (!value || value === "recommend") return "auto";
  const known = NARRATIVE_APPROACH_OPTIONS.some((o) => o.value === value);
  return known ? (value as NarrativeApproachOption) : "custom";
}

export function approachLabel(value: NarrativeApproachOption | string | null | undefined): string {
  if (!value) return "Auto";
  const found = NARRATIVE_APPROACH_OPTIONS.find((o) => o.value === value);
  return found?.label ?? "Custom";
}

export function hookLabel(value: OpeningHookOption | string | null | undefined): string {
  if (!value) return "Auto — match narrative approach";
  const found = OPENING_HOOK_OPTIONS.find((o) => o.value === value);
  return found?.label ?? "Custom opening instructions";
}
