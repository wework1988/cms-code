import { describe, expect, it } from "vitest";
import { parseJsonSafe, repairTruncatedJson } from "@/lib/llm/json";

describe("JSON parsing helpers", () => {
  it("repairs truncated JSON objects", () => {
    const repaired = repairTruncatedJson('{"openingType":"hook","presentationOrder":["a"');
    expect(JSON.parse(repaired)).toEqual({
      openingType: "hook",
      presentationOrder: ["a"],
    });
  });

  it("returns empty object for empty LLM output", () => {
    expect(parseJsonSafe("")).toEqual({});
    expect(parseJsonSafe("   ")).toEqual({});
  });

  it("extracts JSON from markdown fences", () => {
    expect(parseJsonSafe('```json\n{"ok":true}\n```')).toEqual({ ok: true });
  });

  it("repairs truncated JSON ending mid-string", () => {
    const repaired = repairTruncatedJson('{"treatments":[{"centralQuestion":"Why');
    expect(() => JSON.parse(repaired)).not.toThrow();
  });
});
