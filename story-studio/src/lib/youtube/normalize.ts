const VIDEO_ID = /^[a-zA-Z0-9_-]{11}$/;

const YOUTUBE_HOSTS = new Set([
  "youtube.com",
  "www.youtube.com",
  "m.youtube.com",
  "music.youtube.com",
]);

const SHORT_HOSTS = new Set(["youtu.be", "www.youtu.be"]);

function isVideoId(value: string | null | undefined): value is string {
  return Boolean(value && VIDEO_ID.test(value));
}

export function parseYouTubeVideoUrl(input: string): { videoId: string; canonicalUrl: string } | null {
  let url: URL;
  try {
    url = new URL(input.trim());
  } catch {
    return null;
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") return null;
  if (url.username || url.password) return null;

  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  let videoId: string | null = null;

  if (SHORT_HOSTS.has(host)) {
    const id = url.pathname.split("/").filter(Boolean)[0];
    videoId = isVideoId(id) ? id : null;
  } else if (YOUTUBE_HOSTS.has(host)) {
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] === "watch") {
      videoId = isVideoId(url.searchParams.get("v")) ? url.searchParams.get("v") : null;
    } else if (
      (parts[0] === "shorts" || parts[0] === "embed" || parts[0] === "live" || parts[0] === "v") &&
      isVideoId(parts[1])
    ) {
      videoId = parts[1];
    }
  }

  if (!videoId) return null;
  return {
    videoId,
    canonicalUrl: `https://www.youtube.com/watch?v=${videoId}`,
  };
}

export function extractYouTubeVideoId(url: string): string | null {
  return parseYouTubeVideoUrl(url)?.videoId ?? null;
}

export function normalizeYouTubeUrl(url: string): { videoId: string; canonicalUrl: string } | null {
  return parseYouTubeVideoUrl(url);
}
