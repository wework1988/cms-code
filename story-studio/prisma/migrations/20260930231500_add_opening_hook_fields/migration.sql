-- Add opening hook preferences for project-level narrative settings.
ALTER TABLE "Project" ADD COLUMN "openingHook" TEXT;
ALTER TABLE "Project" ADD COLUMN "openingHookCustom" TEXT;
ALTER TABLE "Project" ADD COLUMN "narrativeApproachCustom" TEXT;
