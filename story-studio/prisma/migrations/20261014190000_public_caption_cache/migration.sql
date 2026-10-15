-- AlterTable
ALTER TABLE "Source" ADD COLUMN "captionKind" TEXT;
ALTER TABLE "Source" ADD COLUMN "transcriptRevision" INTEGER NOT NULL DEFAULT 0;

-- CreateTable
CREATE TABLE "PublicCaptionCache" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "cacheKey" TEXT NOT NULL,
    "videoId" TEXT NOT NULL,
    "language" TEXT NOT NULL,
    "captionKind" TEXT NOT NULL,
    "text" TEXT NOT NULL,
    "segmentsJson" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "PublicCaptionCache_cacheKey_key" ON "PublicCaptionCache"("cacheKey");
CREATE INDEX "PublicCaptionCache_videoId_language_idx" ON "PublicCaptionCache"("videoId", "language");
