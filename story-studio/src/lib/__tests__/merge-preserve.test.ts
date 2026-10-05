import { describe, expect, it } from "vitest";
import { mergeWithPreservedFacts } from "@/lib/pipeline/merge-facts";
import type { FactPackItem } from "@/lib/schemas";

describe("persistence of pinned facts", () => {
  it("preserves user-pinned and user-edited facts during merge", () => {
    const newFacts: FactPackItem[] = [
      {
        factId: "fact-001",
        neutralStatement: "Merged statement A",
        sourceClaimIds: ["c1"],
        sourceCount: 1,
        storyImportance: "high",
        userPinned: false,
      },
      {
        factId: "fact-002",
        neutralStatement: "New fact B",
        sourceClaimIds: ["c2"],
        sourceCount: 1,
        storyImportance: "medium",
        userPinned: false,
      },
    ];

    const existing = [
      {
        id: "db-1",
        factId: "fact-001",
        neutralStatement: "User edited statement A",
        sourceClaimIds: '["c1"]',
        sourceCount: 1,
        peoplePlacesDatesNumbers: null,
        storyImportance: "high",
        userPinned: true,
        userEdited: true,
        disabled: false,
        editorNotes: null,
      },
    ];

    const merged = mergeWithPreservedFacts(newFacts, existing, new Set(["c1", "c2"]));

    expect(merged.some((f) => f.factId === "fact-001" && f.neutralStatement === "User edited statement A")).toBe(true);
    expect(merged.some((f) => f.factId === "fact-002")).toBe(true);
    expect(merged.filter((f) => f.factId === "fact-001")).toHaveLength(1);
  });
});
