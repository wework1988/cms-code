-- CreateTable
CREATE TABLE "Project" (
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
    "errorMessage" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Project_channelStyleId_fkey" FOREIGN KEY ("channelStyleId") REFERENCES "ChannelStyleProfile" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Project_promptProfileId_fkey" FOREIGN KEY ("promptProfileId") REFERENCES "PromptProfile" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Source" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "kind" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "url" TEXT,
    "videoId" TEXT,
    "sourceLabel" TEXT,
    "language" TEXT,
    "transcriptStatus" TEXT NOT NULL DEFAULT 'waiting',
    "rawTranscript" TEXT,
    "normalizedHash" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Source_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TranscriptSegment" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "sourceId" TEXT NOT NULL,
    "startSec" REAL,
    "endSec" REAL,
    "text" TEXT NOT NULL,
    "orderIndex" INTEGER NOT NULL,
    CONSTRAINT "TranscriptSegment_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Claim" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "sourceId" TEXT NOT NULL,
    "neutralClaim" TEXT NOT NULL,
    "claimType" TEXT NOT NULL,
    "peoplePlacesDatesNumbers" TEXT,
    "timestampStart" REAL,
    "timestampEnd" REAL,
    "supportExcerpt" TEXT NOT NULL,
    "sourceCertainty" TEXT NOT NULL,
    "storyRelevance" TEXT NOT NULL,
    "requiredByUser" BOOLEAN NOT NULL DEFAULT false,
    "disabled" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "Claim_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "Claim_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "FactPackItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "factId" TEXT NOT NULL,
    "neutralStatement" TEXT NOT NULL,
    "sourceClaimIds" TEXT NOT NULL,
    "sourceCount" INTEGER NOT NULL,
    "peoplePlacesDatesNumbers" TEXT,
    "storyImportance" TEXT NOT NULL,
    "userPinned" BOOLEAN NOT NULL DEFAULT false,
    "disabled" BOOLEAN NOT NULL DEFAULT false,
    "editorNotes" TEXT,
    CONSTRAINT "FactPackItem_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NarrativeFingerprint" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "sourceId" TEXT NOT NULL,
    "openingType" TEXT NOT NULL,
    "openingFunction" TEXT NOT NULL,
    "presentationOrder" TEXT NOT NULL,
    "dominantNarrativeLens" TEXT NOT NULL,
    "turningPointType" TEXT NOT NULL,
    "recurringDevices" TEXT NOT NULL,
    "distinctiveMetaphorsOrPhrases" TEXT NOT NULL,
    "endingFunction" TEXT NOT NULL,
    "titleAndThumbnailPattern" TEXT NOT NULL,
    CONSTRAINT "NarrativeFingerprint_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "NarrativeFingerprint_sourceId_fkey" FOREIGN KEY ("sourceId") REFERENCES "Source" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NarrativePlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "treatmentIndex" INTEGER NOT NULL,
    "centralQuestion" TEXT NOT NULL,
    "openingApproach" TEXT NOT NULL,
    "narrativeLens" TEXT NOT NULL,
    "diffExplanation" TEXT NOT NULL,
    "isSelected" BOOLEAN NOT NULL DEFAULT false,
    "isRecommended" BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT "NarrativePlan_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "NarrativeBeat" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "planId" TEXT NOT NULL,
    "beatNumber" INTEGER NOT NULL,
    "purpose" TEXT NOT NULL,
    "shortDescription" TEXT NOT NULL,
    "claimIds" TEXT NOT NULL,
    "narrativeRole" TEXT NOT NULL,
    "proposedVisualIdea" TEXT,
    "expectedDurationSeconds" INTEGER,
    CONSTRAINT "NarrativeBeat_planId_fkey" FOREIGN KEY ("planId") REFERENCES "NarrativePlan" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ScriptVersion" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "versionNumber" INTEGER NOT NULL,
    "content" TEXT NOT NULL,
    "charCount" INTEGER NOT NULL,
    "estDurationSec" INTEGER,
    "isCurrent" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ScriptVersion_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ScriptParagraphTrace" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "scriptVersionId" TEXT NOT NULL,
    "paragraphIndex" INTEGER NOT NULL,
    "paragraphText" TEXT NOT NULL,
    "factIds" TEXT NOT NULL,
    CONSTRAINT "ScriptParagraphTrace_scriptVersionId_fkey" FOREIGN KEY ("scriptVersionId") REFERENCES "ScriptVersion" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "OriginalityReport" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "overallStatus" TEXT NOT NULL,
    "phraseOverlap" TEXT NOT NULL,
    "hookSimilarity" TEXT NOT NULL,
    "orderSimilarity" TEXT NOT NULL,
    "metaphorWarnings" TEXT,
    "unsupportedClaims" TEXT,
    "recommendedAction" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "OriginalityReport_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "OriginalityFinding" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "reportId" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "explanation" TEXT NOT NULL,
    "affectedSection" TEXT NOT NULL,
    "remedy" TEXT,
    CONSTRAINT "OriginalityFinding_reportId_fkey" FOREIGN KEY ("reportId") REFERENCES "OriginalityReport" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "PipelineRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "projectId" TEXT NOT NULL,
    "stage" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "errorMessage" TEXT,
    "startedAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "finishedAt" DATETIME,
    CONSTRAINT "PipelineRun_projectId_fkey" FOREIGN KEY ("projectId") REFERENCES "Project" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "ChannelStyleProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerId" TEXT NOT NULL DEFAULT 'local-user',
    "name" TEXT NOT NULL,
    "defaultLanguage" TEXT NOT NULL DEFAULT 'hi',
    "audience" TEXT,
    "vocabularyNotes" TEXT,
    "charsPerMinute" INTEGER NOT NULL DEFAULT 900,
    "tonePreset" TEXT NOT NULL DEFAULT 'explanatory',
    "bannedPhrases" TEXT,
    "preferredPhrases" TEXT,
    "channelCta" TEXT,
    "signOff" TEXT,
    "styleExamples" TEXT,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "PromptProfile" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerId" TEXT NOT NULL DEFAULT 'local-user',
    "name" TEXT NOT NULL,
    "genre" TEXT,
    "styleInstructions" TEXT NOT NULL,
    "targetLanguage" TEXT NOT NULL DEFAULT 'hi',
    "audience" TEXT,
    "pacingNotes" TEXT,
    "ctaNotes" TEXT,
    "titleNotes" TEXT,
    "thumbnailNotes" TEXT,
    "visualNotes" TEXT,
    "preferredVocab" TEXT,
    "bannedPhrases" TEXT,
    "version" INTEGER NOT NULL DEFAULT 1,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "NarrativeFingerprint_sourceId_key" ON "NarrativeFingerprint"("sourceId");
