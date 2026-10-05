import { NextResponse } from "next/server";
import { prisma } from "@/lib/db";
import { updateProjectSettingsSchema } from "@/lib/schemas";

const PLAN_AFFECTING_FIELDS = new Set([
  "title",
  "topic",
  "outputLanguage",
  "audience",
  "genre",
  "tone",
  "mustCoverPoints",
  "narrativeGoal",
  "narrativeApproachCustom",
  "openingHook",
  "openingHookCustom",
  "promptProfileId",
]);

function normalizeOptionalString(value: string | null | undefined): string | null | undefined {
  if (value === undefined) return undefined;
  if (value === null) return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function asFieldErrors(error: unknown) {
  if (!(error instanceof Error) || !("issues" in error)) return undefined;
  const issues = (error as { issues?: Array<{ path?: Array<string | number>; message?: string }> }).issues;
  if (!Array.isArray(issues)) return undefined;
  return issues.reduce<Record<string, string>>((acc, issue) => {
    const key = String(issue.path?.[0] ?? "form");
    if (!acc[key]) acc[key] = issue.message ?? "Invalid value";
    return acc;
  }, {});
}

export async function GET(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const project = await prisma.project.findUnique({
    where: { id: projectId },
    include: {
      sources: true,
      claims: true,
      factPackItems: true,
      narrativePlans: { include: { beats: { orderBy: { beatNumber: "asc" } } }, orderBy: { treatmentIndex: "asc" } },
      scriptVersions: {
        where: { isCurrent: true },
        include: { paragraphs: { orderBy: { paragraphIndex: "asc" } } },
        take: 1,
      },
      originalityReports: {
        include: { findings: true },
        orderBy: { createdAt: "desc" },
        take: 1,
      },
      pipelineRuns: { orderBy: { startedAt: "desc" }, take: 10 },
      channelStyle: true,
      promptProfile: true,
    },
  });

  if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });
  return NextResponse.json(project);
}

export async function PATCH(request: Request, { params }: { params: Promise<{ projectId: string }> }) {
  try {
    const { projectId } = await params;
    const parsed = updateProjectSettingsSchema.safeParse(await request.json());
    if (!parsed.success) {
      return NextResponse.json(
        { error: "Invalid settings payload", fieldErrors: asFieldErrors(parsed.error) },
        { status: 400 },
      );
    }
    const body = parsed.data;
    const existing = await prisma.project.findUniqueOrThrow({ where: { id: projectId } });

    if (body.promptProfileId) {
      const profileExists = await prisma.promptProfile.findUnique({ where: { id: body.promptProfileId } });
      if (!profileExists) {
        return NextResponse.json(
          { error: "Invalid prompt profile.", fieldErrors: { promptProfileId: "Prompt profile not found." } },
          { status: 400 },
        );
      }
    }
    if (body.channelStyleId) {
      const channelExists = await prisma.channelStyleProfile.findUnique({ where: { id: body.channelStyleId } });
      if (!channelExists) {
        return NextResponse.json(
          { error: "Invalid channel style profile.", fieldErrors: { channelStyleId: "Channel style not found." } },
          { status: 400 },
        );
      }
    }

    const nextData = {
      ...(body.title !== undefined ? { title: body.title.trim() } : {}),
      ...(body.topic !== undefined ? { topic: normalizeOptionalString(body.topic) } : {}),
      ...(body.outputLanguage !== undefined
        ? { outputLanguage: normalizeOptionalString(body.outputLanguage) ?? "hi" }
        : {}),
      ...(body.targetCharCount !== undefined ? { targetCharCount: body.targetCharCount } : {}),
      ...(body.audience !== undefined ? { audience: normalizeOptionalString(body.audience) } : {}),
      ...(body.genre !== undefined ? { genre: normalizeOptionalString(body.genre) } : {}),
      ...(body.tone !== undefined ? { tone: normalizeOptionalString(body.tone) } : {}),
      ...(body.mustCoverPoints !== undefined
        ? { mustCoverPoints: normalizeOptionalString(body.mustCoverPoints) }
        : {}),
      ...(body.openingHook !== undefined ? { openingHook: body.openingHook ?? "auto" } : {}),
      ...(body.openingHookCustom !== undefined
        ? { openingHookCustom: normalizeOptionalString(body.openingHookCustom) }
        : {}),
      ...(body.ctaPreference !== undefined ? { ctaPreference: body.ctaPreference } : {}),
      ...(body.ctaChannelName !== undefined
        ? { ctaChannelName: normalizeOptionalString(body.ctaChannelName) }
        : {}),
      ...(body.ctaClosingWording !== undefined
        ? { ctaClosingWording: normalizeOptionalString(body.ctaClosingWording) }
        : {}),
      ...(body.narrativeGoal !== undefined
        ? { narrativeGoal: normalizeOptionalString(body.narrativeGoal) ?? "auto" }
        : {}),
      ...(body.narrativeApproachCustom !== undefined
        ? { narrativeApproachCustom: normalizeOptionalString(body.narrativeApproachCustom) }
        : {}),
      ...(body.channelStyleId !== undefined ? { channelStyleId: body.channelStyleId } : {}),
      ...(body.promptProfileId !== undefined ? { promptProfileId: body.promptProfileId } : {}),
    };

    const generationSettingsChanged = Object.entries(nextData).some(([key, value]) => {
      const oldValue = (existing as unknown as Record<string, unknown>)[key];
      return oldValue !== value;
    });
    const planSettingsChanged = Object.entries(nextData).some(
      ([key, value]) =>
        PLAN_AFFECTING_FIELDS.has(key) &&
        (existing as unknown as Record<string, unknown>)[key] !== value,
    );

    const project = await prisma.project.update({
      where: { id: projectId },
      data: {
        ...nextData,
        ...(generationSettingsChanged
          ? {
              status: planSettingsChanged ? "fact_pack_ready" : "narrative_plan_ready",
              selectedPlanId: planSettingsChanged ? null : existing.selectedPlanId,
              lengthStatus: null,
              errorMessage:
                "Settings updated. Your current script was generated with previous settings. Regenerate to apply these changes.",
            }
          : {}),
      },
    });
    if (planSettingsChanged) {
      await prisma.narrativePlan.updateMany({
        where: { projectId },
        data: { isSelected: false },
      });
    }
    return NextResponse.json({
      ...project,
      generationSettingsChanged,
      planSettingsChanged,
      regenerationScope: generationSettingsChanged
        ? planSettingsChanged
          ? "plan_and_script"
          : "script_only"
        : "none",
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Invalid request";
    return NextResponse.json({ error: message, fieldErrors: asFieldErrors(error) }, { status: 400 });
  }
}

export async function DELETE(_: Request, { params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  const existing = await prisma.project.findUnique({ where: { id: projectId }, select: { id: true } });
  if (!existing) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }
  await prisma.project.delete({ where: { id: projectId } });
  return NextResponse.json({ ok: true, projectId });
}
