import { NextResponse } from "next/server";
import { getYouTubeAuthorizeUrl, isYouTubeOAuthConfigured } from "@/lib/youtube/oauth";

export async function GET() {
  if (!isYouTubeOAuthConfigured()) {
    return NextResponse.json(
      { error: "YouTube OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_OAUTH_REDIRECT_URI." },
      { status: 503 },
    );
  }

  const state = crypto.randomUUID();
  const url = getYouTubeAuthorizeUrl(state);

  const response = NextResponse.redirect(url);
  response.cookies.set("yt_oauth_state", state, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });
  return response;
}
