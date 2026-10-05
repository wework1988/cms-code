import { describe, expect, it } from "vitest";
import { isOutputTruncated, maxCharsPerModelCall, tokensForNarrationCharBudget } from "@/lib/llm/errors";
import { allocateBeatBudgets, chunkBeatsByCharBudget, splitOversizedBeat } from "@/lib/narration/budget";
import {
  assembleNarration,
  countCharacters,
  formatLengthMissMessage,
  lengthRange,
  MAX_LENGTH_REPAIR_PASSES,
  trimAtSentenceBoundary,
} from "@/lib/narration/count";
import {
  generateNarration,
  repairNarrationLength,
  type CompletionFn,
  type NarrationDraft,
  type NarrationGenerateInput,
} from "@/lib/narration/engine";
import { buildNarrationExport, NARRATION_ONLY_RULES, sanitizeNarration, stripExtraDeliverableInstructions } from "@/lib/narration/sanitize";
import { buildNarrationStyleContext } from "@/lib/prompts/profile";
import { resolveCtaConfig } from "@/lib/cta/config";
import { reduceRepetition } from "@/lib/narration/editorial";

function padHindi(n: number): string {
  const seed = Array.from("भारतीय इतिहास की यह घटना विस्तार से समझाती है और उसके परिणाम बताती है। ");
  const out: string[] = [];
  while (out.length < Math.max(1, n - 1)) {
    out.push(...seed);
  }
  return `${out.slice(0, Math.max(0, n - 1)).join("")}।`;
}

function padHindiVariant(n: number): string {
  const seed = Array.from("यह अलग विश्लेषण कारणों के बीच संबंध समझाता है और आगे के परिणामों को स्पष्ट करता है। ");
  const out: string[] = [];
  while (out.length < Math.max(1, n - 1)) {
    out.push(...seed);
  }
  return `${out.slice(0, Math.max(0, n - 1)).join("")}।`;
}

function paragraphsJson(text: string, factIds = ["fact-1"]): string {
  return JSON.stringify({ paragraphs: [{ text, factIds }] });
}

const baseBeats = [
  { beatNumber: 1, purpose: "hook", shortDescription: "Open", claimIds: ["fact-1"], narrativeRole: "opening" },
  { beatNumber: 2, purpose: "develop", shortDescription: "Mechanism", claimIds: ["fact-1"], narrativeRole: "development" },
  { beatNumber: 3, purpose: "turn", shortDescription: "Turning point", claimIds: ["fact-1"], narrativeRole: "turning_point" },
  { beatNumber: 4, purpose: "close", shortDescription: "Close", claimIds: ["fact-1"], narrativeRole: "closing" },
];

const baseInput: NarrationGenerateInput = {
  targetCharCount: 12_000,
  brief: { title: "Test", targetCharCount: 12_000 },
  style: { outputMode: "narration_only" },
  beats: baseBeats,
  facts: [{ factId: "fact-1", neutralStatement: "Ajit Doval served as India's National Security Advisor." }],
  avoidanceRules: [],
  validFactIds: new Set(["fact-1"]),
  cta: resolveCtaConfig({ targetCharCount: 12_000, projectChoice: "one_mid_and_closing" }),
};

function taskOf(prompt: string): string {
  try {
    return String(JSON.parse(prompt).task ?? "");
  } catch {
    return "";
  }
}

describe("Unicode character counting", () => {
  it("counts Hindi combining marks and emoji as Unicode code points", () => {
    expect(countCharacters("क्ष")).toBe(Array.from("क्ष").length);
    expect(countCharacters("क्षै")).toBe(Array.from("क्षै").length);
    expect(countCharacters("👩‍🚀")).toBe(Array.from("👩‍🚀").length);
    expect(countCharacters("हिंदी 🚀")).toBe(Array.from("हिंदी 🚀").length);
  });
});

describe("length range", () => {
  it("uses ±5% around the saved target", () => {
    const range = lengthRange(12_000);
    expect(range.min).toBe(11_400);
    expect(range.max).toBe(12_600);
  });
});

