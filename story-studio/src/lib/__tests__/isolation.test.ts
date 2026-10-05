import { describe, expect, it } from "vitest";
import { assertWriterInputIsolation, buildWriterSafePayload } from "@/lib/pipeline/isolation";

describe("source-to-writer isolation", () => {
  it("allows writer-safe payload", () => {
    expect(() =>
      buildWriterSafePayload({
        brief: { title: "Test" },
        channelStyle: { tonePreset: "explanatory" },
        factPack: [{ factId: "fact-001", neutralStatement: "Neutral fact", storyImportance: "high" }],
        blueprint: { centralQuestion: "Why?" },
        avoidanceRules: ["Avoid battle hook"],
      }),
    ).not.toThrow();
  });

  it("rejects payloads containing raw transcript fields", () => {
    expect(() => assertWriterInputIsolation({ rawTranscript: "secret source wording" })).toThrow(
      /isolation violation/i,
    );
  });
});
