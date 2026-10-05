import { describe, expect, it } from "vitest";
import {
  approachLabel,
  GENRE_OPTIONS,
  hookLabel,
  legacyGoalToNarrativeApproach,
  NARRATIVE_APPROACH_OPTIONS,
  OPENING_HOOK_OPTIONS,
} from "@/lib/story-settings/options";

describe("story settings options", () => {
  it("exposes shared genre, approach and opening-hook choices", () => {
    expect(GENRE_OPTIONS.length).toBeGreaterThan(5);
    expect(NARRATIVE_APPROACH_OPTIONS.some((o) => o.value === "question_driven")).toBe(true);
    expect(OPENING_HOOK_OPTIONS.some((o) => o.value === "central_question")).toBe(true);
  });

  it("maps legacy narrative goal values to explicit approach", () => {
    expect(legacyGoalToNarrativeApproach("recommend")).toBe("auto");
    expect(legacyGoalToNarrativeApproach("chronological")).toBe("chronological");
  });

  it("returns stable labels for summaries", () => {
    expect(approachLabel("mystery_investigation")).toContain("Mystery");
    expect(hookLabel("outcome_first")).toContain("Outcome");
  });
});