describe("narration assembly", () => {
  it("assembles stored paragraph text with a consistent separator", () => {
    const paragraphs = [{ text: "पहला।" }, { text: "दूसरा।" }];
    const narration = assembleNarration(paragraphs);
    expect(narration).toBe("पहला।\n\nदूसरा।");
    expect(countCharacters(narration)).toBe(Array.from(narration).length);
  });
});

describe("editorial repetition guard", () => {
  it("removes a shorter repeated passage", () => {
    const original = "अमेरिकी रिफाइनरियों को भारी कच्चे तेल की जरूरत होती है और वे उसी के लिए बनी थीं। जब घरेलू उत्पादन हल्का तेल देता है, तो आयात जारी रहता है। यही अंतर व्यापार को प्रभावित करता है।";
    const recap = "अमेरिकी रिफाइनरियों को भारी कच्चे तेल की जरूरत होती है और वे उसी के लिए बनी थीं। जब घरेलू उत्पादन हल्का तेल देता है, तो आयात जारी रहता है।";
    const reduced = reduceRepetition([
      { paragraphIndex: 0, text: original, factIds: ["fact-1"] },
      { paragraphIndex: 1, text: recap, factIds: ["fact-1"] },
    ]);
    expect(reduced).toHaveLength(1);
  });

  it("removes degenerate repeated sign-off text", () => {
    const reduced = reduceRepetition([
      { paragraphIndex: 0, text: "अगली कड़ी में अगली कड़ी में अगली कड़ी में अगली कड़ी में", factIds: [] },
    ]);
    expect(reduced).toHaveLength(0);
  });
});

