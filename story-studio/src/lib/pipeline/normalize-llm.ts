/** Unwrap common LLM response wrappers and snake_case field names. */

function unwrapRoot(raw: unknown): Record<string, unknown> {
  if (!raw || typeof raw !== "object") return {};
  const record = raw as Record<string, unknown>;
  if (record.data && typeof record.data === "object") return record.data as Record<string, unknown>;
  if (record.result && typeof record.result === "object") return record.result as Record<string, unknown>;
  return record;
}

function asStringArray(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

export function coerceString(value: unknown, fallback: string): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

export function normalizeFingerprintPayload(raw: unknown): Record<string, unknown> {
  let obj = unwrapRoot(raw);
  const record = obj as Record<string, unknown>;
  if (record.fingerprint && typeof record.fingerprint === "object") {
    obj = record.fingerprint as Record<string, unknown>;
  }
  const o = obj as Record<string, unknown>;
  return {
    openingType: o.openingType ?? o.opening_type,
    openingFunction: o.openingFunction ?? o.opening_function,
    presentationOrder: o.presentationOrder ?? o.presentation_order,
    dominantNarrativeLens: o.dominantNarrativeLens ?? o.dominant_narrative_lens,
    turningPointType: o.turningPointType ?? o.turning_point_type,
    recurringDevices: o.recurringDevices ?? o.recurring_devices,
    distinctiveMetaphorsOrPhrases:
      o.distinctiveMetaphorsOrPhrases ?? o.distinctive_metaphors_or_phrases,
    endingFunction: o.endingFunction ?? o.ending_function,
    titleAndThumbnailPattern: o.titleAndThumbnailPattern ?? o.title_and_thumbnail_pattern,
  };
}

export function finalizeFingerprintFields(raw: Record<string, unknown>) {
  return {
    openingType: coerceString(raw.openingType, "unknown"),
    openingFunction: coerceString(raw.openingFunction, "unknown"),
    presentationOrder: asStringArray(raw.presentationOrder),
    dominantNarrativeLens: coerceString(raw.dominantNarrativeLens, "unknown"),
    turningPointType: coerceString(raw.turningPointType, "unknown"),
    recurringDevices: asStringArray(raw.recurringDevices),
    distinctiveMetaphorsOrPhrases: asStringArray(raw.distinctiveMetaphorsOrPhrases),
    endingFunction: coerceString(raw.endingFunction, "unknown"),
    titleAndThumbnailPattern: coerceString(raw.titleAndThumbnailPattern, "unknown"),
  };
}

export function normalizeClaimsPayload(raw: unknown): { claims: unknown[] } {
  const o = unwrapRoot(raw);
  const claims = o.claims ?? o.items ?? o.results;
  if (Array.isArray(claims)) return { claims };
  if (o.neutralClaim || o.claim) return { claims: [o] };
  return { claims: [] };
}

export function normalizeFactPackPayload(raw: unknown): { facts: unknown[] } {
  const o = unwrapRoot(raw);
  const facts = o.facts ?? o.factPack ?? o.items;
  if (Array.isArray(facts)) return { facts };
  if (o.factId || o.neutralStatement) return { facts: [o] };
  return { facts: [] };
}

function pickField(record: Record<string, unknown>, keys: string[]): unknown {
  for (const key of keys) {
    if (record[key] !== undefined && record[key] !== null) return record[key];
  }
  return undefined;
}

function inferPurposeFromText(text: string, index: number): string {
  const match = text.match(/^(hook|develop|turn|close|context|climax)\b/i);
  if (match) return match[1].toLowerCase();
  if (index === 0) return "hook";
  if (index >= 6) return "close";
  return "develop";
}

function inferRoleFromPurpose(purpose: string, index: number): string {
  if (purpose === "hook" || index === 0) return "opening";
  if (purpose === "close") return "closing";
  return "development";
}

function normalizeBeat(raw: unknown, index: number): Record<string, unknown> {
  if (typeof raw === "string") {
    const text = raw.trim();
    const purpose = inferPurposeFromText(text, index);
    const shortDescription = text.replace(/^\d+[\).\s-]+/, "").trim() || text;
    return {
      beatNumber: index + 1,
      purpose,
      shortDescription,
      claimIds: [],
      narrativeRole: inferRoleFromPurpose(purpose, index),
    };
  }

  const b = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const claimIds = pickField(b, ["claimIds", "factIds", "claim_ids", "fact_ids", "facts"]);
  const duration = pickField(b, ["expectedDurationSeconds", "duration", "expected_duration_seconds"]);
  let shortDescription = pickField(b, [
    "shortDescription",
    "short_description",
    "description",
    "summary",
    "title",
    "text",
    "content",
    "beat",
    "beatDescription",
    "beat_description",
  ]);
  if (!shortDescription) {
    const firstString = Object.values(b).find((v) => typeof v === "string" && v.trim());
    shortDescription = firstString;
  }
  const purpose = coerceString(pickField(b, ["purpose", "beatPurpose", "beat_purpose"]), inferPurposeFromText(String(shortDescription ?? ""), index));
  return {
    beatNumber:
      typeof b.beatNumber === "number"
        ? b.beatNumber
        : typeof b.beat_number === "number"
          ? b.beat_number
          : index + 1,
    purpose,
    shortDescription: coerceString(shortDescription, `Story beat ${index + 1}`),
    claimIds: asStringArray(claimIds),
    narrativeRole: coerceString(
      pickField(b, ["narrativeRole", "narrative_role", "role"]),
      inferRoleFromPurpose(purpose, index),
    ),
    proposedVisualIdea: pickField(b, ["proposedVisualIdea", "visualIdea", "visual", "proposed_visual_idea"]),
    expectedDurationSeconds: typeof duration === "number" ? duration : undefined,
  };
}

