import { PrismaClient } from "@prisma/client";

const prisma = new PrismaClient();

async function main() {
  await prisma.channelStyleProfile.deleteMany();
  await prisma.promptProfile.deleteMany();

  await prisma.channelStyleProfile.create({
    data: {
      name: "Default Hindi Documentary",
      defaultLanguage: "hi",
      audience: "General Hindi YouTube audience",
      vocabularyNotes: "Use Devanagari Hindi with familiar English terms where clearer.",
      charsPerMinute: 900,
      tonePreset: "explanatory",
      bannedPhrases: "दोस्तों, like and subscribe",
      preferredPhrases: "सवाल यह है, एक बार रुकिए",
      channelCta: "अगली कड़ी में",
      isDefault: true,
    },
  });

  await prisma.promptProfile.create({
    data: {
      name: "General Documentary",
      genre: "History / Biography",
      styleInstructions:
        "Write calm, cinematic explanatory Hindi. Open with a fresh question. Avoid sensational hooks. Use short spoken sentences.",
      targetLanguage: "hi",
      pacingNotes: "Medium pacing, ~900 chars/min",
      isDefault: true,
    },
  });

  await prisma.promptProfile.create({
    data: {
      name: "Crime / Investigation",
      genre: "True Crime",
      styleInstructions:
        "Use restrained tension and victim-sensitive language. Do not invent dialogue, forensic twists, villains, or unsupported facts.",
      targetLanguage: "hi",
      pacingNotes: "Slightly slower on sensitive beats",
    },
  });
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
