# CMS Story Pipeline — Full Process Guide

End-to-end guide: Drupal CMS → script/storyboard → image prompts → Google Flow images → Digen videos. Covers agents, commands, and where files land.

---

## 1. Big picture

```text
Drupal CMS (PHP)  --nohup ./run.sh-->  story-pipeline-worker (Python)
                                            |
                     +----------------------+----------------------+
                     |                      |                      |
              DeepSeek A/B/C          flow-image-agent        playright
              (prompts/scenes)        (Chrome + Flow)         (Firefox + Digen)
                     |                      |                      |
                     v                      v                      v
              prompts/, scenes/,       images/001.jpg…       videos/scene_N.mp4
              image-prompts/
```

**One story folder** (example node `#170`):

```text
cms-generate-stories/general/170-test-flow-images-story-2/
  meta/           # node id, title, type
  script/         # FULL_STORY.txt, story_meta.txt
  prompts/        # prompt.txt (Digen motion format)
  scenes/         # scene.txt
  image-prompts/  # image-prompts-only.txt (|| Scene N.)
  images/         # 001.jpg … + generation-manifest.json
  videos/         # scene_1.mp4 …
  audio/          # optional ElevenLabs MP3s
```

Asset root: Drupal **Config → Story Pipeline → Story asset folder path**  
(typically `…/cms-code/cms-generate-stories`).

---

## 2. Agents and components

| Component | Role | Tech |
|-----------|------|------|
| Drupal `story_pipeline` | Run jobs UI, progress bar, Outputs downloads | PHP |
| `story-pipeline-worker` | Orchestrates pipelines, syncs asset folders | Python |
| DeepSeek `deepseek_pipeline.py` | Stages A/B/C: config, scenes, image + Digen prompts | Python + DeepSeek |
| `flow-image-agent` | Google Flow: generate → 2K upscale → save stills | Node Playwright CDP + Python helper + Chrome |
| `playright-automation` | Digen.ai: image + motion → MP4 | Node Playwright + Firefox |

### Cursor skills (manual chat shortcuts)

| Skill | Path | Use |
|-------|------|-----|
| `flow-story-images` | `.cursor/skills/flow-story-images/SKILL.md` | Generate Flow images for a story folder |
| `sync-cms-story` | `.cursor/skills/sync-cms-story/SKILL.md` | Validate images; prefer `npm run run:cms` for videos |

These do not replace Drupal jobs; they help when you ask the Cursor agent in chat.

---

## 3. How a Drupal job starts

1. Open **Content → Run story jobs**.
2. Click e.g. **Build storyboard (+ Flow images + Digen videos)**.
3. PHP `WorkerLauncher` runs:

```bash
cd …/story-pipeline-worker && \
  export STORY_ASSET_ROOT='…/cms-generate-stories' && \
  nohup ./run.sh storyboard 170 >> …/story-pipeline/logs/story-170-storyboard-….log 2>&1 &
```

4. Worker sets status `storyboard_running`.
5. Progress bar polls the log (`JobProgressParser`) for `PROGRESS […] N%` and `[flow-images]` / `[digen-videos]` lines.

### Job map

| UI button | Command | Runs |
|-----------|---------|------|
| Write story from YouTube | `./run.sh generate <id>` | YouTube → script |
| Prepare bullets | `./run.sh generate_pointers <id>` | Transcript → bullets |
| Build storyboard (+ Flow + Digen) | `./run.sh storyboard <id>` | A–C → Flow → Digen |
| + narration audio | `./run.sh storyboard <id> --elevenlabs` | Above + MP3s |
| Audio only | `./run.sh elevenlabs <id>` | MP3s |
| Full pipeline | `./run.sh full <id>` | YouTube → … → audio |

Skip gates (worker `.env`): `FLOW_IMAGES=0`, `DIGEN_VIDEOS=0`.

---

## 4. Stage-by-stage

### 0 — Create Story in CMS

- **Content → Add content → Story**
- Set type (General / Crime / English)
- Paste **Full story** *or* add YouTube URLs first
- Folder created: `{STORY_ASSET_ROOT}/{type}/{node-id}-{slug}/`

### 1 — Script (optional)

```bash
cd story-pipeline-worker && ./run.sh generate 170
```

Writes `script/FULL_STORY.txt`, posts back to Drupal.

### 2 — Storyboard (DeepSeek A → B → C)

```bash
./run.sh storyboard 170
# text only, no Flow/Digen:
./run.sh storyboard 170 --max-step 3
```

Orchestrator: `run_storyboard.py` → temp workspace →  
`{AUTOMATION_REPO}/crime-section/helper/deepseek_pipeline.py`

| Stage | Output |
|-------|--------|
| **A** | Story/config notes |
| **B** | Scene breakdown → `scenes/scene.txt` |
| **C** | Image prompts + DIGEN MOTION → `image-prompts/image-prompts-only.txt`, `prompts/prompt.txt` |

