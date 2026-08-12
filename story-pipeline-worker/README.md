# Story Pipeline Worker

Standalone Python project that connects to **Drupal (myresearch2)** and runs pipelines.  
**Does not modify** `research-story-17thmay-automation` — only calls `deepseek_pipeline.py` read-only.

```
/Applications/MAMP/htdocs/story-pipeline-worker/   ← this folder
/Applications/MAMP/htdocs/myresearch2/web/         ← Drupal CMS + API
/Users/averma/project/research-story-17thmay-automation/  ← engine (read-only)
```

---

## Quick start — your story at node/1

### 1. Setup (once)

```bash
cd /Applications/MAMP/htdocs/story-pipeline-worker
cp .env.example .env
```

Edit `.env`:

```env
DRUPAL_BASE_URL=http://localhost:8888/myresearch2/web
DRUPAL_API_KEY=3df3a42b2cd30a84c5953445308443a9
AUTOMATION_REPO=/Users/averma/project/research-story-17thmay-automation
```

Get API key anytime:

```bash
cd /Applications/MAMP/htdocs/myresearch2
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
vendor/bin/drush story-pipeline:info
```

### 2. Set LLM keys in Drupal (required)

Open: **http://localhost:8888/myresearch2/web/admin/config/content/story-pipeline**

For **Crime** (your node/1 is crime type), paste:
- **DeepSeek API key** — required for storyboard
- **Anthropic API key** — optional, for generate-story
- **ElevenLabs API key** — optional, for future TTS

### 3. Run storyboard for node 1

You already saved the script at `http://localhost:8888/myresearch2/web/node/1`:

```bash
cd /Applications/MAMP/htdocs/story-pipeline-worker
chmod +x run.sh
./run.sh storyboard 1
```

This will:
1. `GET /api/story-pipeline/stories/1/bundle` — prompts + keys from Drupal
2. Build temp workspace under `.workspace/`
3. Run `deepseek_pipeline.py` (Stages A→B→C)
4. `POST /api/story-pipeline/stories/1/update` — save config, breakdown, `prompt.txt`

Results appear on the story node in Drupal (refresh node/1).

### Cheaper test (Stage A only)

```bash
./run.sh storyboard 1 --max-step 2
```

---

## Commands

| Command | What it does |
|---------|----------------|
| `./run.sh storyboard 1` | Full storyboard → prompt.txt on Drupal |
| `./run.sh storyboard 1 --max-step 3` | Config + breakdown only |
| `./run.sh generate 1` | YouTube URLs → full_story (needs URLs on story) |
| `./run.sh generate 1 --source-mode bullets` | Extract 20 bullets + flow per source, then generate from ledger only (default) |
| `./run.sh generate 1 --source-mode transcript` | Legacy: pass raw combined transcripts into master prompt |
| `./run.sh worker --story-id 1` | Auto: storyboard if script exists, else generate |
| `./run.sh info 1` | Print story JSON from Drupal |

Or with venv directly:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
source .env  # or use dotenv
.venv/bin/python run_storyboard.py 1
```

---

## Flow diagram

```
Drupal node/1 (Story)
       │
       ▼
drupal_client.py  ──GET bundle──►  prompts + api_keys + full_story
       │
       ▼
workspace.py      ──writes──►  .workspace/story-1-*/
                               bifuracted-template/*.md
                               stories/<slug>/FULL_STORY.txt
       │
       ▼
deepseek_pipeline.py  (read-only from AUTOMATION_REPO)
       │
       ▼
drupal_client.py  ──POST update──►  stage outputs + prompt.txt on node/1
```

---

## Files

| File | Role |
|------|------|
| `drupal_client.py` | All Drupal REST calls |
| `workspace.py` | Bundle → temp `--crime-root` layout |
| `run_storyboard.py` | Stage A→B→C for one story ID |
| `run_generate_story.py` | YouTube → script via master prompt |
| `worker.py` | CLI wrapper with auto-detect |
| `run.sh` | One-command launcher |
| `.env` | Drupal URL, API key, automation repo path |

---

## Troubleshooting

### `403 Forbidden` from Drupal
Wrong `DRUPAL_API_KEY` in `.env`. Run `drush story-pipeline:info`.

### `no DeepSeek API key`

The worker loads keys in this order:
1. Drupal → `/admin/config/content/story-pipeline` → **Crime** → DeepSeek key
2. `story-pipeline-worker/.env` → `DEEPSEEK_API_KEY=...`
3. **Automatic:** `AUTOMATION_REPO/.env` (your automation repo — read-only, not modified)

If you already have `DEEPSEEK_API_KEY` in the automation repo `.env`, just re-run — no extra setup needed.

### Parallel DeepSeek with 2 keys

To let concurrent jobs use separate keys, add this to worker `.env`:

```env
DEEPSEEK_API_KEYS=sk-key-1,sk-key-2
```

Notes:
- Worker auto-picks a less-busy key for each new job and releases it when done.
- If Drupal DeepSeek key is set, it is still eligible as a candidate key.
- For pool-only control, leave Drupal DeepSeek key empty and manage keys only in `.env`.

### `prompt.txt was not created`
Run with `--keep-workspace` and check logs:
```bash
.venv/bin/python run_storyboard.py 1 --keep-workspace
```

### Pipeline dependencies
Storyboard needs Python packages from automation repo:
```bash
pip install -r /Users/averma/project/research-story-17thmay-automation/crime-section/requirements-deepseek.txt
```
(Install in this worker's `.venv` — does not change the automation repo.)

### HTML in full_story
Drupal may store CKEditor HTML. The worker strips tags before writing `FULL_STORY.txt`.

---

## What this project does NOT do

- Does not edit files under `research-story-17thmay-automation`
- Does not edit Drupal PHP modules (those live in `myresearch2`)
- Does not store API keys in git (`.env` is gitignored)

---

## Your story node 1

View: http://localhost:8888/myresearch2/web/node/1

After `./run.sh storyboard 1` succeeds:
- **Stage A output** / **Stage B output** filled on the node
- **Prompt file** downloadable from the story form
- **Status** = `Storyboard done`
