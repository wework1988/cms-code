"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  GENRE_OPTIONS,
  NARRATIVE_APPROACH_OPTIONS,
  OPENING_HOOK_OPTIONS,
  type NarrativeApproachOption,
  type OpeningHookOption,
  type StoryGenreOption,
} from "@/lib/story-settings/options";

type SourceDraft = {
  kind: "youtube" | "pasted";
  title: string;
  url: string;
  transcript: string;
};

type PromptProfile = { id: string; name: string; genre: string | null };
type ChannelStyleProfile = { id: string; name: string; tonePreset: string; isDefault: boolean };

const CTA_OPTIONS = [
  {
    value: "closing_only",
    label: "Closing CTA only",
    help: "Use only a final invite after the narrative resolution.",
  },
  {
    value: "one_mid_and_closing",
    label: "One mid-story CTA + closing CTA (Default)",
    help: "Balanced mode: one contextual engagement line mid-story and one closing invite.",
  },
  {
    value: "two_mid_and_closing",
    label: "Two mid-story CTAs + closing CTA",
    help: "Best for longer scripts; may gracefully downgrade on shorter drafts.",
  },
] as const;

export default function NewProjectPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [profiles, setProfiles] = useState<PromptProfile[]>([]);
  const [channelProfiles, setChannelProfiles] = useState<ChannelStyleProfile[]>([]);
  const [promptProfileId, setPromptProfileId] = useState("");
  const [channelStyleId, setChannelStyleId] = useState("");
  const [title, setTitle] = useState("");
  const [topic, setTopic] = useState("");
  const [targetCharCount, setTargetCharCount] = useState("6000");
  const [audience, setAudience] = useState("");
  const [tone, setTone] = useState("");
  const [mustCoverPoints, setMustCoverPoints] = useState("");
  const [outputLanguage, setOutputLanguage] = useState("hi");
  const [genreChoice, setGenreChoice] = useState<StoryGenreOption>("general_documentary");
  const [customGenre, setCustomGenre] = useState("");
  const [ctaPreference, setCtaPreference] = useState<(typeof CTA_OPTIONS)[number]["value"]>("one_mid_and_closing");
  const [ctaChannelName, setCtaChannelName] = useState("");
  const [ctaClosingWording, setCtaClosingWording] = useState("");
  const [narrativeApproach, setNarrativeApproach] = useState<NarrativeApproachOption>("auto");
  const [narrativeApproachCustom, setNarrativeApproachCustom] = useState("");
  const [openingHook, setOpeningHook] = useState<OpeningHookOption>("auto");
  const [openingHookCustom, setOpeningHookCustom] = useState("");
  const [sources, setSources] = useState<SourceDraft[]>([
    { kind: "pasted", title: "", url: "", transcript: "" },
  ]);

  useEffect(() => {
    Promise.all([fetch("/api/prompt-profiles"), fetch("/api/channel-style-profiles")])
      .then(async ([profilesRes, channelRes]) => {
        const data = (await profilesRes.json()) as PromptProfile[];
        setProfiles(data);
        const defaultProfile = data.find((p) => p.name.includes("General")) ?? data[0];
        if (defaultProfile) setPromptProfileId(defaultProfile.id);
        if (channelRes.ok) {
          const channels = (await channelRes.json()) as ChannelStyleProfile[];
          setChannelProfiles(channels);
          const defaultChannel = channels.find((c) => c.isDefault) ?? channels[0];
          if (defaultChannel) setChannelStyleId(defaultChannel.id);
        }
      });
  }, []);

  function updateSource(index: number, patch: Partial<SourceDraft>) {
    setSources((prev) => prev.map((s, i) => (i === index ? { ...s, ...patch } : s)));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          topic,
          outputLanguage,
          targetCharCount: Number(targetCharCount),
          audience,
          tone: tone.trim() || undefined,
          mustCoverPoints: mustCoverPoints.trim() || undefined,
          genre: genreChoice === "custom" ? customGenre.trim() || undefined : genreChoice,
          ctaPreference,
          ctaChannelName: ctaChannelName.trim() || undefined,
          ctaClosingWording: ctaClosingWording.trim() || undefined,
          narrativeGoal: narrativeApproach,
          narrativeApproachCustom: narrativeApproach === "custom" ? narrativeApproachCustom.trim() || undefined : undefined,
          openingHook,
          openingHookCustom: openingHook === "custom" ? openingHookCustom.trim() || undefined : undefined,
          promptProfileId: promptProfileId || undefined,
          channelStyleId: channelStyleId || undefined,
          sources: sources.map((s) => ({
            kind: s.kind,
            title: s.title || undefined,
            url: s.kind === "youtube" ? s.url : undefined,
            transcript: s.transcript.trim() || undefined,
          })),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed to create project");
      router.push(`/projects/${data.id}`);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppShell>
      <form onSubmit={onSubmit} className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-3xl font-semibold">New story</h1>
          <p className="mt-2 text-slate-600">
            Manual transcript mode is the default. Paste transcripts for every source before generating.
            YouTube URLs are stored as references only — Story Studio does not scrape third-party captions.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Brief</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input placeholder="Working title" value={title} onChange={(e) => setTitle(e.target.value)} required />
            <Input placeholder="Topic" value={topic} onChange={(e) => setTopic(e.target.value)} />
            <Input
              placeholder="Target character count"
              value={targetCharCount}
              onChange={(e) => setTargetCharCount(e.target.value)}
            />
            <Input placeholder="Audience (optional)" value={audience} onChange={(e) => setAudience(e.target.value)} />
            <Input placeholder="Tone / narration style (optional)" value={tone} onChange={(e) => setTone(e.target.value)} />
            <Input
              placeholder="Language code (default hi)"
              value={outputLanguage}
              onChange={(e) => setOutputLanguage(e.target.value)}
            />
            <label className="block text-sm font-medium">Story genre</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={genreChoice}
              onChange={(e) => setGenreChoice(e.target.value as StoryGenreOption)}
            >
              {GENRE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            {genreChoice === "custom" && (
              <Input
                placeholder="Custom genre"
                value={customGenre}
                onChange={(e) => setCustomGenre(e.target.value)}
              />
            )}
            <label className="block text-sm font-medium">Narrative approach</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={narrativeApproach}
              onChange={(e) => setNarrativeApproach(e.target.value as NarrativeApproachOption)}
            >
              {NARRATIVE_APPROACH_OPTIONS.map((approach) => (
                <option key={approach.value} value={approach.value}>
                  {approach.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">
              {NARRATIVE_APPROACH_OPTIONS.find((o) => o.value === narrativeApproach)?.help}
            </p>
            {narrativeApproach === "custom" && (
              <Textarea
                placeholder="Describe your preferred story structure"
                value={narrativeApproachCustom}
                onChange={(e) => setNarrativeApproachCustom(e.target.value)}
              />
            )}
            <label className="block text-sm font-medium">Opening hook</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={openingHook}
              onChange={(e) => setOpeningHook(e.target.value as OpeningHookOption)}
            >
              {OPENING_HOOK_OPTIONS.map((hook) => (
                <option key={hook.value} value={hook.value}>
                  {hook.label}
                </option>
              ))}
            </select>
            {openingHook === "custom" && (
              <Textarea
                placeholder="Custom opening instructions (source-supported only)"
                value={openingHookCustom}
                onChange={(e) => setOpeningHookCustom(e.target.value)}
              />
            )}
            <label className="block text-sm font-medium">Must-cover points / special instructions</label>
            <Textarea
              placeholder="Important points that should be covered (optional)"
              value={mustCoverPoints}
              onChange={(e) => setMustCoverPoints(e.target.value)}
            />
            <label className="block text-sm font-medium">CTA style</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={ctaPreference}
              onChange={(e) =>
                setCtaPreference(e.target.value as (typeof CTA_OPTIONS)[number]["value"])
              }
            >
              {CTA_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">
              {CTA_OPTIONS.find((o) => o.value === ctaPreference)?.help}
            </p>
            <Input
              placeholder="Channel name for closing CTA (optional)"
              value={ctaChannelName}
              onChange={(e) => setCtaChannelName(e.target.value)}
            />
            <Input
              placeholder="Preferred closing CTA wording (optional)"
              value={ctaClosingWording}
              onChange={(e) => setCtaClosingWording(e.target.value)}
            />
            <label className="block text-sm font-medium">Prompt profile</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={promptProfileId}
              onChange={(e) => setPromptProfileId(e.target.value)}
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.genre ? ` — ${p.genre}` : ""}
                </option>
              ))}
            </select>
            <label className="block text-sm font-medium">Channel style profile</label>
            <select
              className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm"
              value={channelStyleId}
              onChange={(e) => setChannelStyleId(e.target.value)}
            >
              <option value="">No channel style</option>
              {channelProfiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name}{profile.isDefault ? " (Default)" : ""}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500">
              Narrative approach controls full structure; opening hook controls only the opening lines.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Sources</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {sources.map((source, index) => (
              <div key={index} className="space-y-3 rounded-lg border border-slate-200 p-4">
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant={source.kind === "pasted" ? "default" : "outline"}
                    size="sm"
                    onClick={() => updateSource(index, { kind: "pasted" })}
                  >
                    Paste transcript
                  </Button>
                  <Button
                    type="button"
                    variant={source.kind === "youtube" ? "default" : "outline"}
                    size="sm"
                    onClick={() => updateSource(index, { kind: "youtube" })}
                  >
                    YouTube reference + transcript
                  </Button>
                </div>
                <Input
                  placeholder="Source title (optional)"
                  value={source.title}
                  onChange={(e) => updateSource(index, { title: e.target.value })}
                />
                {source.kind === "youtube" && (
                  <Input
                    placeholder="YouTube URL (reference only)"
                    value={source.url}
                    onChange={(e) => updateSource(index, { url: e.target.value })}
                    required
                  />
                )}
                <Textarea
                  placeholder={
                    source.kind === "youtube"
                      ? "Paste transcript (required before generation). For owned videos, fetch official captions in the workspace after connecting YouTube OAuth."
                      : "Paste transcript with optional timestamps"
                  }
                  value={source.transcript}
                  onChange={(e) => updateSource(index, { transcript: e.target.value })}
                />
              </div>
            ))}
            {sources.length < 5 && (
              <Button
                type="button"
                variant="outline"
                onClick={() => setSources((s) => [...s, { kind: "pasted", title: "", url: "", transcript: "" }])}
              >
                Add source
              </Button>
            )}
          </CardContent>
        </Card>

        <Button type="submit" disabled={loading}>
          {loading ? "Creating…" : "Create project"}
        </Button>
      </form>
    </AppShell>
  );
}
