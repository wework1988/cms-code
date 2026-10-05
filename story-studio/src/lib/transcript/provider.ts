/** Manual transcript mode is the default. No third-party caption scraping. */

export interface TranscriptResult {
  text: string;
  language?: string;
  segments?: Array<{ startSec: number; duration: number; text: string }>;
}

export interface TranscriptProvider {
  fetchTranscript(videoId: string): Promise<TranscriptResult | null>;
}

class ManualTranscriptProvider implements TranscriptProvider {
  async fetchTranscript(): Promise<TranscriptResult | null> {
    return null;
  }
}

const manualProvider = new ManualTranscriptProvider();

/** Always returns manual provider — transcripts must be pasted or fetched via official OAuth. */
export function getTranscriptProvider(): TranscriptProvider {
  return manualProvider;
}

export function isManualTranscriptMode(): boolean {
  return true;
}
