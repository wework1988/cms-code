"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { estimateDurationSeconds } from "@/lib/utils";
import {
  countCharacters,
  lengthRange,
  lengthStatusLabel,
  resolveTargetCharCount,
  type LengthStatus,
} from "@/lib/narration/count";
import { CTA_MODES, type CtaMode, ctaModeDescription } from "@/lib/cta/config";
import { Input } from "@/components/ui/input";
import {
  approachLabel,
  GENRE_OPTIONS,
  hookLabel,
  isKnownGenre,
  legacyGoalToNarrativeApproach,
  NARRATIVE_APPROACH_OPTIONS,
  OPENING_HOOK_OPTIONS,
  type NarrativeApproachOption,
  type OpeningHookOption,
  type StoryGenreOption,
} from "@/lib/story-settings/options";

type ProjectData = {
  id: string;
  title: string;
  topic?: string | null;
  outputLanguage?: string | null;
  audience?: string | null;
  genre?: string | null;
  tone?: string | null;
  mustCoverPoints?: string | null;
  narrativeGoal?: string | null;
  narrativeApproachCustom?: string | null;
  openingHook?: string | null;
  openingHookCustom?: string | null;
  promptProfileId?: string | null;
  channelStyleId?: string | null;
  status: string;
  targetCharCount?: number | null;
  lengthStatus?: string | null;
  ctaPreference?: string | null;
  ctaChannelName?: string | null;
  ctaClosingWording?: string | null;
  exportOverride: boolean;
  errorMessage?: string | null;
  isDemo: boolean;
  promptProfile?: { id?: string; name: string; genre: string | null } | null;
  channelStyle?: { id?: string; name: string; tonePreset?: string | null } | null;
  sources: Array<{
    id: string;
    kind: string;
    title: string;
    videoId?: string | null;
    transcriptStatus: string;
    transcriptOrigin?: string | null;
    url?: string | null;
    rawTranscript?: string | null;
  }>;
  claims: Array<{ id: string; neutralClaim: string; supportExcerpt: string; storyRelevance: string }>;
  factPackItems: Array<{
    id: string;
    factId: string;
    neutralStatement: string;
    userPinned: boolean;
    userEdited: boolean;
    disabled: boolean;
    storyImportance: string;
  }>;
  narrativePlans: Array<{
    id: string;
    centralQuestion: string;
    openingApproach: string;
    narrativeLens: string;
    diffExplanation: string;
    isSelected: boolean;
    isEdited: boolean;
    beats: Array<{ id?: string; beatNumber: number; shortDescription: string; claimIds: string; purpose: string; narrativeRole: string }>;
  }>;
  scriptVersions: Array<{
    id: string;
    content: string;
    charCount: number;
    versionNumber: number;
    createdAt?: string;
    changeNote?: string | null;
    paragraphs: Array<{ paragraphIndex: number; paragraphText: string; factIds: string }>;
  }>;
  originalityReports: Array<{
    createdAt?: string;
    overallStatus: string;
    phraseOverlap: string;
    hookSimilarity: string;
    orderSimilarity: string;
    recommendedAction: string;
    exportBlocked: boolean;
    findings: Array<{ category: string; severity: string; explanation: string; affectedSection: string; remedy?: string | null }>;
  }>;
  pipelineRuns: Array<{
    id: string;
    stage: string;
    status: string;
    errorMessage?: string | null;
    startedAt?: string;
    finishedAt?: string | null;
  }>;
};

type PromptProfileOption = { id: string; name: string; genre: string | null };
type ChannelStyleOption = { id: string; name: string; tonePreset: string; isDefault: boolean };

type StorySettingsDraft = {
  title: string;
  topic: string;
  genreChoice: StoryGenreOption;
  genreCustom: string;
  promptProfileId: string;
  targetCharCount: string;
  audience: string;
  tone: string;
  outputLanguage: string;
  mustCoverPoints: string;
  narrativeApproach: NarrativeApproachOption;
  narrativeApproachCustom: string;
  openingHook: OpeningHookOption;
  openingHookCustom: string;
  ctaPreference: CtaMode;
  ctaChannelName: string;
  ctaClosingWording: string;
  channelStyleId: string;
};

const TABS = ["Sources", "Fact Bank", "Narrative Plan", "Script", "Originality QA"] as const;

function statusColor(status: string) {
  if (status === "block") return "bg-red-100 text-red-800";
  if (status === "warn") return "bg-amber-100 text-amber-800";
  return "bg-green-100 text-green-800";
}

