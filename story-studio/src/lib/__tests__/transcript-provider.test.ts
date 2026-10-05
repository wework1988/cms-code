import { describe, expect, it } from "vitest";
import { getTranscriptProvider, isManualTranscriptMode } from "@/lib/transcript/provider";

describe("transcript provider", () => {
  it("defaults to manual mode with no auto-fetch", async () => {
    expect(isManualTranscriptMode()).toBe(true);
    const provider = getTranscriptProvider();
    const result = await provider.fetchTranscript("dQw4w9WgXcQ");
    expect(result).toBeNull();
  });
});
