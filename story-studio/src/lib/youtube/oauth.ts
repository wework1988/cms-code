import { prisma } from "@/lib/db";

const YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.force-ssl";
const TOKEN_URL = "https://oauth2.googleapis.com/token";

export function isYouTubeOAuthConfigured(): boolean {
  return Boolean(
    process.env.GOOGLE_CLIENT_ID?.trim() &&
      process.env.GOOGLE_CLIENT_SECRET?.trim() &&
      process.env.GOOGLE_OAUTH_REDIRECT_URI?.trim(),
  );
}

export function getYouTubeAuthorizeUrl(state: string): string {
  const clientId = process.env.GOOGLE_CLIENT_ID!;
  const redirectUri = process.env.GOOGLE_OAUTH_REDIRECT_URI!;
  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    response_type: "code",
    scope: YOUTUBE_SCOPE,
    access_type: "offline",
    prompt: "consent",
    state,
  });
  return `https://accounts.google.com/o/oauth2/v2/auth?${params.toString()}`;
}

export async function exchangeCodeForTokens(code: string) {
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      redirect_uri: process.env.GOOGLE_OAUTH_REDIRECT_URI!,
      grant_type: "authorization_code",
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`OAuth token exchange failed: ${body}`);
  }

  return (await res.json()) as {
    access_token: string;
    refresh_token?: string;
    expires_in: number;
  };
}

export async function refreshAccessToken(refreshToken: string) {
  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      refresh_token: refreshToken,
      client_id: process.env.GOOGLE_CLIENT_ID!,
      client_secret: process.env.GOOGLE_CLIENT_SECRET!,
      grant_type: "refresh_token",
    }),
  });

  if (!res.ok) {
    throw new Error("Failed to refresh YouTube OAuth token");
  }

  return (await res.json()) as { access_token: string; expires_in: number };
}

export async function getValidAccessToken(ownerId = "local-user"): Promise<string | null> {
  const conn = await prisma.youTubeOAuthConnection.findUnique({ where: { ownerId } });
  if (!conn) return null;

  if (conn.expiresAt.getTime() > Date.now() + 60_000) {
    return conn.accessToken;
  }

  const refreshed = await refreshAccessToken(conn.refreshToken);
  const expiresAt = new Date(Date.now() + refreshed.expires_in * 1000);

  await prisma.youTubeOAuthConnection.update({
    where: { ownerId },
    data: { accessToken: refreshed.access_token, expiresAt },
  });

  return refreshed.access_token;
}

export async function saveOAuthConnection(
  ownerId: string,
  tokens: { access_token: string; refresh_token?: string; expires_in: number },
) {
  const channel = await fetchYouTubeChannel(tokens.access_token);
  const expiresAt = new Date(Date.now() + tokens.expires_in * 1000);

  await prisma.youTubeOAuthConnection.upsert({
    where: { ownerId },
    create: {
      ownerId,
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token ?? "",
      expiresAt,
      channelId: channel?.id,
      channelTitle: channel?.title,
    },
    update: {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token ?? undefined,
      expiresAt,
      channelId: channel?.id,
      channelTitle: channel?.title,
    },
  });
}

async function fetchYouTubeChannel(accessToken: string): Promise<{ id: string; title: string } | null> {
  const res = await fetch(
    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
    { headers: { Authorization: `Bearer ${accessToken}` } },
  );
  if (!res.ok) return null;
  const json = (await res.json()) as { items?: Array<{ id: string; snippet?: { title?: string } }> };
  const item = json.items?.[0];
  if (!item) return null;
  return { id: item.id, title: item.snippet?.title ?? item.id };
}

export async function getOAuthStatus(ownerId = "local-user") {
  const conn = await prisma.youTubeOAuthConnection.findUnique({ where: { ownerId } });
  return {
    configured: isYouTubeOAuthConfigured(),
    connected: Boolean(conn?.refreshToken),
    channelId: conn?.channelId ?? null,
    channelTitle: conn?.channelTitle ?? null,
  };
}
