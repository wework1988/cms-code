import { createHash } from "crypto";

const DEBRIS_PATTERNS = [
  /^subscribe\s+to\s+/gim,
  /^like\s+and\s+share/gim,
  /^follow\s+us\s+on/gim,
  /^\[music\]/gim,
  /^\[applause\]/gim,
  /^ignore\s+previous\s+instructions/gim,
  /^system\s*:/gim,
];

export function normalizeTranscript(raw: string): string {
  let text = raw.replace(/\r\n/g, "\n").trim();
  for (const pattern of DEBRIS_PATTERNS) {
    text = text.replace(pattern, "");
  }
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .join("\n");
}

export function hashTranscript(text: string): string {
  return createHash("sha256").update(normalizeTranscript(text)).digest("hex");
}

export function parseTimestampedSegments(text: string): Array<{ startSec: number | null; endSec: number | null; text: string }> {
  const lines = normalizeTranscript(text).split("\n");
  const segments: Array<{ startSec: number | null; endSec: number | null; text: string }> = [];
  const tsPattern = /^\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?\s*(.+)$/;

  for (const line of lines) {
    const match = line.match(tsPattern);
    if (match) {
      segments.push({
        startSec: parseTimestamp(match[1]),
        endSec: null,
        text: match[2],
      });
    } else {
      segments.push({ startSec: null, endSec: null, text: line });
    }
  }
  return segments;
}

function parseTimestamp(value: string): number {
  const parts = value.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return parts[0] * 60 + parts[1];
}
