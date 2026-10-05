export interface FingerprintLike {
  openingType: string;
  openingFunction: string;
  presentationOrder: string[];
  dominantNarrativeLens: string;
  turningPointType: string;
  endingFunction: string;
  recurringDevices: string[];
}

export function structuralOverlapScore(
  plan: {
    openingApproach: string;
    narrativeLens: string;
    beats: Array<{ shortDescription: string }>;
  },
  fingerprint: FingerprintLike,
): number {
  let overlap = 0;
  let checks = 0;

  if (similar(plan.openingApproach, fingerprint.openingType)) overlap += 1;
  checks += 1;
  if (similar(plan.narrativeLens, fingerprint.dominantNarrativeLens)) overlap += 1;
  checks += 1;

  const planOrder = plan.beats.map((b) => b.shortDescription.slice(0, 40).toLowerCase());
  const fpOrder = fingerprint.presentationOrder.map((x) => x.toLowerCase());
  const orderSim = jaccard(planOrder, fpOrder);
  overlap += orderSim;
  checks += 1;

  return overlap / checks;
}

function similar(a: string, b: string): boolean {
  const na = a.toLowerCase().trim();
  const nb = b.toLowerCase().trim();
  return na === nb || na.includes(nb) || nb.includes(na);
}

function jaccard(a: string[], b: string[]): number {
  const setA = new Set(a);
  const setB = new Set(b);
  const intersection = [...setA].filter((x) => setB.has(x)).length;
  const union = new Set([...setA, ...setB]).size;
  return union === 0 ? 0 : intersection / union;
}

export function structuralStatus(score: number): "pass" | "warn" | "fail" {
  if (score > 0.55) return "fail";
  if (score > 0.35) return "warn";
  return "pass";
}
