import { describe, expect, it } from "vitest";
import { updateProjectSettingsSchema } from "@/lib/schemas";

describe("updateProjectSettingsSchema", () => {
  it("accepts partial updates and preserves omitted fields", () => {
    const parsed = updateProjectSettingsSchema.parse({
      targetCharCount: 12000,
      ctaPreference: "one_mid_and_closing",
      narrativeGoal: "question_driven",
      openingHook: "central_question",
    });
    expect(parsed.targetCharCount).toBe(12000);
    expect(parsed.ctaPreference).toBe("one_mid_and_closing");
    expect(parsed.narrativeGoal).toBe("question_driven");
    expect(parsed.openingHook).toBe("central_question");
    expect(parsed.title).toBeUndefined();
  });

  it("supports explicit clears for nullable optional fields", () => {
    const parsed = updateProjectSettingsSchema.parse({
      topic: null,
      promptProfileId: null,
      ctaChannelName: null,
      channelStyleId: null,
    });
    expect(parsed.topic).toBeNull();
    expect(parsed.promptProfileId).toBeNull();
    expect(parsed.ctaChannelName).toBeNull();
    expect(parsed.channelStyleId).toBeNull();
  });

  it("rejects invalid target length", () => {
    const result = updateProjectSettingsSchema.safeParse({ targetCharCount: 999 });
    expect(result.success).toBe(false);
  });

  it("rejects invalid CTA enum values", () => {
    const result = updateProjectSettingsSchema.safeParse({ ctaPreference: "invalid" });
    expect(result.success).toBe(false);
  });

  it("rejects invalid narrative approach and opening hook values", () => {
    const badApproach = updateProjectSettingsSchema.safeParse({ narrativeGoal: "timeline_fresh" });
    const badHook = updateProjectSettingsSchema.safeParse({ openingHook: "battle_scene" });
    expect(badApproach.success).toBe(false);
    expect(badHook.success).toBe(false);
  });
});
