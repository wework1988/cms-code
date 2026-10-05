export type BudgetBeat = {
  beatNumber: number;
  purpose: string;
  shortDescription: string;
  claimIds: string[];
  narrativeRole: string;
  characterBudget: number;
  segmentIndex?: number;
  segmentCount?: number;
};

const ROLE_WEIGHT: Record<string, number> = {
  opening: 0.7,
  hook: 0.7,
  closing: 0.85,
  close: 0.85,
  turning_point: 1.35,
  turn: 1.35,
  climax: 1.35,
  development: 1.15,
  develop: 1.15,
  analysis: 1.2,
  evidence: 1.15,
  system: 1.15,
  setup: 0.95,
  context: 0.95,
  bridge: 0.8,
  reflection: 0.9,
};

export function beatWeight(beat: { purpose: string; narrativeRole: string }): number {
  const role = beat.narrativeRole.toLowerCase();
  const purpose = beat.purpose.toLowerCase();
  return ROLE_WEIGHT[role] ?? ROLE_WEIGHT[purpose] ?? 1;
}

export function allocateBeatBudgets(
  beats: Array<{
    beatNumber: number;
    purpose: string;
    shortDescription: string;
    claimIds: string[];
    narrativeRole: string;
  }>,
  targetChars: number,
  separatorChars = 2,
): BudgetBeat[] {
  if (beats.length === 0) return [];

  const separatorTotal = Math.max(0, beats.length - 1) * separatorChars;
  const bodyTarget = Math.max(beats.length * 80, targetChars - separatorTotal);
  const weights = beats.map((b) => beatWeight(b));
  const weightSum = weights.reduce((a, b) => a + b, 0) || beats.length;

  const allocated = beats.map((beat, i) => ({
    ...beat,
    characterBudget: Math.max(80, Math.round((weights[i] / weightSum) * bodyTarget)),
  }));

  const drift = bodyTarget - allocated.reduce((sum, b) => sum + b.characterBudget, 0);
  if (drift !== 0) {
    const richest = allocated.reduce((best, b) => (b.characterBudget > best.characterBudget ? b : best));
    richest.characterBudget = Math.max(80, richest.characterBudget + drift);
  }

  return allocated;
}

export function chunkBeatsByCharBudget<T extends { characterBudget: number }>(
  beats: T[],
  maxCharsPerCall: number,
): T[][] {
  if (beats.length === 0) return [];
  const limit = Math.max(200, maxCharsPerCall);
  const chunks: T[][] = [];
  let current: T[] = [];
  let used = 0;

  for (const beat of beats) {
    const cost = beat.characterBudget;
    if (current.length > 0 && used + cost > limit) {
      chunks.push(current);
      current = [];
      used = 0;
    }
    current.push(beat);
    used += cost;
    if (cost >= limit && current.length === 1) {
      chunks.push(current);
      current = [];
      used = 0;
    }
  }

  if (current.length > 0) chunks.push(current);
  return chunks;
}

export function splitOversizedBeat(
  beat: BudgetBeat,
  maxChunkChars: number,
  minChunkChars = 700,
): BudgetBeat[] {
  if (beat.characterBudget <= maxChunkChars) return [beat];
  const safeMax = Math.max(minChunkChars, maxChunkChars);
  const parts = Math.max(2, Math.ceil(beat.characterBudget / safeMax));
  const base = Math.floor(beat.characterBudget / parts);
  const remainder = beat.characterBudget % parts;

  return Array.from({ length: parts }, (_, i) => {
    const budget = base + (i < remainder ? 1 : 0);
    return {
      ...beat,
      characterBudget: Math.max(minChunkChars, budget),
      shortDescription: `${beat.shortDescription} (part ${i + 1}/${parts})`,
      segmentIndex: i + 1,
      segmentCount: parts,
    };
  });
}
