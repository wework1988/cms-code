const YOUTUBE_PATTERNS = [
  /(?:youtube\.com\/watch\?v=|youtube\.com\/watch\?.*&v=)([a-zA-Z0-9_-]{11})/,
  /youtu\.be\/([a-zA-Z0-9_-]{11})/,
  /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/,
  /youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
  /youtube\.com\/live\/([a-zA-Z0-9_-]{11})/,
];

export function extractYouTubeVideoId(url: string): string | null {
  const trimmed = url.trim();
  for (const pattern of YOUTUBE_PATTERNS) {
    const match = trimmed.match(pattern);
    if (match?.[1]) return match[1];
  }
  return null;
}

export function normalizeYouTubeUrl(url: string): { videoId: string; canonicalUrl: string } | null {
  const videoId = extractYouTubeVideoId(url);
  if (!videoId) return null;
  return {
    videoId,
    canonicalUrl: `https://www.youtube.com/watch?v=${videoId}`,
  };
}
