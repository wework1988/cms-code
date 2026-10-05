-- AlterTable
ALTER TABLE "Project" ADD COLUMN "ctaChannelName" TEXT;
ALTER TABLE "Project" ADD COLUMN "ctaClosingWording" TEXT;

-- AlterTable
ALTER TABLE "ScriptParagraphTrace" ADD COLUMN "paragraphRole" TEXT;
