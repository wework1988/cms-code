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

  it("rejects lookalike hosts and non-YouTube links", () => {
    expect(extractYouTubeVideoId("https://www.youtube.com.evil.com/watch?v=dQw4w9WgXcQ")).toBeNull();
    expect(extractYouTubeVideoId("https://evil.example/watch?v=dQw4w9WgXcQ")).toBeNull();
    expect(extractYouTubeVideoId("https://evil.example/?u=https://www.youtube.com/watch?v=dQw4w9WgXcQ")).toBeNull();
    expect(extractYouTubeVideoId("not a url")).toBeNull();
  });

  it("returns canonical URL", () => {
    expect(normalizeYouTubeUrl("https://youtu.be/abc12345678")).toEqual({
      videoId: "abc12345678",
      canonicalUrl: "https://www.youtube.com/watch?v=abc12345678",
    });
  });
});