Log may show `PROGRESS 100% · Complete · …/prompt.txt` — that is **storyboard text only**. Flow and Digen still run after. The UI progress parser keeps the bar in the ~72–96% band during those steps.

### 3 — Flow images

Hook in `run_storyboard.py`:

```python
run_flow_images_for_story(asset_dest)  # soft-fail
```

→ `run_flow_images.py` →:

```bash
bash flow-image-agent/scripts/run_images.sh {story-folder} --all
```

Manual:

```bash
cd flow-image-agent
./scripts/run_images.sh 170-test-flow-images-story-2 --all
./scripts/run_images.sh 170-test-flow-images-story-2 --first-two
```

**Agent internals:**

```text
run_images.sh → run-images.mjs
  start helper :8765
  POST /jobs → images/generation-manifest.json
  Chrome CDP :9222 (Chrome-FlowAgent profile)
  per scene: Nano Banana 2.1 · 16:9 · x1 → generate → 2K Upscaled → images/NNN.jpg
  resume skips completed scenes in the manifest
```

Needs: Chrome signed into Google Flow; Homebrew `node` on PATH (worker auto-adds it).

### 4 — Digen videos

Hook after Flow:

```python
run_digen_videos_for_story(asset_dest)  # soft-fail
```

Gates: `prompts/prompt.txt` exists; image count ≥ scene count.

```bash
cd playright-automation
WAIT_READY=1 \
FIREFOX_PROFILE_PATH="$PWD/profiles/firefox-automation" \
CMS_STORIES_ROOT="…/cms-generate-stories" \
node run-cms-story.js --missing general/170-test-flow-images-story-2
```

Manual: `WAIT_READY=1 npm run run:cms:missing -- general/170-…`

**Agent internals:**

```text
run-cms-story.js → run-digen-missing.js → run-digen.js
  Firefox profile: profiles/firefox-automation
  open digen.ai/create
  batch (BATCH_SIZE=2): upload 001.jpg + motion prompt → download scene_N.mp4
```

Needs: Digen login in that Firefox profile; `npx playwright install firefox`.

### 5 — Audio (optional)

```bash
./run.sh storyboard 170 --elevenlabs
./run.sh elevenlabs 170
```

Writes `audio/*.mp3`.

---

## 5. Exact Build-storyboard order

Inside `run_storyboard.py` (`max_step >= 4`):

1. GET Drupal bundle  
2. Temp workspace + seed script  
3. DeepSeek A → B → C  
4. Sync to `cms-generate-stories/…`  
5. Optional ElevenLabs  
6. Flow images → `images/` (soft-fail)  
7. Digen videos → `videos/` (soft-fail)  
8. POST `storyboard_done` + meta  
9. Cleanup workspace  

Progress bands: 0–70 storyboard · ~72–86 Flow · ~88–96 Digen · 100 done.

---

## 6. Soft-fail and resume

| Step | On failure | Resume |
|------|------------|--------|
| DeepSeek | Job usually failed | Re-run storyboard (`--resume` for Stage C gaps) |
| Flow | Soft-fail; text still done | `./scripts/run_images.sh … --all` |
| Digen | Soft-fail; images kept | `npm run run:cms:missing -- type/slug` |
| Audio | Per flags | `./run.sh elevenlabs <id>` |

---

## 7. Commands cheat sheet

```bash
# Worker
cd story-pipeline-worker
./run.sh storyboard 170
./run.sh full 170
.venv/bin/python -u run_flow_images.py ../cms-generate-stories/general/170-…
.venv/bin/python -u run_digen_videos.py ../cms-generate-stories/general/170-…

# Flow
cd flow-image-agent
./scripts/run_images.sh 170-test-flow-images-story-2 --all

# Digen
cd playright-automation
WAIT_READY=1 npm run run:cms:missing -- general/170-test-flow-images-story-2
```

---

## 8. Prerequisites

- MAMP / Drupal up; `STORY_ASSET_ROOT` set  
- DeepSeek keys in Drupal  
- Chrome signed into Flow (Chrome-FlowAgent / port 9222)  
- Node (`/opt/homebrew/bin/node`)  
- Firefox profile `playright-automation/profiles/firefox-automation` logged into Digen  
- Playwright browsers installed  
- Mac stays awake for long jobs  

---

## 9. Related docs

- `STORY-PIPELINE-RUN-JOBS-README.md` — Drupal UI (non-technical)  
- `STORY-PIPELINE-USER-GUIDE.md` — broader CMS guide  
- `flow-image-agent/README.md` — Flow agent  
- `playright-automation/CMS-MODE.md` — CMS-direct Digen  
- `playright-automation/MIGRATION.md` — Firefox profile setup  

---

## 10. Mental model

1. **Drupal** = control panel + downloads  
2. **Worker** = conductor  
3. **DeepSeek** = text storyboard (scenes + prompts)  
4. **flow-image-agent** = stills via Google Flow  
5. **playright-automation** = MP4s via Digen  
6. One episode = one folder under `cms-generate-stories/` (source of truth)
