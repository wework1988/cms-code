const DEFAULT_MAX = 12_000;

export function truncateTranscriptForLlm(transcript: string, maxChars = DEFAULT_MAX): string {
  const text = transcript.trim();
  if (text.length <= maxChars) return text;

  const headSize = Math.floor(maxChars * 0.6);
  const tailSize = Math.floor(maxChars * 0.35);
  const head = text.slice(0, headSize);
  const tail = text.slice(-tailSize);

  return `${head}\n\n[... transcript truncated for LLM input ...]\n\n${tail}`;
}

export function truncateTranscriptForFingerprint(transcript: string): string {
  return truncateTranscriptForLlm(transcript, 8_000);
}
