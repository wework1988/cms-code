import { describe, expect, it } from "vitest";
import { extractYouTubeVideoId, normalizeYouTubeUrl } from "@/lib/youtube/normalize";

describe("YouTube URL normalization", () => {
  it("extracts watch URL video IDs", () => {
    expect(extractYouTubeVideoId("https://www.youtube.com/watch?v=dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
  });

  it("extracts youtu.be IDs", () => {
    expect(extractYouTubeVideoId("https://youtu.be/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
  });

  it("extracts shorts IDs", () => {
    expect(extractYouTubeVideoId("https://www.youtube.com/shorts/dQw4w9WgXcQ")).toBe("dQw4w9WgXcQ");
  });

  it("returns canonical URL", () => {
    expect(normalizeYouTubeUrl("https://youtu.be/abc12345678")).toEqual({
      videoId: "abc12345678",
      canonicalUrl: "https://www.youtube.com/watch?v=abc12345678",
    });
  });
});
