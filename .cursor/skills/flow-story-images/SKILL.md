---
name: flow-story-images
description: >-
  Generate Google Flow images for a CMS story by running flow-image-agent
  when the user points at a story folder or image-prompts-only.txt (or asks
  to generate/create Flow images / scene images for a story). Defaults to
  the first two scenes unless the user specifies a range or all scenes.
disable-model-invocation: false
---

# Flow story images (one-command agent)

When the user gives a CMS story path or `image-prompts-only.txt` (or asks to
generate Flow images for a story), **immediately run the generator**. Do not
stop at a plan. Do not ask them to paste tokens or load an extension.

## Resolve the story key

Accept any of:

- Story folder: `.../general/164-how-captain-saved-video-done`
- Prompt file: `.../164-how-captain-saved-video-done/image-prompts/image-prompts-only.txt`
- Short key: `164-how-captain-saved-video-done`
- Category key: `general/164-how-captain-saved-video-done`

If given a file path, use its story folder name (parent of `image-prompts/`).
If given a folder that contains `image-prompts/image-prompts-only.txt`, use that folder’s name.

Confirm the prompt file exists before starting. If missing, stop with a clear error.

## Defaults

| User says | Flags |
|-----------|--------|
| (nothing about range) / “first 2” / “test” | `--first-two` |
| “scenes 1–5” / “from 3 to 10” | `--from N --to M` |
| “all scenes” / “entire story” | omit `--first-two`; use `--from 1 --to <last>` only if needed — prefer letting the helper use full prompt range via `--from 1 --to 9999` only when they explicitly want all; otherwise ask once for confirmation before burning many credits |
| “regenerate” / “redo” | add `--regenerate` |

**Default for a bare file/folder path: `--first-two`.**

## Command to run

```bash
cd /Users/alokkumarverma/project/cms-code/flow-image-agent
./scripts/run_images.sh "<story-key>" --first-two
```

Examples:

```bash
./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
./scripts/run_images.sh 165-pakistan-army --from 1 --to 2
FLOW_PROJECT_URL="$URL" ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
```

The script starts the local helper if needed, opens Chrome (persistent profile),
drives Google Flow (Nano Banana 2.1 · 16:9 · 2K Upscaled), and saves into:

`<story>/images/001.jpg`, `002.jpg`, …

## How to run it

1. Use the Shell tool with a long enough block time (generation can take several minutes per scene). Prefer `block_until_ms` of at least 600000 (10 minutes) for two scenes; if it backgrounds, poll the terminal output.
2. Request permissions that allow opening Chrome / network (`all` if sandbox blocks the browser).
3. Do **not** invent alternate Playwright or extension steps unless this command fails.

## Chrome login

The runner attaches to your **normal Chrome profile** via remote debugging (`scripts/start_chrome_debug.sh`). It may briefly quit and reopen Chrome so Google/Flow stay signed in. Warn the user only if that restart is about to happen and they might lose unsaved tab work — then continue.

If Flow still shows signed-out:

1. Manually open Chrome, sign into Google/Flow once
2. Re-run the same `./scripts/run_images.sh …` command

Optional env:

- `FLOW_PROJECT_URL` — skip project discovery
- `CDP_URL` — default `http://127.0.0.1:9222`
- `CHROME_USER_DATA_DIR` — override Chrome profile path

Do not collect Google passwords.

## After success

Report briefly:

- story key
- scenes completed
- output paths under `<story>/images/`
- any `needs_review` / failed scenes from the terminal or `images/generation-manifest.json`

## Do not

- Run all 200+ scenes unless the user explicitly asks
- Publish, delete story assets, or buy credits
- Fall back to the manual Chrome-extension popup workflow unless the one-command runner fails
