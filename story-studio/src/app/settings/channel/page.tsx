import { prisma } from "@/lib/db";
import { AppShell } from "@/components/layout/app-shell";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default async function ChannelSettingsPage() {
  const profiles = await prisma.channelStyleProfile.findMany({ orderBy: { updatedAt: "desc" } });

  return (
    <AppShell active="settings">
      <h1 className="mb-2 text-3xl font-semibold">Channel Style Profile</h1>
      <p className="mb-6 max-w-2xl text-slate-600">
        Reusable voice settings for Hindi narration. Competitor transcripts are never used as style examples.
      </p>

      <div className="grid gap-4">
        {profiles.map((profile) => (
          <Card key={profile.id}>
            <CardHeader>
              <div className="flex items-center gap-2">
                <CardTitle className="text-base">{profile.name}</CardTitle>
                {profile.isDefault && <Badge>Default</Badge>}
              </div>
            </CardHeader>
            <CardContent className="grid gap-2 text-sm text-slate-600 sm:grid-cols-2">
              <p>Language: {profile.defaultLanguage}</p>
              <p>Tone: {profile.tonePreset}</p>
              <p>Pacing: {profile.charsPerMinute} chars/min</p>
              <p>Audience: {profile.audience ?? "—"}</p>
              <p>Banned: {profile.bannedPhrases ?? "—"}</p>
              <p>Preferred: {profile.preferredPhrases ?? "—"}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
