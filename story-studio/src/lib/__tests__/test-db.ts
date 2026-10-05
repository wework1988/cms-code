import { PrismaClient } from "@prisma/client";
import { execSync } from "child_process";
import path from "path";

let prisma: PrismaClient | null = null;

export function getTestPrisma(): PrismaClient {
  if (!prisma) {
    process.env.DATABASE_URL = `file:${path.join(process.cwd(), "prisma", "test.db")}`;
    execSync("npx prisma db push --skip-generate", {
      cwd: process.cwd(),
      env: process.env,
      stdio: "ignore",
    });
    prisma = new PrismaClient();
  }
  return prisma;
}

export async function resetTestDb() {
  const db = getTestPrisma();
  await db.originalityFinding.deleteMany();
  await db.originalityReport.deleteMany();
  await db.scriptParagraphTrace.deleteMany();
  await db.scriptVersion.deleteMany();
  await db.narrativeBeat.deleteMany();
  await db.narrativePlan.deleteMany();
  await db.narrativeFingerprint.deleteMany();
  await db.factPackItem.deleteMany();
  await db.claim.deleteMany();
  await db.transcriptSegment.deleteMany();
  await db.source.deleteMany();
  await db.pipelineRun.deleteMany();
  await db.project.deleteMany();
  await db.youTubeOAuthConnection.deleteMany();
}
