import { NextResponse } from "next/server";
import { getOAuthStatus } from "@/lib/youtube/oauth";

export async function GET() {
  return NextResponse.json(await getOAuthStatus());
}
