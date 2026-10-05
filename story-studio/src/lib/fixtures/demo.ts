import type { Claim, NarrativeTreatment, ScriptResponse } from "@/lib/schemas";
import type { OriginalityAnalysisResult } from "@/lib/originality/analyzer";

export function loadDemoFixture(sourceIds?: [string, string]) {
  const source1 = sourceIds?.[0] ?? "placeholder-source-1";
  const source2 = sourceIds?.[1] ?? "placeholder-source-2";

  const claims: Claim[] = [
    {
      id: "claim-001",
      sourceId: source1,
      neutralClaim: "1600 में Queen Elizabeth I ने East India Company को व्यापारिक अनुमति दी।",
      claimType: "date",
      peoplePlacesDatesNumbers: "1600, Queen Elizabeth I, East India Company",
      timestampStart: 12,
      timestampEnd: 28,
      supportExcerpt: "[producer only]",
      sourceCertainty: "explicit",
      storyRelevance: "high",
      requiredByUser: false,
    },
    {
      id: "claim-002",
      sourceId: source1,
      neutralClaim: "Company को भारत में व्यापारिक अनुमति मिलने से पहले व्यापारिक monopoly का लक्ष्य था।",
      claimType: "background",
      peoplePlacesDatesNumbers: "East India Company, India trade",
      supportExcerpt: "[producer only]",
      sourceCertainty: "explicit",
      storyRelevance: "high",
      requiredByUser: false,
    },
    {
      id: "claim-003",
      sourceId: source2,
      neutralClaim: "1757 की Plassey की लड़ाई Company की सैन्य शक्ति बढ़ाने का महत्वपूर्ण मोड़ थी।",
      claimType: "event",
      peoplePlacesDatesNumbers: "1757, Battle of Plassey",
      supportExcerpt: "[producer only]",
      sourceCertainty: "explicit",
      storyRelevance: "high",
      requiredByUser: true,
    },
    {
      id: "claim-004",
      sourceId: source2,
      neutralClaim: "Company का शासन प्रशासनिक और सैन्य दोनों तंत्रों पर निर्भर था।",
      claimType: "interpretation",
      supportExcerpt: "[producer only]",
      sourceCertainty: "ambiguous",
      storyRelevance: "medium",
      requiredByUser: false,
    },
  ];

  const treatments: NarrativeTreatment[] = [
    {
      centralQuestion: "एक व्यापारिक संस्था राजनीतिक साम्राज्य कैसे बन गई?",
      openingApproach: "आज के corporate power से तुलना करके शुरुआत",
      narrativeLens: "institution",
      diffExplanation: "Sources open with dramatic battle; this opens with institutional logic.",
      beats: [
        { beatNumber: 1, purpose: "hook", shortDescription: "Modern corporation vs historic company", claimIds: ["fact-001"], narrativeRole: "opening", expectedDurationSeconds: 45 },
        { beatNumber: 2, purpose: "context", shortDescription: "Royal charter and trade monopoly aim", claimIds: ["fact-001", "fact-002"], narrativeRole: "setup", expectedDurationSeconds: 60 },
        { beatNumber: 3, purpose: "turn", shortDescription: "From trade permission to military leverage", claimIds: ["fact-003"], narrativeRole: "turning_point", expectedDurationSeconds: 75 },
        { beatNumber: 4, purpose: "system", shortDescription: "Administrative and military dependence", claimIds: ["fact-004"], narrativeRole: "analysis", expectedDurationSeconds: 60 },
        { beatNumber: 5, purpose: "close", shortDescription: "Legacy question for viewers", claimIds: ["fact-003"], narrativeRole: "closing", expectedDurationSeconds: 40 },
        { beatNumber: 6, purpose: "bridge", shortDescription: "Trade to governance shift", claimIds: ["fact-002"], narrativeRole: "bridge", expectedDurationSeconds: 30 },
        { beatNumber: 7, purpose: "evidence", shortDescription: "Charter date anchor", claimIds: ["fact-001"], narrativeRole: "evidence", expectedDurationSeconds: 25 },
        { beatNumber: 8, purpose: "reflection", shortDescription: "Institutional drift question", claimIds: ["fact-004"], narrativeRole: "reflection", expectedDurationSeconds: 35 },
      ],
    },
    {
      centralQuestion: "Plassey से पहले Company क्या थी — और बाद में क्या बन गई?",
      openingApproach: "Consequence-first: post-Plassey power, then rewind",
      narrativeLens: "timeline",
      diffExplanation: "Inverts source chronology with consequence-first frame.",
      beats: [
        { beatNumber: 1, purpose: "hook", shortDescription: "Post-1757 power snapshot", claimIds: ["fact-003"], narrativeRole: "opening", expectedDurationSeconds: 40 },
        { beatNumber: 2, purpose: "rewind", shortDescription: "1600 charter context", claimIds: ["fact-001"], narrativeRole: "context", expectedDurationSeconds: 55 },
        { beatNumber: 3, purpose: "build", shortDescription: "Trade monopoly ambition", claimIds: ["fact-002"], narrativeRole: "development", expectedDurationSeconds: 50 },
        { beatNumber: 4, purpose: "pivot", shortDescription: "Military-administrative machinery", claimIds: ["fact-004"], narrativeRole: "analysis", expectedDurationSeconds: 55 },
        { beatNumber: 5, purpose: "close", shortDescription: "Open question on institutional drift", claimIds: ["fact-003"], narrativeRole: "closing", expectedDurationSeconds: 35 },
        { beatNumber: 6, purpose: "bridge", shortDescription: "From trader to ruler", claimIds: ["fact-002"], narrativeRole: "bridge", expectedDurationSeconds: 30 },
        { beatNumber: 7, purpose: "evidence", shortDescription: "Plassey as pivot", claimIds: ["fact-003"], narrativeRole: "evidence", expectedDurationSeconds: 25 },
        { beatNumber: 8, purpose: "reflection", shortDescription: "What changed after 1757", claimIds: ["fact-004"], narrativeRole: "reflection", expectedDurationSeconds: 35 },
      ],
    },
  ];

  const script: ScriptResponse = {
    narration: `कल्पना कीजिए: कोई कंपनी सिर्फ माल बेचने के लिए बनी हो, और कुछ दशकों बाद वही संस्था राजनीतिक फैसले लेने लगे। East India Company की कहानी ठीक यहीं से शुरू होती है — न किसी युद्ध के नाटक से, बल्कि एक अनुमति पत्र से।

1600 में Queen Elizabeth I ने इस Company को व्यापार की formal permission दी। उस समय का लक्ष्य साफ था: भारत से माल लाना और Europe में बेचना। लेकिन monopoly की hunger धीरे-धीरे institution को बदलने लगी।

1757 की Plassey की लड़ाई इस बदलाव का visible मोड़ बनी। अब Company सिर्फ trader नहीं, बल्कि एक सैन्य-प्रशासनिक force के रूप में उभरी। यही वह point है जहाँ trade permission, long-term political control में convert होती दिखती है।

आज जब हम corporate power पर बहस करते हैं, तो East India Company एक पुराना लेकिन relevant example है: जब profit, permission और force एक साथ चलें, तो institution का character बदल सकता है।`,
    paragraphs: [
      { paragraphIndex: 0, text: "कल्पना कीजिए...", factIds: ["fact-001"] },
      { paragraphIndex: 1, text: "1600 में Queen Elizabeth...", factIds: ["fact-001", "fact-002"] },
      { paragraphIndex: 2, text: "1757 की Plassey...", factIds: ["fact-003"] },
      { paragraphIndex: 3, text: "आज जब हम corporate power...", factIds: ["fact-004"] },
    ],
  };

  const originality: OriginalityAnalysisResult = {
    overallStatus: "pass",
    phraseOverlap: "pass",
    hookSimilarity: "pass",
    orderSimilarity: "pass",
    metaphorWarnings: [],
    unsupportedClaims: [],
    recommendedAction: "Pass — editorial originality check only, not legal clearance.",
    exportBlocked: false,
    findings: [
      {
        category: "structure",
        severity: "low",
        explanation: "Opening uses institutional comparison rather than source battle hook.",
        affectedSection: "Paragraph 1",
      },
    ],
  };

  return {
    sourceIds: [source1, source2] as [string, string],
    claims,
    fingerprints: [
      {
        sourceId: source1,
        openingType: "dramatic_question",
        openingFunction: "curiosity_hook",
        presentationOrder: ["charter", "trade", "monopoly"],
        presentationOrderFactIds: ["fact-001", "fact-002"],
        dominantNarrativeLens: "chronology",
        turningPointType: "battle",
        recurringDevices: ["rhetorical questions"],
        distinctiveMetaphorsOrPhrases: ["empire in a boardroom"],
        endingFunction: "moral_summary",
        titleAndThumbnailPattern: "shock_title",
      },
      {
        sourceId: source2,
        openingType: "battle_scene",
        openingFunction: "high_stakes",
        presentationOrder: ["plassey", "expansion", "administration"],
        presentationOrderFactIds: ["fact-003", "fact-004"],
        dominantNarrativeLens: "military",
        turningPointType: "victory",
        recurringDevices: ["countdown"],
        distinctiveMetaphorsOrPhrases: ["company army"],
        endingFunction: "legacy_question",
        titleAndThumbnailPattern: "before_after",
      },
    ],
    treatments,
    script,
    originality,
    demoSources: [
      {
        kind: "pasted" as const,
        title: "Demo Source — Charter Era",
        transcript: "[00:12] In 1600, Queen Elizabeth granted the East India Company a royal charter...",
        sourceLabel: "Demo transcript 1",
      },
      {
        kind: "pasted" as const,
        title: "Demo Source — Plassey Era",
        transcript: "[02:05] The Battle of Plassey in 1757 marked a turning point for company rule...",
        sourceLabel: "Demo transcript 2",
      },
    ],
  };
}
