import { describe, expect, it } from "vitest";
import { resolveCtaConfig } from "@/lib/cta/config";
import {
  buildClosingCtaText,
  buildMidCtaText,
  ctaContainsFactualAssertion,
  detectCtaParagraphs,
  recommendedMidIndices,
  validateCtaCoverage,
} from "@/lib/cta/validation";

describe("CTA configuration resolution", () => {
  it("uses safe defaults for existing projects with unset CTA fields", () => {
    const resolved = resolveCtaConfig({
      targetCharCount: 6000,
      projectChoice: null,
      promptProfile: null,
      channelStyle: null,
    });

    expect(resolved.mode).toBe("one_mid_and_closing");
    expect(resolved.midCountEffective).toBe(1);
    expect(resolved.source).toBe("default");
  });

  it("applies precedence: project > profile > channel > default", () => {
    const profileFirst = resolveCtaConfig({
      targetCharCount: 9000,
      projectChoice: null,
      promptProfile: {
        id: "p",
        ownerId: "u",
        name: "Profile",
        genre: null,
        styleInstructions: "x",
        targetLanguage: "hi",
        audience: null,
        pacingNotes: null,
        ctaNotes: "two mid",
        titleNotes: null,
        thumbnailNotes: null,
        visualNotes: null,
        preferredVocab: null,
        bannedPhrases: null,
        version: 1,
        isDefault: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
      channelStyle: {
        id: "c",
        ownerId: "u",
        name: "Channel",
        defaultLanguage: "hi",
        audience: null,
        vocabularyNotes: null,
        charsPerMinute: 900,
        tonePreset: "explanatory",
        bannedPhrases: null,
        preferredPhrases: null,
        channelCta: "closing only",
        signOff: null,
        styleExamples: null,
        isDefault: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });
    expect(profileFirst.mode).toBe("two_mid_and_closing");
    expect(profileFirst.source).toBe("profile");

    const projectFirst = resolveCtaConfig({
      targetCharCount: 9000,
      projectChoice: "closing_only",
      promptProfile: null,
      channelStyle: null,
    });
    expect(projectFirst.mode).toBe("closing_only");
    expect(projectFirst.source).toBe("project");
  });

  it("downgrades two-mid mode for short stories", () => {
    const resolved = resolveCtaConfig({
      targetCharCount: 5000,
      projectChoice: "two_mid_and_closing",
      promptProfile: null,
      channelStyle: null,
    });
    expect(resolved.midCountRequested).toBe(2);
    expect(resolved.midCountEffective).toBe(1);
    expect(resolved.placementNote).toMatch(/shorter/i);
  });

  it("does not treat a bare channel teaser as a complete closing CTA", () => {
    const resolved = resolveCtaConfig({
      targetCharCount: 12000,
      projectChoice: "closing_only",
      channelStyle: {
        id: "c",
        ownerId: "u",
        name: "Channel",
        defaultLanguage: "hi",
        audience: null,
        vocabularyNotes: null,
        charsPerMinute: 900,
        tonePreset: "explanatory",
        bannedPhrases: null,
        preferredPhrases: null,
        channelCta: "अगली कड़ी में",
        signOff: null,
        styleExamples: null,
        isDefault: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });
    expect(resolved.preferredClosingWording).toBeUndefined();
    expect(buildClosingCtaText(resolved)).toContain("सब्सक्राइब");
  });
});

describe("CTA validation and placement", () => {
  const paragraphs = [
    { paragraphIndex: 0, text: "यह शुरुआत है।", factIds: ["f1"] },
    { paragraphIndex: 1, text: "घटना का संदर्भ और पृष्ठभूमि।", factIds: ["f1"] },
    { paragraphIndex: 2, text: "निर्णय और परिणाम का मोड़।", factIds: ["f2"] },
    { paragraphIndex: 3, text: "दीर्घकालिक प्रभाव।", factIds: ["f3"] },
    { paragraphIndex: 4, text: "अगर ऐसी कहानियां पसंद हैं तो चैनल को सब्सक्राइब करें।", factIds: [] },
  ];

  it("default mode expects one middle and one closing CTA", () => {
    const cfg = resolveCtaConfig({ targetCharCount: 12000, projectChoice: "one_mid_and_closing" });
    const withMid = [
      ...paragraphs.slice(0, 2),
      { paragraphIndex: 2, text: "इस मोड़ पर आपकी राय क्या है, कमेंट में बताइए।", factIds: [] },
      ...paragraphs.slice(2),
    ];
    const report = validateCtaCoverage(withMid, cfg);
    expect(report.midFound).toBeGreaterThanOrEqual(1);
    expect(report.closingFound).toBe(true);
  });

  it("closing-only mode does not require middle CTA", () => {
    const cfg = resolveCtaConfig({ targetCharCount: 6000, projectChoice: "closing_only" });
    const report = validateCtaCoverage(paragraphs, cfg);
    expect(report.closingFound).toBe(true);
  });

  it("places two-mid windows in distinct regions when possible", () => {
    const picks = recommendedMidIndices(
      [
        ...paragraphs,
        { paragraphIndex: 5, text: "आगे का विश्लेषण।", factIds: ["f3"] },
        { paragraphIndex: 6, text: "अंतिम निष्कर्ष।", factIds: ["f4"] },
      ],
      2,
    );
    expect(picks.length).toBeGreaterThan(0);
    expect(new Set(picks).size).toBe(picks.length);
  });

  it("detects duplicate CTA paragraphs", () => {
    const cfg = resolveCtaConfig({ targetCharCount: 12000, projectChoice: "one_mid_and_closing" });
    const duplicated = [
      ...paragraphs,
      { paragraphIndex: 5, text: "इस पर आपकी राय क्या है, कमेंट में बताइए।", factIds: [] },
      { paragraphIndex: 6, text: "इस पर आपकी राय क्या है, कमेंट में बताइए।", factIds: [] },
    ];
    const report = validateCtaCoverage(duplicated, cfg);
    expect(report.duplicateDetected).toBe(true);
  });

  it("identifies pure CTA vs factual CTA claim support requirement", () => {
    expect(ctaContainsFactualAssertion("आपकी राय क्या है, कमेंट में बताइए।")).toBe(false);
    expect(ctaContainsFactualAssertion("1962 के इस मोड़ पर आपकी राय क्या है?")).toBe(true);
  });

  it("supports channel sign-off reuse for closing CTA", () => {
    const cfg = resolveCtaConfig({
      targetCharCount: 10000,
      projectChoice: "closing_only",
      projectClosingWording: null,
      channelStyle: {
        id: "c",
        ownerId: "u",
        name: "Channel",
        defaultLanguage: "hi",
        audience: null,
        vocabularyNotes: null,
        charsPerMinute: 900,
        tonePreset: "explanatory",
        bannedPhrases: null,
        preferredPhrases: null,
        channelCta: null,
        signOff: "चैनल को सब्सक्राइब करके जुड़े रहिए।",
        styleExamples: null,
        isDefault: false,
        createdAt: new Date(),
        updatedAt: new Date(),
      },
    });
    expect(buildClosingCtaText(cfg)).toContain("सब्सक्राइब");
    const idx = detectCtaParagraphs([
      { paragraphIndex: 0, text: "कहानी का अंत।", factIds: [] },
      { paragraphIndex: 1, text: "चैनल को सब्सक्राइब करके जुड़े रहिए।", factIds: [] },
    ]);
    expect(idx).toHaveLength(1);
  });

  it("uses restrained wording for sensitive contexts", () => {
    const cta = buildMidCtaText("यह घटना कई पीड़ित परिवारों की त्रासदी से जुड़ी है", true);
    expect(cta).toMatch(/सम्मानजनक|शांत/);
  });
});
