export function assertWriterInputIsolation(payload: unknown): void {
  const serialized = JSON.stringify(payload).toLowerCase();
  const forbiddenPatterns = [
    "rawtranscript",
    "supportexcerpt",
    "source transcript",
    "competitor transcript",
  ];

  for (const pattern of forbiddenPatterns) {
    if (serialized.includes(pattern.replace(/\s/g, ""))) {
      throw new Error(`Writer input isolation violation: contains "${pattern}"`);
    }
  }
}

export function buildWriterSafePayload(input: {
  brief: Record<string, unknown>;
  channelStyle: Record<string, unknown>;
  factPack: Array<{ factId: string; neutralStatement: string; storyImportance: string }>;
  blueprint: Record<string, unknown>;
  avoidanceRules: string[];
}) {
  assertWriterInputIsolation(input);
  return input;
}
