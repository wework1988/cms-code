-- AlterTable
ALTER TABLE "Source" ADD COLUMN "transcriptOrigin" TEXT;

-- CreateTable
CREATE TABLE "YouTubeOAuthConnection" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ownerId" TEXT NOT NULL DEFAULT 'local-user',
    "channelId" TEXT,
    "channelTitle" TEXT,
    "accessToken" TEXT NOT NULL,
    "refreshToken" TEXT NOT NULL,
    "expiresAt" DATETIME NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "YouTubeOAuthConnection_ownerId_key" ON "YouTubeOAuthConnection"("ownerId");
