import { normalizeTranscript } from "@/lib/transcript/normalize";
import type { TranscriptResult } from "@/lib/transcript/provider";
import { getValidAccessToken } from "@/lib/youtube/oauth";

/**
 * Fetch captions via the official YouTube Data API (OAuth).
 * Only works for videos owned by or authorized for the authenticated channel.
 * Never used for arbitrary third-party videos.
 */
export async function fetchOfficialYouTubeCaptions(
  videoId: string,
  ownerId = "local-user",
): Promise<TranscriptResult> {
  const accessToken = await getValidAccessToken(ownerId);
  if (!accessToken) {
    throw new Error(
      "YouTube OAuth not connected. Connect your channel to fetch captions for owned videos only.",
    );
  }

  await assertVideoAccessible(videoId, accessToken);

  const listRes = await fetch(
    `https://www.googleapis.com/youtube/v3/captions?part=snippet&videoId=${encodeURIComponent(videoId)}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );

  if (listRes.status === 403) {
    throw new Error(
      "Cannot access captions for this video. Official OAuth captions are only for videos you own or manage.",
    );
  }
  if (!listRes.ok) {
    throw new Error(`YouTube captions.list failed (${listRes.status})`);
  }

  const listJson = (await listRes.json()) as {
    items?: Array<{ id: string; snippet?: { language?: string; trackKind?: string } }>;
  };

  const tracks = listJson.items ?? [];
  if (tracks.length === 0) {
    throw new Error("No captions available for this owned/authorized video.");
  }

  const track =
    tracks.find((t) => t.snippet?.language?.startsWith("hi")) ??
    tracks.find((t) => t.snippet?.language?.startsWith("en")) ??
    tracks[0];

  const downloadRes = await fetch(
    `https://www.googleapis.com/youtube/v3/captions/${track.id}?tfmt=vtt`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );

  if (downloadRes.status === 403) {
    throw new Error(
      "Caption download denied. This video may not belong to your connected YouTube channel.",
    );
  }
  if (!downloadRes.ok) {
    throw new Error(`YouTube captions.download failed (${downloadRes.status})`);
  }

  const vtt = await downloadRes.text();
  const segments = parseVtt(vtt);
  const text = normalizeTranscript(segments.map((s) => s.text).join("\n"));

  return {
    text,
    language: track.snippet?.language,
    segments: segments.map((s) => ({
      startSec: s.startSec,
      duration: s.duration,
      text: s.text,
    })),
  };
}

async function assertVideoAccessible(videoId: string, accessToken: string): Promise<void> {
  const res = await fetch(
    `https://www.googleapis.com/youtube/v3/videos?part=snippet&id=${encodeURIComponent(videoId)}`,
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );

  if (!res.ok) {
    throw new Error(`YouTube videos.list failed (${res.status})`);
  }

  const json = (await res.json()) as { items?: unknown[] };
  if (!json.items?.length) {
    throw new Error("Video not found or not accessible with your connected YouTube account.");
  }
}

function parseVtt(vtt: string): Array<{ startSec: number; duration: number; text: string }> {
  const lines = vtt.replace(/\r\n/g, "\n").split("\n");
  const segments: Array<{ startSec: number; duration: number; text: string }> = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i].trim();
    if (line.includes("-->")) {
      const [startRaw, endRaw] = line.split("-->").map((s) => s.trim());
      const startSec = parseVttTimestamp(startRaw);
      const endSec = parseVttTimestamp(endRaw);
      i++;
      const textLines: string[] = [];
      while (i < lines.length && lines[i].trim() !== "") {
        textLines.push(lines[i].trim());
        i++;
      }
      const text = textLines.join(" ").replace(/<[^>]+>/g, "");
      if (text) {
        segments.push({ startSec, duration: Math.max(0, endSec - startSec), text });
      }
    }
    i++;
  }

  return segments;
}

function parseVttTimestamp(value: string): number {
  const cleaned = value.split(" ")[0];
  const parts = cleaned.split(":").map(parseFloat);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return parts[0] * 60 + parts[1];
}

export function isOfficialCaptionsAvailable(): boolean {
  return Boolean(process.env.GOOGLE_CLIENT_ID?.trim() && process.env.GOOGLE_CLIENT_SECRET?.trim());
}