export function finalizeBeatFields(raw: Record<string, unknown>, index: number) {
  return {
    beatNumber: typeof raw.beatNumber === "number" ? raw.beatNumber : index + 1,
    purpose: coerceString(raw.purpose, "develop"),
    shortDescription: coerceString(raw.shortDescription, "Story beat"),
    claimIds: asStringArray(raw.claimIds),
    narrativeRole: coerceString(raw.narrativeRole, "development"),
    proposedVisualIdea:
      typeof raw.proposedVisualIdea === "string" ? raw.proposedVisualIdea : undefined,
    expectedDurationSeconds:
      typeof raw.expectedDurationSeconds === "number" ? raw.expectedDurationSeconds : undefined,
  };
}

function normalizeTreatment(raw: unknown, index: number): Record<string, unknown> {
  const t = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const beatsRaw = pickField(t, ["beats", "outline", "sections", "narrativeBeats", "narrative_beats"]);
  const beats = Array.isArray(beatsRaw)
    ? beatsRaw.map((beat, i) => finalizeBeatFields(normalizeBeat(beat, i), i))
    : [];

  return finalizeTreatmentFields(
    {
      centralQuestion: pickField(t, [
        "centralQuestion",
        "central_question",
        "question",
        "coreQuestion",
        "core_question",
        "title",
      ]),
      openingApproach: pickField(t, [
        "openingApproach",
        "opening_approach",
        "opening",
        "openingStrategy",
        "opening_strategy",
        "openingHook",
        "opening_hook",
      ]),
      narrativeLens: pickField(t, [
        "narrativeLens",
        "narrative_lens",
        "lens",
        "narrativeRoute",
        "narrative_route",
        "structure",
        "angle",
      ]),
      diffExplanation: pickField(t, [
        "diffExplanation",
        "diff_explanation",
        "rationale",
        "differentiation",
        "whyDifferent",
        "why_different",
      ]),
      beats,
    },
    index,
  );
}

export function finalizeTreatmentFields(raw: Record<string, unknown>, index: number) {
  const beatsRaw = Array.isArray(raw.beats) ? raw.beats : [];
  const beats = beatsRaw.map((beat, i) => finalizeBeatFields(normalizeBeat(beat, i), i));

  return {
    centralQuestion: coerceString(raw.centralQuestion, `Treatment ${index + 1}`),
    openingApproach: coerceString(raw.openingApproach, "Fresh contextual opening"),
    narrativeLens: coerceString(raw.narrativeLens, "explanatory"),
    diffExplanation: coerceString(
      raw.diffExplanation,
      "Distinct from source storytelling patterns.",
    ),
    beats,
  };
}

