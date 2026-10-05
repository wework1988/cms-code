import type { ChannelStyleProfile, PromptProfile } from "@prisma/client";
import { resolveTargetCharCount } from "@/lib/narration/count";

export const CTA_MODES = [
  "closing_only",
  "one_mid_and_closing",
  "two_mid_and_closing",
] as const;

export type CtaMode = (typeof CTA_MODES)[number];

export type ResolvedCtaConfig = {
  mode: CtaMode;
  midCountRequested: number;
  midCountEffective: number;
  closingRequired: boolean;
  channelName?: string;
  preferredClosingWording?: string;
  channelSignOff?: string;
  source: "project" | "profile" | "channel" | "default";
  placementNote?: string;
};

type ResolveInput = {
  targetCharCount?: number | null;
  projectChoice?: string | null;
  projectChannelName?: string | null;
  projectClosingWording?: string | null;
  promptProfile?: PromptProfile | null;
  channelStyle?: ChannelStyleProfile | null;
};

function coerceMode(value: string | null | undefined): CtaMode | null {
  if (!value) return null;
  const normalized = value.trim().toLowerCase();
  if (normalized === "closing_only") return "closing_only";
  if (normalized === "one_mid_and_closing") return "one_mid_and_closing";
  if (normalized === "two_mid_and_closing") return "two_mid_and_closing";
  return null;
}

function modeFromPromptNotes(notes: string | null | undefined): CtaMode | null {
  if (!notes) return null;
  const text = notes.toLowerCase();
  if (text.includes("closing only") || text.includes("केवल क्लोजिंग")) return "closing_only";
  if (text.includes("two mid") || text.includes("2 mid")) return "two_mid_and_closing";
  if (text.includes("one mid") || text.includes("1 mid")) return "one_mid_and_closing";
  return null;
}

function requestedMidCount(mode: CtaMode): number {
  if (mode === "closing_only") return 0;
  if (mode === "two_mid_and_closing") return 2;
  return 1;
}

function isUsableClosingWording(value: string | null | undefined): boolean {
  if (!value?.trim()) return false;
  return /सब्सक्राइब|subscribe|चैनल|कमेंट|टिप्पणी|लाइक|share|शेयर|जुड़/i.test(value);
}

export function resolveCtaConfig(input: ResolveInput): ResolvedCtaConfig {
  const target = resolveTargetCharCount(input.targetCharCount);
  const explicitMode = coerceMode(input.projectChoice);
  const promptMode = modeFromPromptNotes(input.promptProfile?.ctaNotes);
  const channelMode = modeFromPromptNotes(input.channelStyle?.channelCta);

  const mode: CtaMode =
    explicitMode ??
    promptMode ??
    channelMode ??
    "one_mid_and_closing";

  const source: ResolvedCtaConfig["source"] = explicitMode
    ? "project"
    : promptMode
      ? "profile"
      : channelMode
        ? "channel"
        : "default";

  const channelName =
    input.projectChannelName?.trim() ||
    input.channelStyle?.name?.trim() ||
    undefined;

  const preferredClosingWording =
    [input.projectClosingWording, input.promptProfile?.ctaNotes, input.channelStyle?.channelCta]
      .map((value) => value?.trim())
      .find(isUsableClosingWording) ||
    undefined;

  let midCountEffective = requestedMidCount(mode);
  let placementNote: string | undefined;

  if (mode === "two_mid_and_closing" && target < 7000) {
    midCountEffective = 1;
    placementNote = "Story length is shorter than ideal for three CTAs; used one middle CTA and one closing CTA.";
  }

  return {
    mode,
    midCountRequested: requestedMidCount(mode),
    midCountEffective,
    closingRequired: true,
    channelName,
    preferredClosingWording,
    channelSignOff: input.channelStyle?.signOff?.trim() || undefined,
    source,
    placementNote,
  };
}

export function ctaModeDescription(mode: CtaMode): string {
  if (mode === "closing_only") return "Closing CTA only";
  if (mode === "two_mid_and_closing") return "Two mid-story CTAs plus closing CTA";
  return "One mid-story CTA plus closing CTA";
}
