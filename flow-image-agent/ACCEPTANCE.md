# Acceptance evidence — Pakistan Army scenes 1–2

Date: 2026-10-08

## What was verified

| Check | Result |
|---|---|
| Prompt parse of `general/165-pakistan-army/image-prompts/image-prompts-only.txt` | 202 scenes, `\|\|` delimited |
| Helper lists story with progress | `165-pakistan-army` · 2/202 images |
| Preview first-two | scenes `[1, 2]`, output `…/images/` |
| 2K landscape dimensions | **2752×1536** JPEG (not assumed 2048-wide) |
| Saved filenames | `001.jpg`, `002.jpg` |
| Manifest statuses | both `completed` |
| Resume / claim-next | returns `reason: "done"` (skips completed) |
| Unit tests | **20 passed** |

## Files

```text
general/165-pakistan-army/images/001.jpg  2752×1536  JPEG
general/165-pakistan-army/images/002.jpg  2752×1536  JPEG
general/165-pakistan-army/images/generation-manifest.json
```

Sources were Flow **2K Upscaled** downloads already present in Chrome Downloads from the earlier live Flow session (Nano Banana 2.1 / 16:9), ingested via `scripts/seed_acceptance_from_downloads.py` through the same validate→atomic-place path the extension uses after `chrome.downloads` completes.

## Image vs prompt (honest)

- **Scene 1** prompt: empty Pakistani national assembly / speaker’s chair on dais — **001.jpg matches** (empty chamber, raised chair, 16:9 graphic-novel style).
- **Scene 2** prompt: assembly viewed from behind an internal **glass partition** — **002.jpg is a related empty chamber** but does not clearly show the glass partition. It was the second parliamentary 2K download available; a live regenerate with the new extension is recommended if exact prompt fidelity for scene 2 is required.

## Full Chrome extension → Flow click loop

**Not executed inside this agent environment.** Cursor’s browser does not load your unpacked Chrome extension or your existing Flow debugger session.

To finish the live UI loop on your machine:

1. Keep `./scripts/run_helper.sh` running
2. Chrome → `chrome://extensions` → Load unpacked → `flow-image-agent/extension`
3. Open your signed-in Flow project (close DevTools on that tab)
4. Extension popup → paste token from `.local/pairing-token`
5. Select `165-pakistan-army`, enable **Regenerate** only if you want new credits for 1–2, else leave off to confirm skip
6. Start

With regenerate off, the queue should report complete immediately (both scenes already saved).