describe("generateNarration length repair", () => {
  it("passes resolved CTA and length settings into generation and repair prompts", async () => {
    const seen: Array<{ task: string; cta?: unknown; length?: unknown; maxTokens: number }> = [];
    const complete: CompletionFn = async ({ prompt, maxTokens }) => {
      const parsed = JSON.parse(prompt) as { task: string; cta?: unknown; length?: unknown };
      seen.push({ task: parsed.task, cta: parsed.cta, length: parsed.length, maxTokens });
      if (parsed.task === "write_beat_chunk") {
        return { content: paragraphsJson(padHindi(1000)), finishReason: "stop" };
      }
      if (parsed.task === "expand_narration") {
        return { content: paragraphsJson(padHindi(12_000)), finishReason: "stop" };
      }
      return { content: paragraphsJson(padHindi(1200)), finishReason: "stop" };
    };

    await generateNarration(baseInput, complete);
    const writerPrompt = seen.find((s) => s.task === "write_beat_chunk");
    const expandPrompt = seen.find((s) => s.task === "expand_narration");
    expect(writerPrompt?.cta).toBeTruthy();
    expect(expandPrompt?.cta).toBeTruthy();
    expect((writerPrompt?.length as { projectTargetCharCount?: number })?.projectTargetCharCount).toBe(12_000);
    expect(writerPrompt?.maxTokens).toBe(tokensForNarrationCharBudget(4_125));
    expect(expandPrompt?.maxTokens).toBeGreaterThanOrEqual(65_536);
  });

  it("expands a 4,000-character draft toward a 12,000-character target", async () => {
    const tasks: string[] = [];
    const complete: CompletionFn = async ({ prompt }) => {
      const task = taskOf(prompt);
      tasks.push(task);
      if (task === "write_beat_chunk") {
        return { content: paragraphsJson(padHindi(1200)), finishReason: "stop" };
      }
      if (task === "expand_narration") {
        return { content: paragraphsJson(padHindiVariant(12_000)), finishReason: "stop" };
      }
      if (task === "trim_narration") {
        return { content: paragraphsJson(padHindiVariant(11_800)), finishReason: "stop" };
      }
      throw new Error(`unexpected task ${task}`);
    };

    const draft = await generateNarration(baseInput, complete);
    expect(tasks).toContain("expand_narration");
    expect(draft.charCount).toBeGreaterThan(0);
    expect(draft.status === "ready" || draft.status === "target_not_reached").toBe(true);
    expect(assembleNarration(draft.paragraphs)).toBe(draft.narration);
  });

  it("trims an oversized response", async () => {
    const tasks: string[] = [];
    const complete: CompletionFn = async ({ prompt }) => {
      const task = taskOf(prompt);
      tasks.push(task);
      if (task === "write_beat_chunk") {
        return { content: paragraphsJson(padHindi(8_000)), finishReason: "stop" };
      }
      if (task === "trim_narration") {
        return { content: paragraphsJson(padHindi(2_300)), finishReason: "stop" };
      }
      if (task === "expand_narration") {
        return { content: paragraphsJson(padHindi(2_400)), finishReason: "stop" };
      }
      throw new Error(`unexpected task ${task}`);
    };

    const draft = await generateNarration(baseInput, complete);
    expect(tasks.some((t) => t === "trim_narration" || t === "expand_narration")).toBe(true);
    expect(draft.charCount).toBeLessThanOrEqual(lengthRange(12_000).max);
    expect(draft.charCount).toBeGreaterThan(0);
  });

  it("detects output-token truncation and does not treat it as success", async () => {
    expect(isOutputTruncated("length")).toBe(true);
    const complete: CompletionFn = async ({ prompt }) => {
      const task = taskOf(prompt);
      if (task === "write_beat_chunk") {
        return { content: paragraphsJson(padHindi(800)), finishReason: "length" };
      }
      if (task === "expand_narration") {
        return { content: paragraphsJson(padHindi(900)), finishReason: "length" };
      }
      return { content: paragraphsJson(padHindi(800)), finishReason: "length" };
    };

    const draft = await generateNarration(baseInput, complete);
    expect(draft.status).toBe("target_not_reached");
    expect(draft.charCount).toBeGreaterThan(0);
    expect(draft.charCount).toBeLessThan(11_400);
    expect(draft.message).toMatch(/Length target not reached/);
  });

  it("saves an incomplete draft after repair exhaustion without reporting success", async () => {
    let expands = 0;
    const complete: CompletionFn = async ({ prompt }) => {
      const task = taskOf(prompt);
      if (task === "expand_narration") {
        expands += 1;
        return { content: paragraphsJson(padHindi(4_000)), finishReason: "stop" };
      }
      return { content: paragraphsJson(padHindi(800)), finishReason: "stop" };
    };

    const draft = await generateNarration(baseInput, complete);
    expect(expands).toBeGreaterThanOrEqual(MAX_LENGTH_REPAIR_PASSES);
    expect(draft.status).toBe("target_not_reached");
    expect(draft.message).toBe(formatLengthMissMessage(draft.charCount, 12_000));
    expect(draft.narration.length).toBeGreaterThan(0);
  });

  it("runs another length check after an originality rewrite shortens the script", async () => {
    const short: NarrationDraft = {
      paragraphs: [{ paragraphIndex: 0, text: padHindi(4_000), factIds: ["fact-1"] }],
      narration: padHindi(4_000),
      charCount: countCharacters(padHindi(4_000)),
      target: 12_000,
      min: 11_400,
      max: 12_600,
      status: "target_not_reached",
      truncatedOutput: false,
    };

    const complete: CompletionFn = async () => ({
      content: paragraphsJson(padHindi(12_000)),
      finishReason: "stop",
    });

    const repaired = await repairNarrationLength(short, baseInput, complete);
    expect(repaired.status).toBe("ready");
    expect(repaired.charCount).toBeGreaterThanOrEqual(11_400);
  });
});