export function ProjectWorkspace({ projectId }: { projectId: string }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Sources");
  const [project, setProject] = useState<ProjectData | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [preparingFacts, setPreparingFacts] = useState(false);
  const [scriptDraft, setScriptDraft] = useState("");
  const [sourceDrafts, setSourceDrafts] = useState<Record<string, string>>({});
  const [versionHistory, setVersionHistory] = useState<Array<{ versionNumber: number; changeNote?: string | null }>>([]);
  const [youtubeConnected, setYoutubeConnected] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [regeneratingWithSettings, setRegeneratingWithSettings] = useState(false);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [externalWriterBrief, setExternalWriterBrief] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [scriptEditing, setScriptEditing] = useState(false);
  const [scriptSavePending, setScriptSavePending] = useState(false);
  const [promptProfiles, setPromptProfiles] = useState<PromptProfileOption[]>([]);
  const [channelProfiles, setChannelProfiles] = useState<ChannelStyleOption[]>([]);
  const [settingsDraft, setSettingsDraft] = useState<StorySettingsDraft>({
    title: "",
    topic: "",
    genreChoice: "general_documentary",
    genreCustom: "",
    promptProfileId: "",
    targetCharCount: "6000",
    audience: "",
    tone: "",
    outputLanguage: "hi",
    mustCoverPoints: "",
    narrativeApproach: "auto",
    narrativeApproachCustom: "",
    openingHook: "auto",
    openingHookCustom: "",
    ctaPreference: "one_mid_and_closing",
    ctaChannelName: "",
    ctaClosingWording: "",
    channelStyleId: "",
  });

  const [lengthUiStatus, setLengthUiStatus] = useState<LengthStatus | null>(null);

  const refresh = useCallback(async () => {
    const res = await fetch(`/api/projects/${projectId}`);
    const data = await res.json();
    setProject(data);
    setExternalWriterBrief(null);
    setScriptDraft(data.scriptVersions[0]?.content ?? "");
    setScriptEditing(false);
    setLengthUiStatus((data.lengthStatus as LengthStatus | null) ?? null);
    const approach = legacyGoalToNarrativeApproach(data.narrativeGoal);
    const hook = OPENING_HOOK_OPTIONS.some((h) => h.value === data.openingHook)
      ? (data.openingHook as OpeningHookOption)
      : "auto";
    const genreChoice = isKnownGenre(data.genre) ? (data.genre as StoryGenreOption) : "custom";
    setSettingsDraft({
      title: data.title ?? "",
      topic: data.topic ?? "",
      genreChoice,
      genreCustom: genreChoice === "custom" ? (data.genre ?? "") : "",
      promptProfileId: data.promptProfileId ?? "",
      targetCharCount: String(resolveTargetCharCount(data.targetCharCount)),
      audience: data.audience ?? "",
      tone: data.tone ?? "",
      outputLanguage: data.outputLanguage ?? "hi",
      mustCoverPoints: data.mustCoverPoints ?? "",
      narrativeApproach: approach,
      narrativeApproachCustom: approach === "custom" ? (data.narrativeApproachCustom ?? "") : "",
      openingHook: hook,
      openingHookCustom: hook === "custom" ? (data.openingHookCustom ?? "") : "",
      ctaPreference: CTA_MODES.includes((data.ctaPreference as CtaMode) ?? "one_mid_and_closing")
        ? (data.ctaPreference as CtaMode)
        : "one_mid_and_closing",
      ctaChannelName: data.ctaChannelName ?? "",
      ctaClosingWording: data.ctaClosingWording ?? "",
      channelStyleId: data.channelStyleId ?? "",
    });
    const drafts: Record<string, string> = {};
    for (const s of data.sources) drafts[s.id] = s.rawTranscript ?? "";
    setSourceDrafts(drafts);
    setLoading(false);

    const [versionsRes, ytRes, profilesRes, channelRes] = await Promise.all([
      fetch(`/api/projects/${projectId}/script`),
      fetch("/api/youtube/oauth/status"),
      fetch("/api/prompt-profiles"),
      fetch("/api/channel-style-profiles"),
    ]);

    if (versionsRes.ok) setVersionHistory(await versionsRes.json());
    if (ytRes.ok) {
      const yt = await ytRes.json();
      setYoutubeConnected(Boolean(yt.connected));
    }
    if (profilesRes.ok) {
      setPromptProfiles(await profilesRes.json());
    }
    if (channelRes.ok) {
      setChannelProfiles(await channelRes.json());
    }
  }, [projectId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const activePipelineRun =
    project?.pipelineRuns.find((run) => run.status === "running") ?? null;
  const pipelineBusy = running || Boolean(activePipelineRun);

  useEffect(() => {
    if (!activePipelineRun && !running) return;
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [activePipelineRun, running, refresh]);

  function hasUnsavedScriptChanges(): boolean {
    return scriptEditing && scriptDraft !== (project?.scriptVersions[0]?.content ?? "");
  }

  async function prepareFactBullets() {
    if (pipelineBusy || !project) return;
    if (hasUnsavedScriptChanges() || settingsDirty || project.sources.some(
      (source) => (sourceDrafts[source.id] ?? "") !== (source.rawTranscript ?? ""),
    )) {
      setSettingsError("Save or cancel your pending edits before generating fact bullets.");
      return;
    }
    setPreparingFacts(true);
    setRunning(true);
    setSettingsError(null);
    setSettingsMessage("Preparing fact bullets from your saved transcripts. This may take a few minutes.");
    setExternalWriterBrief(null);
    setTab("Fact Bank");
    try {
      const res = await fetch(`/api/projects/${projectId}/prepare-facts`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Fact preparation failed");
      await refresh();
      setSettingsMessage(`${data.factCount} fact bullets prepared. Review them in Fact Bank, then click Copy master prompt. No script was generated.`);
    } catch (error) {
      setSettingsMessage(null);
      setSettingsError(error instanceof Error ? error.message : "Fact preparation failed");
    } finally {
      setRunning(false);
      setPreparingFacts(false);
    }
  }

  async function runPipeline() {
    if (hasUnsavedScriptChanges()) {
      alert("You have unsaved script edits. Save or cancel script edits before running generation.");
      return;
    }
    setRunning(true);
    setLengthUiStatus("drafting");
    try {
      const res = await fetch(`/api/projects/${projectId}/generate-original-story`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Pipeline failed");
      await refresh();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Pipeline failed");
    } finally {
      setRunning(false);
    }
  }

  async function cancelActivePipelineRun() {
    if (
      !confirm(
        "Stop the in-progress pipeline run? If the server is still calling the AI, restart the dev server before retrying.",
      )
    ) {
      return;
    }
    const res = await fetch(`/api/projects/${projectId}/pipeline-runs/cancel-active`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error ?? "Could not cancel run");
      return;
    }
    setRunning(false);
    await refresh();
  }

  async function regenerateNarration() {
    if (hasUnsavedScriptChanges()) {
      alert("You have unsaved script edits. Save or cancel script edits before regenerating.");
      return;
    }
    setRunning(true);
    setLengthUiStatus("drafting");
    try {
      const res = await fetch(`/api/projects/${projectId}/stages/generate_script`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Narration generation failed");
      await refresh();
    } catch (error) {
      alert(error instanceof Error ? error.message : "Narration generation failed");
    } finally {
      setRunning(false);
    }
  }

  async function selectPlan(planId: string) {
    await fetch(`/api/projects/${projectId}/plans/${planId}/select`, { method: "POST" });
    await refresh();
  }

  async function updateFact(factId: string, patch: Record<string, unknown>) {
    await fetch(`/api/projects/${projectId}/facts/${factId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    await refresh();
  }

  async function saveSource(sourceId: string) {
    await fetch(`/api/projects/${projectId}/sources/${sourceId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rawTranscript: sourceDrafts[sourceId] }),
    });
    await refresh();
  }

  async function fetchOfficialCaptions(sourceId: string) {
    const res = await fetch(`/api/projects/${projectId}/sources/${sourceId}/fetch-official-captions`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error ?? "Failed to fetch official captions");
      return;
    }
    await refresh();
  }

  function updateSettingsDraft<K extends keyof StorySettingsDraft>(key: K, value: StorySettingsDraft[K]) {
    setSettingsDraft((prev) => ({ ...prev, [key]: value }));
  }

  async function saveScript() {
    setScriptSavePending(true);
    const res = await fetch(`/api/projects/${projectId}/script`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content: scriptDraft, changeNote: "Manual save" }),
    });
    if (!res.ok) {
      const data = await res.json();
      setScriptSavePending(false);
      alert(data.error ?? "Failed to save script");
      return false;
    }
    setScriptEditing(false);
    await refresh();
    setScriptSavePending(false);
    return true;
  }

  const buildSettingsPayload = useCallback(() => {
    const parsed = Number(settingsDraft.targetCharCount);
    if (!Number.isInteger(parsed) || parsed < 1000 || parsed > 50000) {
      throw new Error("Target characters must be a whole number between 1,000 and 50,000.");
    }
    return {
      title: settingsDraft.title.trim(),
      topic: settingsDraft.topic.trim() || null,
      genre:
        settingsDraft.genreChoice === "custom"
          ? settingsDraft.genreCustom.trim() || null
          : settingsDraft.genreChoice,
      promptProfileId: settingsDraft.promptProfileId || null,
      targetCharCount: parsed,
      audience: settingsDraft.audience.trim() || null,
      tone: settingsDraft.tone.trim() || null,
      outputLanguage: settingsDraft.outputLanguage.trim() || "hi",
      mustCoverPoints: settingsDraft.mustCoverPoints.trim() || null,
      narrativeGoal: settingsDraft.narrativeApproach,
      narrativeApproachCustom:
        settingsDraft.narrativeApproach === "custom"
          ? settingsDraft.narrativeApproachCustom.trim() || null
          : null,
      openingHook: settingsDraft.openingHook,
      openingHookCustom: settingsDraft.openingHook === "custom" ? settingsDraft.openingHookCustom.trim() || null : null,
      ctaPreference: settingsDraft.ctaPreference,
      ctaChannelName: settingsDraft.ctaChannelName.trim() || null,
      ctaClosingWording: settingsDraft.ctaClosingWording.trim() || null,
      channelStyleId: settingsDraft.channelStyleId || null,
    };
  }, [settingsDraft]);

  async function saveStorySettings() {
    setSettingsSaving(true);
    setSettingsError(null);
    setSettingsMessage(null);
    setFieldErrors({});
    let payload: Record<string, unknown>;
    try {
      payload = buildSettingsPayload();
    } catch (error) {
      setSettingsSaving(false);
      setSettingsError(error instanceof Error ? error.message : "Invalid settings.");
      return null;
    }
    const res = await fetch(`/api/projects/${projectId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      setFieldErrors((data.fieldErrors as Record<string, string>) ?? {});
      setSettingsError(data.error ?? "Failed to save settings");
      setSettingsSaving(false);
      return null;
    }
    await refresh();
    const note = data.generationSettingsChanged
      ? "Settings updated. Your current script was generated with previous settings. Regenerate to apply these changes."
      : "Settings saved.";
    setSettingsMessage(note);
    setSettingsOpen(false);
    setSettingsSaving(false);
    return data as { regenerationScope?: "none" | "script_only" | "plan_and_script"; generationSettingsChanged?: boolean };
  }

  async function saveAndRegenerateWithSettings() {
    if (running || regeneratingWithSettings || settingsSaving) return;
    if (scriptEditing && scriptDraft !== (project?.scriptVersions[0]?.content ?? "")) {
      alert("You have unsaved script edits. Save or cancel script edits before regenerating.");
      return;
    }
    setRegeneratingWithSettings(true);
    setRunning(true);
    setLengthUiStatus("drafting");
    const saved = await saveStorySettings();
    if (!saved) {
      setRunning(false);
      setRegeneratingWithSettings(false);
      return;
    }
    try {
      const scope = saved.regenerationScope === "plan_and_script" ? "plan_and_script" : "script_only";
      const regenRes = await fetch(`/api/projects/${projectId}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scope }),
      });
      const regenData = await regenRes.json();
      if (!regenRes.ok) {
        setSettingsMessage("Settings saved, but regeneration failed. Your previous script is still preserved.");
        throw new Error(regenData.error ?? "Regeneration failed");
      }
      await refresh();
      setSettingsMessage("Settings saved and narration regenerated using the new settings.");
    } catch (error) {
      alert(error instanceof Error ? error.message : "Regeneration failed");
    } finally {
      setRegeneratingWithSettings(false);
      setRunning(false);
    }
  }

  async function saveScriptSettings() {
    const saved = await saveStorySettings();
    if (!saved) return;
    await refresh();
  }

  async function regenerateParagraph(index: number) {
    const res = await fetch(`/api/projects/${projectId}/script/regenerate-paragraph`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paragraphIndex: index }),
    });
    if (!res.ok) {
      const data = await res.json();
      alert(data.error ?? "Regeneration failed");
      return;
    }
    await refresh();
  }

  async function originalityAction(action: "rewrite" | "replan") {
    if (action === "rewrite") setLengthUiStatus("drafting");
    await fetch(`/api/projects/${projectId}/originality/rewrite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });
    await refresh();
  }

  async function overrideExport() {
    if (!confirm("Override export block? This does NOT constitute legal copyright clearance.")) return;
    await fetch(`/api/projects/${projectId}/export/override`, { method: "POST" });
    await refresh();
  }

  async function tryExport(format: "txt" | "md") {
    if (hasUnsavedScriptChanges()) {
      const discard = confirm(
        "You have unsaved script edits. Export the last saved version instead? Choose Cancel to continue editing.",
      );
      if (!discard) return;
      setScriptDraft(project?.scriptVersions[0]?.content ?? "");
      setScriptEditing(false);
    }
    const res = await fetch(`/api/projects/${projectId}/export?format=${format}`);
    if (!res.ok) {
      const data = await res.json();
      alert(data.error ?? "Export blocked");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `script.${format}`;
    a.click();
  }

  async function prepareExternalWriterBrief() {
    if (settingsDirty) {
      setSettingsError("Save your story settings before copying the master prompt.");
      return;
    }
    const res = await fetch(`/api/projects/${projectId}/external-writer-brief`);
    const data = await res.json();
    if (!res.ok) {
      alert(data.error ?? "Could not prepare the external writer brief");
      return;
    }

    setExternalWriterBrief(data.prompt);
    try {
      await navigator.clipboard.writeText(data.prompt);
      setSettingsMessage("Paste-ready master prompt copied. Paste it into ChatGPT or Claude to generate the full story.");
    } catch {
      setSettingsMessage("The paste-ready master prompt is below. Copy it manually and paste it into ChatGPT or Claude.");
    }
  }

  async function copyExternalWriterBrief() {
    if (!externalWriterBrief) return;
    try {
      await navigator.clipboard.writeText(externalWriterBrief);
      setSettingsMessage("Paste-ready master prompt copied.");
    } catch {
      alert("Select the text below and copy it manually.");
    }
  }

  if (loading || !project) {
    return (
      <AppShell>
        <p className="text-slate-500">Loading workspace…</p>
      </AppShell>
    );
  }

  const script = project.scriptVersions[0];
  const enabledFactCount = project.factPackItems.filter((fact) => !fact.disabled && fact.neutralStatement.trim()).length;
  const qa = project.originalityReports[0];
  const currentApproach = legacyGoalToNarrativeApproach(project.narrativeGoal);
  const currentHook = OPENING_HOOK_OPTIONS.some((h) => h.value === project.openingHook)
    ? (project.openingHook as OpeningHookOption)
    : "auto";
  const settingsSummary = {
    storyType:
      GENRE_OPTIONS.find((g) => g.value === project.genre)?.label ??
      project.genre ??
      project.promptProfile?.genre ??
      "General documentary",
    narrativeApproach:
      currentApproach === "custom"
        ? project.narrativeApproachCustom || "Custom"
        : approachLabel(currentApproach),
    openingHook: currentHook === "custom" ? project.openingHookCustom || "Custom" : hookLabel(currentHook),
    target: resolveTargetCharCount(project.targetCharCount),
    tone: project.tone ?? project.channelStyle?.tonePreset ?? "Default",
    ctaMode: ctaModeDescription(
      CTA_MODES.includes((project.ctaPreference as CtaMode) ?? "one_mid_and_closing")
        ? (project.ctaPreference as CtaMode)
        : "one_mid_and_closing",
    ),
  };
  const targetChars = resolveTargetCharCount(project.targetCharCount);
  const range = lengthRange(targetChars);
  const liveCount = countCharacters(scriptDraft);
  const settingsDirty = (() => {
    const savedCta = CTA_MODES.includes((project.ctaPreference as CtaMode) ?? "one_mid_and_closing")
      ? (project.ctaPreference as CtaMode)
      : "one_mid_and_closing";
    return (
      settingsDraft.title.trim() !== (project.title ?? "") ||
      settingsDraft.topic.trim() !== (project.topic ?? "") ||
      (settingsDraft.genreChoice === "custom" ? settingsDraft.genreCustom.trim() : settingsDraft.genreChoice) !==
        (project.genre ?? "") ||
      (settingsDraft.promptProfileId || "") !== (project.promptProfileId ?? "") ||
      Number(settingsDraft.targetCharCount || 0) !== resolveTargetCharCount(project.targetCharCount) ||
      settingsDraft.audience.trim() !== (project.audience ?? "") ||
      settingsDraft.tone.trim() !== (project.tone ?? "") ||
      settingsDraft.outputLanguage.trim() !== (project.outputLanguage ?? "hi") ||
      settingsDraft.mustCoverPoints.trim() !== (project.mustCoverPoints ?? "") ||
      settingsDraft.narrativeApproach !== currentApproach ||
      (settingsDraft.narrativeApproach === "custom" ? settingsDraft.narrativeApproachCustom.trim() : "") !==
        (currentApproach === "custom" ? project.narrativeApproachCustom ?? "" : "") ||
      settingsDraft.openingHook !== currentHook ||
      (settingsDraft.openingHook === "custom" ? settingsDraft.openingHookCustom.trim() : "") !==
        (currentHook === "custom" ? project.openingHookCustom ?? "" : "") ||
      settingsDraft.ctaPreference !== savedCta ||
      settingsDraft.ctaChannelName.trim() !== (project.ctaChannelName ?? "") ||
      settingsDraft.ctaClosingWording.trim() !== (project.ctaClosingWording ?? "") ||
      (settingsDraft.channelStyleId || "") !== (project.channelStyleId ?? "")
    );
  })();
  const scriptChangedAfterQa =
    Boolean(qa?.createdAt && script?.createdAt) &&
    new Date(qa.createdAt ?? 0).getTime() < new Date(script.createdAt ?? 0).getTime();
  const scriptStageProgress =
    activePipelineRun?.stage === "generate_script"
      ? activePipelineRun.errorMessage?.trim() || "Generating narration…"
      : null;
  const latestFailedScriptRun = project.pipelineRuns.find(
    (run) => run.stage === "generate_script" && run.status === "failed",
  );
  const scriptMissingNotice =
    !script && !activePipelineRun
      ? project.errorMessage?.trim() ||
        latestFailedScriptRun?.errorMessage?.trim() ||
        (project.status === "narrative_plan_ready"
          ? "Narrative plan is ready, but no Hindi script has been saved yet."
          : null)
      : null;
  const planReadyNoScript =
    !script && !pipelineBusy && project.narrativePlans.some((p) => p.isSelected);

  const derivedStatus: LengthStatus = pipelineBusy
    ? (lengthUiStatus ?? "drafting")
    : liveCount >= range.min && liveCount <= range.max
      ? "ready"
      : ((project.lengthStatus as LengthStatus | null) ?? "target_not_reached");
  const steps = [
    "draft", "sources_ready", "claims_ready", "fact_pack_ready",
    "narrative_plan_ready", "script_generated", "originality_review_ready", "complete",
  ];
  const stepIndex = steps.indexOf(project.status);

  return (
    <AppShell>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <Link href="/" className="text-sm text-slate-500 hover:underline">← Dashboard</Link>
          <h1 className="mt-2 text-3xl font-semibold">{project.title}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge className="capitalize">{project.status.replaceAll("_", " ")}</Badge>
            {project.isDemo && <Badge>Demo</Badge>}
            {project.promptProfile && <Badge>{project.promptProfile.name}</Badge>}
            {project.channelStyle && <Badge>{project.channelStyle.name}</Badge>}
          </div>
          <p className="mt-2 text-sm text-slate-600">
            Type: {settingsSummary.storyType} · Approach: {settingsSummary.narrativeApproach} · Hook: {settingsSummary.openingHook}
          </p>
          <p className="text-sm text-slate-600">
            Target: {settingsSummary.target.toLocaleString()} chars · Tone: {settingsSummary.tone} · CTA: {settingsSummary.ctaMode}
          </p>
          {activePipelineRun && (
            <div className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-700">
              <p>
                Pipeline in progress ({activePipelineRun.stage.replaceAll("_", " ")})
                {activePipelineRun.errorMessage ? `: ${activePipelineRun.errorMessage}` : "…"}
              </p>
              <Button type="button" size="sm" variant="outline" onClick={() => void cancelActivePipelineRun()}>
                Cancel run
              </Button>
            </div>
          )}
          {scriptMissingNotice && !activePipelineRun && (
            <p className="mt-2 text-sm text-amber-800">{scriptMissingNotice}</p>
          )}
          {project.errorMessage && !activePipelineRun && script && (
            <p className="mt-2 text-sm text-red-600">{project.errorMessage}</p>
          )}
          {settingsMessage && <p className="mt-2 text-sm text-emerald-700">{settingsMessage}</p>}
          {settingsError && <p className="mt-2 text-sm text-red-600">{settingsError}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => {
              if (settingsOpen && settingsDirty) {
                const discard = confirm("Discard unsaved story settings changes?");
                if (!discard) return;
              }
              setSettingsOpen((prev) => !prev);
              setFieldErrors({});
              setSettingsError(null);
            }}
            disabled={pipelineBusy || settingsSaving || regeneratingWithSettings}
          >
            Edit story settings
          </Button>
          {planReadyNoScript && (
            <Button variant="secondary" onClick={() => void regenerateNarration()} disabled={pipelineBusy}>
              {pipelineBusy ? "Generating script…" : "Generate script"}
            </Button>
          )}
          <Button onClick={runPipeline} disabled={pipelineBusy}>
            {pipelineBusy ? "Running pipeline…" : "Generate original story"}
          </Button>
          {project.factPackItems.length === 0 && (
            <Button variant="secondary" onClick={() => void prepareFactBullets()} disabled={pipelineBusy || settingsSaving}>
              {preparingFacts ? "Preparing fact bullets…" : "Generate fact bullets"}
            </Button>
          )}
          <Button variant="secondary" onClick={() => void prepareExternalWriterBrief()} disabled={pipelineBusy || enabledFactCount === 0}>
            Copy master prompt
          </Button>
          <Button variant="outline" onClick={() => tryExport("txt")}>Export .txt</Button>
          <Button variant="outline" onClick={() => tryExport("md")}>Export .md</Button>
        </div>
      </div>

      {externalWriterBrief && (
        <Card className="mb-6 border-slate-200">
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <div>
              <CardTitle className="text-base">External writer master prompt</CardTitle>
              <p className="mt-1 text-sm text-slate-600">
                Paste this whole prompt into ChatGPT or Claude to generate the complete story. It contains selected settings and neutral Fact Bank bullets—no source transcript, source phrasing, or plan prose.
              </p>
            </div>
            <Button size="sm" variant="outline" onClick={() => void copyExternalWriterBrief()}>
              Copy master prompt
            </Button>
          </CardHeader>
          <CardContent>
            <Textarea readOnly value={externalWriterBrief} className="min-h-80 font-mono text-xs" />
          </CardContent>
        </Card>
      )}

      {settingsOpen && (
        <Card className="mb-6 border-slate-200">
          <CardHeader>
            <CardTitle className="text-base">Edit story settings</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Story title</label>
              <Input value={settingsDraft.title} onChange={(e) => updateSettingsDraft("title", e.target.value)} />
              {fieldErrors.title && <p className="mt-1 text-xs text-red-600">{fieldErrors.title}</p>}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Topic / brief</label>
              <Input value={settingsDraft.topic} onChange={(e) => updateSettingsDraft("topic", e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Story type / genre</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.genreChoice}
                onChange={(e) => updateSettingsDraft("genreChoice", e.target.value as StoryGenreOption)}
              >
                {GENRE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              {settingsDraft.genreChoice === "custom" && (
                <Input
                  className="mt-2"
                  value={settingsDraft.genreCustom}
                  onChange={(e) => updateSettingsDraft("genreCustom", e.target.value)}
                  placeholder="Custom genre"
                />
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Prompt profile</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.promptProfileId}
                onChange={(e) => updateSettingsDraft("promptProfileId", e.target.value)}
              >
                <option value="">No profile</option>
                {promptProfiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.genre ? ` — ${p.genre}` : ""}
                  </option>
                ))}
              </select>
              {fieldErrors.promptProfileId && <p className="mt-1 text-xs text-red-600">{fieldErrors.promptProfileId}</p>}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Target length (characters)</label>
              <Input
                type="number"
                min={1000}
                max={50000}
                step={100}
                value={settingsDraft.targetCharCount}
                onChange={(e) => updateSettingsDraft("targetCharCount", e.target.value)}
              />
              <p className="mt-1 text-xs text-slate-500">
                Count method: Unicode code points (includes spaces, punctuation and paragraph breaks). Accepted range: target ±5%.
              </p>
              {fieldErrors.targetCharCount && <p className="mt-1 text-xs text-red-600">{fieldErrors.targetCharCount}</p>}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Audience</label>
              <Input value={settingsDraft.audience} onChange={(e) => updateSettingsDraft("audience", e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Tone / narration style</label>
              <Input value={settingsDraft.tone} onChange={(e) => updateSettingsDraft("tone", e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Language</label>
              <Input value={settingsDraft.outputLanguage} onChange={(e) => updateSettingsDraft("outputLanguage", e.target.value)} />
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-slate-600">Narrative approach</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.narrativeApproach}
                onChange={(e) => updateSettingsDraft("narrativeApproach", e.target.value as NarrativeApproachOption)}
              >
                {NARRATIVE_APPROACH_OPTIONS.map((approach) => (
                  <option key={approach.value} value={approach.value}>
                    {approach.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">
                {NARRATIVE_APPROACH_OPTIONS.find((a) => a.value === settingsDraft.narrativeApproach)?.help}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Project approach and hook choices override conflicting structural instructions in prompt profiles.
              </p>
              {settingsDraft.narrativeApproach === "custom" && (
                <Textarea
                  className="mt-2"
                  value={settingsDraft.narrativeApproachCustom}
                  onChange={(e) => updateSettingsDraft("narrativeApproachCustom", e.target.value)}
                  placeholder="Describe your preferred narrative structure"
                />
              )}
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-slate-600">Opening hook</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.openingHook}
                onChange={(e) => updateSettingsDraft("openingHook", e.target.value as OpeningHookOption)}
              >
                {OPENING_HOOK_OPTIONS.map((hook) => (
                  <option key={hook.value} value={hook.value}>
                    {hook.label}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500">
                Opening hook affects the first lines only; narrative approach controls the full story structure.
              </p>
              {settingsDraft.openingHook === "custom" && (
                <Textarea
                  className="mt-2"
                  value={settingsDraft.openingHookCustom}
                  onChange={(e) => updateSettingsDraft("openingHookCustom", e.target.value)}
                  placeholder="Custom opening instructions (source-supported only)"
                />
              )}
            </div>
            <div className="sm:col-span-2">
              <label className="mb-1 block text-xs font-medium text-slate-600">Must-cover points / special instructions</label>
              <Textarea
                value={settingsDraft.mustCoverPoints}
                onChange={(e) => updateSettingsDraft("mustCoverPoints", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">CTA mode</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.ctaPreference}
                onChange={(e) => updateSettingsDraft("ctaPreference", e.target.value as CtaMode)}
              >
                {CTA_MODES.map((mode) => (
                  <option key={mode} value={mode}>
                    {ctaModeDescription(mode)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Channel style profile</label>
              <select
                className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
                value={settingsDraft.channelStyleId}
                onChange={(e) => updateSettingsDraft("channelStyleId", e.target.value)}
              >
                <option value="">No channel style</option>
                {channelProfiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}{profile.isDefault ? " (Default)" : ""}
                  </option>
                ))}
              </select>
              {fieldErrors.channelStyleId && <p className="mt-1 text-xs text-red-600">{fieldErrors.channelStyleId}</p>}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">CTA channel name (optional)</label>
              <Input
                value={settingsDraft.ctaChannelName}
                onChange={(e) => updateSettingsDraft("ctaChannelName", e.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-600">Preferred closing CTA wording (optional)</label>
              <Input
                value={settingsDraft.ctaClosingWording}
                onChange={(e) => updateSettingsDraft("ctaClosingWording", e.target.value)}
              />
            </div>
            <div className="sm:col-span-2">
              <p className="mb-2 text-xs text-slate-500">
                Save settings stores changes only. Save & regenerate stores settings and then rebuilds narrative planning/script as needed.
              </p>
              <div className="flex flex-wrap gap-2">
                <Button onClick={saveScriptSettings} disabled={settingsSaving || regeneratingWithSettings || pipelineBusy}>
                  {settingsSaving ? "Saving…" : "Save settings"}
                </Button>
                <Button
                  variant="outline"
                  onClick={saveAndRegenerateWithSettings}
                  disabled={settingsSaving || regeneratingWithSettings || pipelineBusy}
                >
                  {regeneratingWithSettings ? "Saving & regenerating…" : "Save & regenerate"}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {planReadyNoScript && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <p className="font-medium">No script yet — you are on step 5 of 8.</p>
          <p className="mt-1 text-amber-900">
            Sources, facts, and narrative plan are done. Open the <strong>Script</strong> tab or click{" "}
            <strong>Generate script</strong> to write the Hindi narration (about 12,000 characters in three sections).
          </p>
          {latestFailedScriptRun?.errorMessage && (
            <p className="mt-2 text-amber-800">Last attempt: {latestFailedScriptRun.errorMessage}</p>
          )}
        </div>
      )}

      <div className="mb-6 flex flex-wrap gap-2">
        {steps.map((step, i) => (
          <div key={step} className={`rounded-full px-3 py-1 text-xs capitalize ${i <= stepIndex ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-600"}`}>
            {step.replaceAll("_", " ")}
          </div>
        ))}
      </div>

      <div className="mb-4 flex flex-wrap gap-2 border-b border-slate-200 pb-3">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-2 text-sm ${tab === t ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "Sources" && (
        <div className="grid gap-4">
          {project.sources.map((source) => (
            <Card key={source.id}>
              <CardHeader>
                <CardTitle className="text-base">{source.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-slate-600">
                <p>Status: {source.transcriptStatus.replaceAll("_", " ")}</p>
                {source.transcriptOrigin && (
                  <p className="text-slate-500">Origin: {source.transcriptOrigin.replaceAll("_", " ")}</p>
                )}
                {source.url && <p className="break-all text-slate-500">Reference: {source.url}</p>}
                <Textarea
                  placeholder="Paste or edit transcript (required before generation)"
                  value={sourceDrafts[source.id] ?? ""}
                  onChange={(e) => setSourceDrafts({ ...sourceDrafts, [source.id]: e.target.value })}
                />
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" onClick={() => saveSource(source.id)}>Save transcript</Button>
                  {source.kind === "youtube" && source.videoId && youtubeConnected && (
                    <Button size="sm" variant="outline" onClick={() => fetchOfficialCaptions(source.id)}>
                      Fetch official captions (owned videos)
                    </Button>
                  )}
                </div>
                {source.transcriptStatus === "needs_transcript" && (
                  <p className="text-amber-700">
                    Transcript required — paste manually or fetch official captions for a video you own via{" "}
                    <Link href="/settings/youtube" className="underline">YouTube OAuth</Link>.
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === "Fact Bank" && (
        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Prepare references for ChatGPT or Claude</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-slate-600">
              {project.factPackItems.length === 0 ? (
                <>
                  <p>Generate neutral fact bullets from your saved source transcripts. This stops at the Fact Bank; it does not write a story.</p>
                  <Button onClick={() => void prepareFactBullets()} disabled={pipelineBusy || settingsSaving}>
                    {preparingFacts ? "Preparing fact bullets…" : "Generate fact bullets"}
                  </Button>
                </>
              ) : (
                <>
                  <p>{enabledFactCount} fact bullets enabled. Review, edit, or disable bullets below, then copy the master prompt with your selected profile and story settings.</p>
                  <p>These are claims extracted from your sources, not independently verified facts.</p>
                  <Button onClick={() => void prepareExternalWriterBrief()} disabled={pipelineBusy || enabledFactCount === 0}>
                    Copy master prompt
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
          {project.factPackItems.map((fact) => (
            <Card key={fact.id}>
              <CardContent className="space-y-3 py-5">
                <div className="flex items-center gap-2">
                  <Badge>{fact.factId}</Badge>
                  <Badge>{fact.storyImportance}</Badge>
                  {fact.userPinned && <Badge className="bg-amber-100">Pinned</Badge>}
                  {fact.userEdited && <Badge className="bg-blue-100">Edited</Badge>}
                </div>
                <Textarea
                  defaultValue={fact.neutralStatement}
                  onBlur={(e) => updateFact(fact.id, { neutralStatement: e.target.value })}
                />
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => updateFact(fact.id, { userPinned: !fact.userPinned })}>
                    {fact.userPinned ? "Unpin" : "Pin required"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => updateFact(fact.id, { disabled: !fact.disabled })}>
                    {fact.disabled ? "Enable" : "Disable"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === "Narrative Plan" && (
        <div className="grid gap-4 lg:grid-cols-2">
          {project.narrativePlans.map((plan) => (
            <Card key={plan.id} className={plan.isSelected ? "ring-2 ring-slate-900" : ""}>
              <CardHeader>
                <CardTitle className="text-base">{plan.centralQuestion}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p><strong>Angle:</strong> {plan.centralQuestion}</p>
                <p><strong>Approach:</strong> {plan.narrativeLens}</p>
                <p><strong>Proposed hook:</strong> {plan.openingApproach}</p>
                <p className="text-slate-600">{plan.diffExplanation}</p>
                {plan.isEdited && <Badge>Edited</Badge>}
                <ol className="list-decimal space-y-1 pl-5">
                  {plan.beats.map((beat) => (
                    <li key={beat.beatNumber}>{beat.shortDescription}</li>
                  ))}
                </ol>
                <Button size="sm" variant={plan.isSelected ? "default" : "outline"} onClick={() => selectPlan(plan.id)}>
                  {plan.isSelected ? "Selected" : "Select treatment"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === "Script" && (
        <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Hindi narration</CardTitle>
            </CardHeader>
            <CardContent>
              {script ? (
                <>
                  <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                    <p>Target: {targetChars.toLocaleString()} characters</p>
                    <p>Actual: {liveCount.toLocaleString()}</p>
                    <p>Accepted range: {range.min.toLocaleString()}–{range.max.toLocaleString()}</p>
                    <p>Status: {lengthStatusLabel(derivedStatus)}</p>
                  </div>
                  {scriptChangedAfterQa && (
                    <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                      Originality and editorial checks are outdated for this manually edited script. Regenerate originality QA to refresh.
                    </p>
                  )}
                  <p className="mb-4 text-sm text-slate-500">
                    v{script.versionNumber} · ~
                    {Math.round(estimateDurationSeconds(liveCount) / 60)} min
                  </p>
                  <Textarea
                    className="min-h-[480px] font-medium leading-7"
                    value={scriptDraft}
                    readOnly={!scriptEditing}
                    onChange={(e) => setScriptDraft(e.target.value)}
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    {!scriptEditing ? (
                      <Button size="sm" variant="outline" onClick={() => setScriptEditing(true)}>Edit script</Button>
                    ) : (
                      <>
                        <Button size="sm" onClick={saveScript} disabled={scriptSavePending}>
                          {scriptSavePending ? "Saving…" : "Save edits"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            setScriptDraft(script.content);
                            setScriptEditing(false);
                          }}
                        >
                          Cancel edits
                        </Button>
                      </>
                    )}
                    <Button size="sm" variant="outline" onClick={regenerateNarration} disabled={pipelineBusy}>
                      {pipelineBusy ? "Regenerating…" : "Regenerate narration to target length"}
                    </Button>
                  </div>
                </>
              ) : scriptStageProgress || (pipelineBusy && activePipelineRun?.stage === "generate_script") ? (
                <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm">
                  <p className="font-medium text-slate-800">Script generation in progress</p>
                  <p className="text-slate-600">{scriptStageProgress ?? "Generating narration…"}</p>
                  <p className="text-xs text-slate-500">
                    The full script appears here only after all sections finish. Long Hindi targets (e.g. 12,000
                    characters) can take several minutes per section—this page refreshes automatically.
                  </p>
                </div>
              ) : planReadyNoScript ? (
                <div className="space-y-3 text-sm">
                  <p className="text-slate-600">
                    Narration has not been generated yet. Use the button below (or <strong>Generate script</strong> at
                    the top) and keep this tab open while all three sections finish.
                  </p>
                  {scriptMissingNotice && <p className="text-amber-800">{scriptMissingNotice}</p>}
                  <Button onClick={() => void regenerateNarration()} disabled={pipelineBusy}>
                    {pipelineBusy ? "Generating script…" : "Generate script"}
                  </Button>
                </div>
              ) : (
                <p className="text-sm text-slate-500">Generate a narrative plan and script to see output here.</p>
              )}
            </CardContent>
          </Card>
          <div className="space-y-4">
            <Card>
              <CardHeader><CardTitle className="text-base">Traceability</CardTitle></CardHeader>
              <CardContent className="space-y-3 text-sm">
                {script?.paragraphs.map((p) => (
                  <div key={p.paragraphIndex} className="rounded bg-slate-50 p-3">
                    <p className="line-clamp-3">{p.paragraphText}</p>
                    <p className="mt-1 text-xs text-slate-500">Facts: {p.factIds}</p>
                    <Button size="sm" variant="outline" className="mt-2" onClick={() => regenerateParagraph(p.paragraphIndex)}>
                      Regenerate
                    </Button>
                  </div>
                )) ?? <p className="text-slate-500">No trace map yet.</p>}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle className="text-base">Version history</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-sm">
                {versionHistory.map((v) => (
                  <div key={v.versionNumber} className="rounded bg-slate-50 px-3 py-2">
                    v{v.versionNumber} — {v.changeNote ?? "—"}
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {tab === "Originality QA" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Editorial originality report</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm">
            {!qa ? (
              <p className="text-slate-500">Run the pipeline to generate an originality report.</p>
            ) : (
              <>
                <p className="text-slate-600">
                  Editorial originality check only — not legal clearance or a guarantee of uniqueness.
                </p>
                {scriptChangedAfterQa && (
                  <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-800">
                    This report is from an older script version. Run generation or rewrite to refresh findings.
                  </p>
                )}
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  <Badge className={statusColor(qa.overallStatus)}>Overall: {qa.overallStatus.toUpperCase()}</Badge>
                  <Badge className={statusColor(qa.phraseOverlap)}>Phrase: {qa.phraseOverlap.toUpperCase()}</Badge>
                  <Badge className={statusColor(qa.hookSimilarity)}>Hook: {qa.hookSimilarity.toUpperCase()}</Badge>
                  <Badge className={statusColor(qa.orderSimilarity)}>Order: {qa.orderSimilarity.toUpperCase()}</Badge>
                </div>
                <p><strong>Recommended action:</strong> {qa.recommendedAction}</p>
                {qa.exportBlocked && !project.exportOverride && (
                  <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-red-800">
                    Export is blocked until narrative structure is revised or explicitly overridden.
                    <div className="mt-2 flex gap-2">
                      <Button size="sm" variant="outline" onClick={() => originalityAction("replan")}>Re-plan structure</Button>
                      <Button size="sm" variant="outline" onClick={overrideExport}>Override export</Button>
                    </div>
                  </div>
                )}
                {qa.overallStatus === "warn" && (
                  <Button size="sm" variant="outline" onClick={() => originalityAction("rewrite")}>
                    Targeted rewrite
                  </Button>
                )}
                <div className="space-y-3">
                  {qa.findings.map((f, i) => (
                    <div key={i} className="rounded border border-slate-200 p-3">
                      <p className="font-medium capitalize">{f.category} · {f.severity}</p>
                      <p className="mt-1">{f.explanation}</p>
                      <p className="mt-1 text-slate-500">Section: {f.affectedSection}</p>
                      {f.remedy && <p className="mt-1 text-slate-500">Remedy: {f.remedy}</p>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </AppShell>
  );
}
