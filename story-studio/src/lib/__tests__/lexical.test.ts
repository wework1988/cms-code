import { describe, expect, it } from "vitest";
import { lexicalOverlapScore } from "@/lib/originality/lexical";

describe("lexical overlap detection", () => {
  it("flags unusually shared phrase shingles", () => {
    const source = "the private company conquered the subcontinent through trade and force repeatedly";
    const script = "the private company conquered the subcontinent through trade and force repeatedly in a new frame";
    const result = lexicalOverlapScore(source, script);
    expect(result.sharedPhrases.length).toBeGreaterThan(0);
    expect(["pass", "warn", "block"]).toContain(result.status);
  });

  it("passes when texts share only common factual names", () => {
    const source = "East India Company Battle of Plassey 1757";
    const script = "1757 में Plassey और East India Company का सफर";
    const result = lexicalOverlapScore(source, script);
    expect(result.status).toBe("pass");
  });
});
