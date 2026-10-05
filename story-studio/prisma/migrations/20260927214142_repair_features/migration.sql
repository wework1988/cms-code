-- AlterTable
ALTER TABLE "NarrativeFingerprint" ADD COLUMN "presentationOrderFactIds" TEXT;

-- AlterTable
ALTER TABLE "ScriptVersion" ADD COLUMN "changeNote" TEXT;

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_FactPackItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "factId" TEXT NOT NULL,
    "neutralStatement" TEXT NOT NULL,
    "sourceClaimIds" TEXT NOT NULL,
    "sourceCount" INTEGER NOT NULL,
    "peoplePlacesDatesNumbers" TEXT,
    "storyImportance" TEXT NOT NULL,
    "userPinned" BOOLEAN NOT NULL DEFAULT false,
    "userEdited" BOOLEAN NOT NULL DEFAULT false,
    "disabled" BOOLEAN NOT NULL DEFAULT false,
    "editorNotes" TEXT,
    CONSTRAINT "FactPackItem_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_FactPackItem" ("disabled", "editorNotes", "factId", "id", "neutralStatement", "peoplePlacesDatesNumbers", "projectId", "sourceClaimIds", "sourceCount", "storyImportance", "userPinned") SELECT "disabled", "editorNotes", "factId", "id", "neutralStatement", "peoplePlacesDatesNumbers", "projectId", "sourceClaimIds", "sourceCount", "storyImportance", "userPinned" FROM "FactPackItem";
DROP TABLE "FactPackItem";
ALTER TABLE "new_FactPackItem" RENAME TO "FactPackItem";
CREATE TABLE "new_NarrativePlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "treatmentIndex" INTEGER NOT NULL,
    "centralQuestion" TEXT NOT NULL,
    "openingApproach" TEXT NOT NULL,
    "narrativeLens" TEXT NOT NULL,
    "diffExplanation" TEXT NOT NULL,
    "isSelected" BOOLEAN NOT NULL DEFAULT false,
    "isRecommended" BOOLEAN NOT NULL DEFAULT false,
    "isEdited" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "NarrativePlan_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_NarrativePlan" ("centralQuestion", "diffExplanation", "id", "isRecommended", "isSelected", "narrativeLens", "openingApproach", "projectId", "treatmentIndex") SELECT "centralQuestion", "diffExplanation", "id", "isRecommended", "isSelected", "narrativeLens", "openingApproach", "projectId", "treatmentIndex" FROM "NarrativePlan";
DROP TABLE "NarrativePlan";
ALTER TABLE "new_NarrativePlan" RENAME TO "NarrativePlan";
CREATE TABLE "new_OriginalityReport" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "overallStatus" TEXT NOT NULL,
    "phraseOverlap" TEXT NOT NULL,
    "hookSimilarity" TEXT NOT NULL,
    "orderSimilarity" TEXT NOT NULL,
    "metaphorWarnings" TEXT,
    "unsupportedClaims" TEXT,
    "recommendedAction" TEXT NOT NULL,
    "exportBlocked" BOOLEAN NOT NULL DEFAULT false,
    "exportOverride" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "OriginalityReport_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);
INSERT INTO "new_OriginalityReport" ("createdAt", "hookSimilarity", "id", "metaphorWarnings", "orderSimilarity", "overallStatus", "phraseOverlap", "projectId", "recommendedAction", "unsupportedClaims") SELECT "createdAt", "hookSimilarity", "id", "metaphorWarnings", "orderSimilarity", "overallStatus", "phraseOverlap", "projectId", "recommendedAction", "unsupportedClaims" FROM "OriginalityReport";
DROP TABLE "OriginalityReport";
ALTER TABLE "new_OriginalityReport" RENAME TO "OriginalityReport";
CREATE TABLE "new_Project" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerId" TEXT NOT NULL DEFAULT 'local-user',
    "title" TEXT NOT NULL,
    "topic" TEXT,
    "outputLanguage" TEXT NOT NULL DEFAULT 'hi',
    "targetDurationMin" INTEGER,
    "targetCharCount" INTEGER,
    "audience" TEXT,
    "genre" TEXT,
    "tone" TEXT,
    "mustCoverPoints" TEXT,
    "ctaPreference" TEXT,
    "narrativeGoal" TEXT NOT NULL DEFAULT 'recommend',
    "status" TEXT NOT NULL DEFAULT 'draft',
    "channelStyleId" TEXT,
    "promptProfileId" TEXT,
    "selectedPlanId" TEXT,
    "isDemo" BOOLEAN NOT NULL DEFAULT false,
    "exportOverride" BOOLEAN NOT NULL DEFAULT false,
    "errorMessage" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Project_channelStyleId_fkey" FOREIGN KEY ("channelStyleId") REFERENCES "ChannelStyleProfile" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Project_promptProfileId_fkey" FOREIGN KEY ("promptProfileId") REFERENCES "PromptProfile" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Project" ("audience", "channelStyleId", "createdAt", "ctaPreference", "errorMessage", "genre", "id", "isDemo", "mustCoverPoints", "narrativeGoal", "outputLanguage", "ownerId", "promptProfileId", "selectedPlanId", "status", "targetCharCount", "targetDurationMin", "title", "tone", "topic", "updatedAt") SELECT "audience", "channelStyleId", "createdAt", "ctaPreference", "errorMessage", "genre", "id", "isDemo", "mustCoverPoints", "narrativeGoal", "outputLanguage", "ownerId", "promptProfileId", "selectedPlanId", "status", "targetCharCount", "targetDurationMin", "title", "tone", "topic", "updatedAt" FROM "Project";
DROP TABLE "Project";
ALTER TABLE "new_Project" RENAME TO "Project";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