export function normalizeNarrativePlansPayload(raw: unknown): { treatments: Record<string, unknown>[] } {
  const o = unwrapRoot(raw);
  let treatments = pickField(o, ["treatments", "narrativePlans", "plans", "options", "narrative_plans"]);
  if (!Array.isArray(treatments) && (o.centralQuestion || o.central_question || o.beats)) {
    treatments = [o];
  }
  const list = Array.isArray(treatments) ? treatments : [];
  return { treatments: list.map((t, i) => normalizeTreatment(t, i)) };
}

function salvageStringBeatArray(raw: unknown): unknown[] | null {
  if (!Array.isArray(raw)) return null;
  if (raw.every((item) => typeof item === "string" && item.trim())) return raw;
  return null;
}

/** Parse narrative plans leniently — always returns structurally valid treatments when possible. */
export function parseNarrativePlansLenient(raw: unknown): {
  treatments: Array<{
    centralQuestion: string;
    openingApproach: string;
    narrativeLens: string;
    diffExplanation: string;
    beats: Array<{
      beatNumber: number;
      purpose: string;
      shortDescription: string;
      claimIds: string[];
      narrativeRole: string;
      proposedVisualIdea?: string;
      expectedDurationSeconds?: number;
    }>;
  }>;
} {
  const o = unwrapRoot(raw);
  let treatmentsRaw = pickField(o, ["treatments", "narrativePlans", "plans", "options", "narrative_plans"]);
  if (!Array.isArray(treatmentsRaw) && (o.centralQuestion || o.central_question || o.beats)) {
    treatmentsRaw = [o];
  }

  const treatments = (Array.isArray(treatmentsRaw) ? treatmentsRaw : []).map((treatment, i) => {
    const record = (treatment && typeof treatment === "object" ? treatment : {}) as Record<string, unknown>;
    const beatsRaw = pickField(record, ["beats", "outline", "sections", "narrativeBeats", "narrative_beats"]);
    const stringBeats = salvageStringBeatArray(beatsRaw);
    const beats = stringBeats
      ? stringBeats.map((beat, beatIndex) => finalizeBeatFields(normalizeBeat(beat, beatIndex), beatIndex))
      : undefined;

    return finalizeTreatmentFields(
      {
        ...record,
        ...(beats ? { beats } : {}),
      },
      i,
    );
  }).filter((t) => t.beats.length > 0);

  if (treatments.length === 0) {
    throw new Error("No usable narrative treatments in LLM response.");
  }

  return { treatments: treatments.slice(0, 3) };
}

export function normalizeScriptPayload(raw: unknown): Record<string, unknown> {
  const o = unwrapRoot(raw);
  const paragraphs = o.paragraphs ?? o.traces ?? o.sections;
  return {
    narration: o.narration ?? o.script ?? o.content ?? "",
    paragraphs: Array.isArray(paragraphs) ? paragraphs : [],
  };
}

export function parseBeatParagraphs(raw: unknown): Array<{ beatNumber?: number; text: string; factIds: string[] }> {
  const o = unwrapRoot(raw);
  let paragraphs = o.paragraphs ?? o.traces ?? o.sections;
  if (typeof o.text === "string" && !paragraphs) {
    paragraphs = [{ text: o.text, factIds: o.factIds }];
  }
  if (!Array.isArray(paragraphs) && typeof o.narration === "string") {
    paragraphs = String(o.narration)
      .split(/\n{2,}/)
      .filter(Boolean)
      .map((text) => ({ text }));
  }
  if (!Array.isArray(paragraphs)) return [];

  return paragraphs
    .map((item, i) => {
      if (typeof item === "string") {
        return { beatNumber: i + 1, text: item.trim(), factIds: [] as string[] };
      }
      const row = (item && typeof item === "object" ? item : {}) as Record<string, unknown>;
      const factIds = row.factIds ?? row.fact_ids ?? row.claimIds;
      return {
        beatNumber: typeof row.beatNumber === "number" ? row.beatNumber : i + 1,
        text: coerceString(row.text ?? row.paragraphText ?? row.content, ""),
        factIds: asStringArray(factIds),
      };
    })
    .filter((p) => p.text.trim().length > 0);
}
