export function extractJson(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "{}";

  const fenced = trimmed.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenced?.[1]?.trim()) return fenced[1].trim();

  const start = trimmed.indexOf("{");
  const end = trimmed.lastIndexOf("}");
  if (start >= 0 && end > start) return trimmed.slice(start, end + 1);

  const arrStart = trimmed.indexOf("[");
  const arrEnd = trimmed.lastIndexOf("]");
  if (arrStart >= 0 && arrEnd > arrStart) return trimmed.slice(arrStart, arrEnd + 1);

  return trimmed;
}

/** Close an unterminated JSON string if the payload ends mid-value. */
function closeOpenString(text: string): string {
  let inString = false;
  let escaped = false;
  for (const ch of text) {
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === '"') inString = !inString;
  }
  return inString ? `${text}"` : text;
}

/** Attempt to close truncated JSON objects/arrays. */
export function repairTruncatedJson(text: string): string {
  let repaired = closeOpenString(text.trim());
  if (!repaired) return "{}";

  if (repaired.endsWith(",")) repaired = repaired.slice(0, -1);

  const stack: Array<"object" | "array"> = [];
  let inString = false;
  let escaped = false;

  for (const ch of repaired) {
    if (escaped) {
      escaped = false;
      continue;
    }
    if (ch === "\\") {
      escaped = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === "{") stack.push("object");
    else if (ch === "[") stack.push("array");
    else if (ch === "}") stack.pop();
    else if (ch === "]") stack.pop();
  }

  while (stack.length > 0) {
    const frame = stack.pop();
    repaired += frame === "object" ? "}" : "]";
  }

  return repaired;
}

export function parseJsonSafe(text: string): unknown {
  const extracted = extractJson(text);
  if (!extracted) return {};

  try {
    return JSON.parse(extracted);
  } catch {
    try {
      return JSON.parse(repairTruncatedJson(extracted));
    } catch {
      return {};
    }
  }
}
