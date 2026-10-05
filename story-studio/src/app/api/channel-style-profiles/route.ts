import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";

export async function GET() {
  const profiles = await prisma.channelStyleProfile.findMany({
    orderBy: [{ isDefault: "desc" }, { updatedAt: "desc" }],
  });
  return NextResponse.json(profiles);
}
