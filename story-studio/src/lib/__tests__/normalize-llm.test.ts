import { describe, expect, it } from "vitest";
import { fingerprintResponseSchema } from "@/lib/schemas";
import { finalizeFingerprintFields, normalizeFingerprintPayload } from "@/lib/pipeline/normalize-llm";

describe("fingerprint LLM normalization", () => {
  it("unwraps nested fingerprint objects", () => {
    const normalized = normalizeFingerprintPayload({
      fingerprint: {
        openingType: "dramatic_question",
        opening_function: "hook",
        presentationOrder: ["a", "b"],
      },
    });

    expect(normalized.openingType).toBe("dramatic_question");
    expect(normalized.openingFunction).toBe("hook");
  });

  it("applies defaults for missing fields", () => {
    const result = fingerprintResponseSchema.parse({});
    expect(result.openingType).toBe("unknown");
    expect(result.presentationOrder).toEqual([]);
    expect(result.recurringDevices).toEqual([]);
  });

  it("coerces partial snake_case payloads", () => {
    const result = fingerprintResponseSchema.parse(
      finalizeFingerprintFields(
        normalizeFingerprintPayload({
          dominant_narrative_lens: "chronology",
          recurring_devices: ["countdown"],
        }),
      ),
    );
    expect(result.dominantNarrativeLens).toBe("chronology");
    expect(result.recurringDevices).toEqual(["countdown"]);
    expect(result.openingType).toBe("unknown");
  });
});
