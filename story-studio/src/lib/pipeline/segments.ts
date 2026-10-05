import { prisma } from "@/lib/db";
import { parseTimestampedSegments } from "@/lib/transcript/normalize";

export async function persistTranscriptSegments(
  sourceId: string,
  text: string,
  providerSegments?: Array<{ startSec: number; duration: number; text: string }>,
): Promise<void> {
  await prisma.transcriptSegment.deleteMany({ where: { sourceId } });

  if (providerSegments && providerSegments.length > 0) {
    for (const [index, seg] of providerSegments.entries()) {
      await prisma.transcriptSegment.create({
        data: {
          sourceId,
          startSec: seg.startSec,
          endSec: seg.startSec + seg.duration,
          text: seg.text,
          orderIndex: index,
        },
      });
    }
    return;
  }

  const parsed = parseTimestampedSegments(text);
  for (const [index, seg] of parsed.entries()) {
    await prisma.transcriptSegment.create({
      data: {
        sourceId,
        startSec: seg.startSec,
        endSec: seg.endSec,
        text: seg.text,
        orderIndex: index,
      },
    });
  }
}
