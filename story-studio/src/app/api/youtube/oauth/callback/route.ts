import { NextRequest, NextResponse } from "next/server";
import { exchangeCodeForTokens, saveOAuthConnection } from "@/lib/youtube/oauth";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const storedState = request.cookies.get("yt_oauth_state")?.value;

  if (!code || !state || state !== storedState) {
    return NextResponse.redirect(new URL("/settings/youtube?error=oauth_state", request.url));
  }

  try {
    const tokens = await exchangeCodeForTokens(code);
    if (!tokens.refresh_token) {
      return NextResponse.redirect(new URL("/settings/youtube?error=no_refresh_token", request.url));
    }
    await saveOAuthConnection("local-user", tokens);
    const response = NextResponse.redirect(new URL("/settings/youtube?connected=1", request.url));
    response.cookies.delete("yt_oauth_state");
    return response;
  } catch {
    return NextResponse.redirect(new URL("/settings/youtube?error=exchange_failed", request.url));
  }
}
