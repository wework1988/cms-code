---
name: sync-cms-story
description: >-
  Validate a cms-generate-stories story folder (images vs image-prompts count),
  optionally copy into playright-automation, or prefer CMS-direct mode
  (npm run run:cms) that reads/writes the CMS folder without copying.
  Use when the user points at a CMS story folder like
  cms-generate-stories/general/168-karwa-chauth-story, or asks to sync/copy
  a story into playright-automation / playwright automation.
disable-model-invocation: false
---

# Sync CMS Story → playright-automation

## Prefer CMS-direct (no copy)

If the user wants to **run Digen** against a CMS folder, use CMS mode instead of copying:

```bash
cd /Users/alokkumarverma/project/cms-code/playright-automation
WAIT_READY=1 npm start
# or: WAIT_READY=1 npm run run:cms -- general/168-karwa-chauth-story
```

- Images ← `<story>/images/`
- Prompt ← `<story>/prompts/prompt.txt`
- Videos → `<story>/videos/`

Playright lives inside `cms-code/playright-automation/` by default (sibling of `cms-generate-stories/`).

See [CMS-MODE.md](../../../CMS-MODE.md).

## When to use this skill (copy / validate)

User gives a CMS story folder path and wants validation and/or a local copy under playright `images/` + `prompt/`.

Example:

`/Users/alokkumarverma/project/cms-code/cms-generate-stories/general/168-karwa-chauth-story`

## What copy mode does

1. **Validate** image count in `<story>/images/` against scene count in `<story>/image-prompts/image-prompts-only.txt`
2. **Copy images** → `~/project/playright-automation/images/<story-folder-name>/`
3. **Copy prompt** → `~/project/playright-automation/prompt/<story-folder-name>.txt`
   - Source: `<story>/prompts/prompt.txt` (preferred; Digen format)
   - Fallback: `<story>/image-prompts/image-prompts-only.txt`

Story folder name is used as-is (e.g. `168-karwa-chauth-story`).

## Required input

- Absolute path to one CMS story directory that contains at least:
  - `images/`
  - `image-prompts/image-prompts-only.txt`
  - `prompts/prompt.txt` (preferred)

## Workflow

Run the helper (do not invent ad-hoc copy commands):

```bash
python3 /Users/alokkumarverma/project/cms-code/playright-automation/tools/sync_cms_story.py \
  "/ABS/PATH/TO/cms-generate-stories/<type>/<story-folder>"
```

Dry-run first if useful:

```bash
python3 /Users/alokkumarverma/project/cms-code/playright-automation/tools/sync_cms_story.py \
  "/ABS/PATH/TO/story-folder" \
  --dry-run
```

### Count mismatch

If validation fails (example: 116 images vs 120 prompt scenes):

1. Report clearly: image count, prompt-scene count, missing image numbers
2. **Do not copy** unless the user explicitly says to continue
3. If they confirm, re-run with `--force`:

```bash
python3 /Users/alokkumarverma/project/cms-code/playright-automation/tools/sync_cms_story.py \
  "/ABS/PATH/TO/story-folder" \
  --force
```

## Destinations (fixed)

| Artifact | Destination |
|----------|-------------|
| Images | `/Users/alokkumarverma/project/cms-code/playright-automation/images/<story-name>/` |
| Prompt file | `/Users/alokkumarverma/project/cms-code/playright-automation/prompt/<story-name>.txt` |

Playright root override (rare):

```bash
python3 .../sync_cms_story.py "/path/to/story" --playright-root "/other/playright-automation"
```

## After success

Report:

- validation result (OK / forced mismatch details)
- how many images copied
- destination image folder path
- destination prompt `.txt` path

Do not start a Digen run unless the user asks.
