"use client";

import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";

type PromptProfile = {
  id: string;
  name: string;
  genre: string | null;
  styleInstructions: string;
  version: number;
};

export default function PromptProfilesPage() {
  const [profiles, setProfiles] = useState<PromptProfile[]>([]);
  const [editing, setEditing] = useState<PromptProfile | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", genre: "", styleInstructions: "" });

  const refresh = useCallback(async () => {
    const res = await fetch("/api/prompt-profiles");
    setProfiles(await res.json());
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function saveProfile() {
    const payload = {
      name: form.name,
      genre: form.genre || undefined,
      styleInstructions: form.styleInstructions,
    };

    if (editing) {
      await fetch(`/api/prompt-profiles/${editing.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      await fetch("/api/prompt-profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    }

    setEditing(null);
    setForm({ name: "", genre: "", styleInstructions: "" });
    await refresh();
  }

  async function duplicateProfile(id: string) {
    await fetch(`/api/prompt-profiles/${id}/duplicate`, { method: "POST" });
    await refresh();
  }

  return (
    <AppShell active="prompts">
      <h1 className="mb-2 text-3xl font-semibold">Prompt Profiles</h1>
      <p className="mb-6 max-w-2xl text-slate-600">
        Store reusable writing profiles here—for example, Crime, Faith / devotional, History, or General Documentary.
        Select one in a project’s story settings; its rules are then merged with that project’s settings and approved Fact Bank bullets when you copy the external master prompt.
      </p>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>{editing ? "Edit profile" : "New profile"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input placeholder="Profile name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <Input placeholder="Genre" value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} />
          <Textarea
            placeholder="Reusable writing rules: voice, structure, pacing, sensitivity, and ending. Do not paste source transcript wording here."
            value={form.styleInstructions}
            onChange={(e) => setForm({ ...form, styleInstructions: e.target.value })}
          />
          <div className="flex gap-2">
            <Button onClick={saveProfile} disabled={!form.name || !form.styleInstructions}>
              {editing ? "Update" : "Create"}
            </Button>
            {editing && (
              <Button variant="outline" onClick={() => { setEditing(null); setForm({ name: "", genre: "", styleInstructions: "" }); }}>
                Cancel
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {profiles.map((profile) => (
          <Card key={profile.id}>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">{profile.name}</CardTitle>
                  <Badge>{profile.genre ?? "General"}</Badge>
                  <Badge>v{profile.version}</Badge>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant={viewingId === profile.id ? "default" : "outline"}
                    onClick={() =>
                      setViewingId((current) => (current === profile.id ? null : profile.id))
                    }
                  >
                    {viewingId === profile.id ? "Hide" : "View"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setViewingId(null);
                      setEditing(profile);
                      setForm({
                        name: profile.name,
                        genre: profile.genre ?? "",
                        styleInstructions: profile.styleInstructions,
                      });
                    }}
                  >
                    Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => duplicateProfile(profile.id)}>
                    Duplicate
                  </Button>
                </div>
              </div>
            </CardHeader>
            {viewingId === profile.id && (
              <CardContent className="border-t pt-4">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Writing rules
                </p>
                <div className="max-h-[min(70vh,32rem)] overflow-y-auto rounded-md border bg-slate-50 p-4">
                  <p className="whitespace-pre-wrap text-sm text-slate-700">
                    {profile.styleInstructions}
                  </p>
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