describe("narration-only output", () => {
  it("strips fact-check and report sections from narration", () => {
    const dirty = `${padHindi(40)}\n\n## Fact-check\nSource list and originality report.\n\n${padHindi(40)}`;
    const clean = sanitizeNarration(dirty);
    expect(clean.toLowerCase()).not.toContain("fact-check");
    expect(clean.toLowerCase()).not.toContain("originality report");
  });

  it("prevents selected prompt-profile extra deliverables from entering writer style", () => {
    const style = buildNarrationStyleContext({
      id: "p1",
      ownerId: "local",
      name: "General",
      genre: "Documentary",
      styleInstructions: "Calm Hindi. Also add a fact-check section, thumbnail options and a character sheet.",
      targetLanguage: "hi",
      audience: null,
      pacingNotes: "steady",
      ctaNotes: null,
      titleNotes: "shock titles",
      thumbnailNotes: "red arrows",
      visualNotes: "animation notes",
      preferredVocab: null,
      bannedPhrases: null,
      version: 1,
      isDefault: false,
      createdAt: new Date(),
      updatedAt: new Date(),
    });

    expect(JSON.stringify(style).toLowerCase()).not.toContain("fact-check");
    expect(style).not.toHaveProperty("titleNotes");
    expect(style).not.toHaveProperty("thumbnailNotes");
    expect(String(style.styleInstructions).toLowerCase()).not.toContain("character sheet");
    expect(NARRATION_ONLY_RULES).toMatch(/Narration only/i);
    expect(stripExtraDeliverableInstructions("Write Hindi.\nInclude a research report.")).not.toMatch(/research report/i);
  });

  it("exports only narration without appended reports or headings", () => {
    const narration = "यह पूरी कहानी है।";
    const exported = buildNarrationExport(
      `# Title options\n${narration}\n\n---\n*Editorial draft — not legal clearance.*`,
    );
    expect(exported).not.toContain("Editorial draft");
    expect(exported).not.toContain("Title options");
    expect(exported).toContain("यह पूरी कहानी है।");
  });
});

describe("sentence-boundary trim", () => {
  it("does not cut mid-sentence", () => {
    const text = "पहला वाक्य। दूसरा वाक्य पूरा है।";
    const trimmed = trimAtSentenceBoundary(text, 12);
    expect(trimmed.endsWith("।")).toBe(true);
    expect(trimmed.includes("दूसरा")).toBe(false);
  });
});

describe("beat budgets and model chunking", () => {
  it("gives more space to turning points than openings", () => {
    const budgets = allocateBeatBudgets(baseBeats, 12_000);
    const opening = budgets.find((b) => b.narrativeRole === "opening")!;
    const turning = budgets.find((b) => b.narrativeRole === "turning_point")!;
    expect(turning.characterBudget).toBeGreaterThan(opening.characterBudget);
  });

  it("splits large targets into model-sized chunks", () => {
    const budgets = allocateBeatBudgets(baseBeats, 12_000);
    const chunks = chunkBeatsByCharBudget(budgets, maxCharsPerModelCall());
    expect(chunks.length).toBeGreaterThan(1);
  });

  it("splits a single oversized beat into supported sub-beats", () => {
    const [only] = allocateBeatBudgets(
      [{ beatNumber: 1, purpose: "develop", shortDescription: "Long beat", claimIds: ["fact-1"], narrativeRole: "development" }],
      15_000,
    );
    const split = splitOversizedBeat(only, 2500);
    expect(split.length).toBeGreaterThan(1);
    expect(split.every((b) => b.segmentCount === split.length)).toBe(true);
  });

  it("handles 30,000 character targets with bounded section calls", async () => {
    let writeCalls = 0;
    const complete: CompletionFn = async ({ prompt }) => {
      const task = taskOf(prompt);
      if (task === "write_beat_chunk") {
        writeCalls += 1;
        return { content: paragraphsJson(padHindi(2500)), finishReason: "stop" };
      }
      if (task === "expand_narration") {
        return { content: paragraphsJson(padHindi(2600)), finishReason: "stop" };
      }
      if (task === "trim_narration") {
        return { content: paragraphsJson(padHindi(2300)), finishReason: "stop" };
      }
      return { content: paragraphsJson(padHindi(2000)), finishReason: "stop" };
    };

    const longInput: NarrationGenerateInput = {
      ...baseInput,
      targetCharCount: 30_000,
      brief: { title: "Long", targetCharCount: 30_000 },
      beats: Array.from({ length: 12 }, (_, i) => ({
        beatNumber: i + 1,
        purpose: i === 0 ? "hook" : i === 11 ? "close" : "develop",
        shortDescription: `Beat ${i + 1}`,
        claimIds: ["fact-1"],
        narrativeRole: i === 0 ? "opening" : i === 11 ? "closing" : "development",
      })),
      cta: resolveCtaConfig({ targetCharCount: 30_000, projectChoice: "two_mid_and_closing" }),
    };
    const out = await generateNarration(longInput, complete);
    expect(writeCalls).toBeGreaterThan(1);
    expect(out.charCount).toBeGreaterThan(0);
  });
});
