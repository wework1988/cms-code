"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type OAuthStatus = {
  configured: boolean;
  connected: boolean;
  channelId: string | null;
  channelTitle: string | null;
};

export default function YouTubeSettingsPage() {
  const [status, setStatus] = useState<OAuthStatus | null>(null);

  useEffect(() => {
    fetch("/api/youtube/oauth/status")
      .then((r) => r.json())
      .then(setStatus);
  }, []);

  return (
    <AppShell active="youtube">
      <h1 className="mb-2 text-3xl font-semibold">YouTube OAuth</h1>
      <p className="mb-6 max-w-2xl text-slate-600">
        Connect your YouTube channel to fetch <strong>official captions</strong> for videos you own or manage.
        Story Studio does not scrape third-party videos and does not fetch captions for arbitrary URLs.
      </p>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Connection status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {!status ? (
            <p className="text-slate-500">Loading…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge className={status.configured ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"}>
                  OAuth {status.configured ? "configured" : "not configured"}
                </Badge>
                <Badge className={status.connected ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-700"}>
                  {status.connected ? "Connected" : "Not connected"}
                </Badge>
              </div>
              {status.connected && status.channelTitle && (
                <p>Channel: <strong>{status.channelTitle}</strong></p>
              )}
              {!status.configured && (
                <p className="text-slate-600">
                  Add <code>GOOGLE_CLIENT_ID</code>, <code>GOOGLE_CLIENT_SECRET</code>, and{" "}
                  <code>GOOGLE_OAUTH_REDIRECT_URI</code> to <code>.env</code>.
                </p>
              )}
              {status.configured && (
                <Button asChild>
                  <a href="/api/youtube/oauth/authorize">Connect YouTube channel</a>
                </Button>
              )}
              <p className="text-slate-500">
                Manual transcript paste remains the default for all sources, including YouTube reference URLs.
              </p>
            </>
          )}
        </CardContent>
      </Card>

      <p className="mt-6 text-sm text-slate-500">
        <Link href="/" className="underline">← Back to dashboard</Link>
      </p>
    </AppShell>
  );
}
