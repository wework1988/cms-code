# Story Pipeline — User Guide

How to run an episode from start to finish using the Drupal site at **myresearch2**.

You do **not** need to touch code or edit prompt files for a normal episode. Prompts live under **Story Type** (General / Crime / English). Each **Story** node is one video episode.

---

## Before you start

1. **Start MAMP** — Apache + MySQL must be running.
2. **Open the site** in your browser (typical URL):
   ```
   http://localhost:8888/myresearch2/web
   ```
   Adjust the port/path if your MAMP setup differs.
3. **Log in** as an admin user.

---

## What you are doing (simple picture)

```
┌─────────────────────────────────────────────────────────────┐
│  OPTION A — You already wrote the script                    │
│    Create Story → paste script → Run storyboard → prompt.txt│
├─────────────────────────────────────────────────────────────┤
│  OPTION B — Start from YouTube research                     │
│    Create Story → add URLs → Generate script → Run storyboard│
└─────────────────────────────────────────────────────────────┘
```

| Step | What happens | Where you see the result |
|------|----------------|--------------------------|
| **Create story** | Title, type (Crime/General/English), URLs or script | Story node |
| **Generate script** *(optional)* | AI reads YouTube transcripts + master prompt | **Full story** field |
| **Run storyboard** | AI runs Stage A → B → C | **Prompt file**, breakdown, config fields |
| **Download** | Use `prompt.txt` for video production | File field on the story |

---

## Story types — pick one per episode

| Type | Use for |
|------|---------|
| **Crime** | Hindi true crime, mystery, paranormal |
| **General** | Documentary, history, ops stories |
| **English** | English-language episodes |

The type controls **which prompts** are used automatically. You do not copy prompt files manually.

---

## Option A — You already have a script (most common)

Use this when your Hindi/English script is ready (written in Cursor, Google Docs, etc.).

### Step 1 — Create a story

1. Go to **Content → Add content → Story**  
   Or open: `/node/add/story`
2. Fill in:
   - **Title** — e.g. `London Case`
   - **Story type** — e.g. `Crime`
   - **Characters info** — optional notes about people/places
   - **Full story** — paste your **complete narration script**
3. **Status** — leave as `Draft` or set `Story generated` if the script is final.
4. Click **Save**.

### Step 2 — Run the storyboard pipeline

**Easiest (no Terminal):** go to **Content → Run story jobs** and click **Build storyboard**.  
See **`STORY-PIPELINE-RUN-JOBS-README.md`** for start/stop/monitor instructions.

<details>
<summary>Alternative — Terminal / API (technical)</summary>

The storyboard step (Stage A → B → C) can also be triggered via the API or worker CLI:

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
cd /Applications/MAMP/htdocs/myresearch2

# Get your API key (copy the line "API key: ...")
vendor/bin/drush story-pipeline:info
```

Then run storyboard for story ID **1** (replace `1` with your story’s ID from the URL `/node/1`):

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/run-storyboard" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_API_KEY_HERE" \
  -d '{"story_id": "1", "max_step": 4}'
```

**Status while running:** open the story node → **Status** should show `Storyboard running`.

</details>

### Step 3 — Check results

1. Open the story node again.
2. Look for:
   - **Stage A output** — story config
   - **Stage B output** — scene breakdown
   - **Prompt file** — download `prompt.txt` (main deliverable)
   - **Scene file** — optional `scene.txt`
3. **Status** should be `Storyboard done`.

If something failed, **Status** = `Failed` — check fields or ask someone to inspect the worker logs.

---

## Option B — Start from YouTube URLs

Use this when you have **2–3 reference YouTube videos** and want the system to draft a script first.

### Step 1 — Create a story with URLs

1. **Content → Add content → Story**
2. Fill in:
   - **Title**
   - **Story type** (Crime / General / English)
   - **YouTube URLs** — add 2 or 3 links (one per line/field)
   - **Characters info** — optional
3. Leave **Full story** empty for now.
4. **Save** — note the story ID from the URL (`/node/123` → ID is `123`).

### Step 2 — Generate the script (Pipeline 1)

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/generate-story" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_API_KEY_HERE" \
  -d '{"story_id": "123"}'
```

When the worker finishes, the story node will have:
- **Full story** — the narration script
- **Story meta** — title ideas, hook, length notes, etc.

### Step 3 — Review and edit

1. Open the story in Drupal.
2. Read **Full story** — fix any lines directly in the form.
3. **Save**.

### Step 4 — Run storyboard

Same as Option A, Step 2:

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/run-storyboard" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_API_KEY_HERE" \
  -d '{"story_id": "123", "max_step": 4}'
```

### Step 5 — Download prompt.txt

Open the story → download **Prompt file**.

---

## Poll status without opening Drupal

Replace `123` with your story ID:

```bash
curl -s "http://localhost:8888/myresearch2/web/api/story-pipeline/stories/123" \
  -H "X-Story-Pipeline-Key: YOUR_API_KEY_HERE"
```

Response includes `"status"`, `"full_story"`, and `"prompt_file_url"` when ready.

---

## Status values — what they mean

| Status | Meaning |
|--------|---------|
| **Draft** | Story created; script not ready or not generated yet |
| **Story generated** | Full script is saved (Pipeline 1 done or pasted manually) |
| **Storyboard running** | Stage A/B/C is in progress |
| **Storyboard done** | `prompt.txt` and other outputs are ready |
| **Failed** | Something went wrong — re-run or check with admin |

---

## Using Cursor instead of curl

You can ask Cursor to:

1. Create a story via API (`POST /api/story-pipeline/stories`)
2. Trigger generate-story or run-storyboard
3. Poll until `status` is `storyboard_done`
4. Download the prompt file URL from the response

Give Cursor:
- Site base URL: `http://localhost:8888/myresearch2/web`
- API key from: `vendor/bin/drush story-pipeline:info`

Example prompt for Cursor:

> Create a crime story titled "London Case" with these YouTube URLs: …  
> Then run storyboard max_step 4 and wait until prompt_file_url is available.

---

## Admin tasks (occasionally)

### View or edit prompts (General / Crime / English)

**Structure → Taxonomy → Story type → Edit term**

Each term has:
- Master prompt (for script generation from YouTube)
- Stage A / B / C config
- Default characters
- Pipeline settings (JSON — model, batch size)

You rarely need to change these unless tuning the pipeline.

### Re-import prompts from the automation repo

If prompt files were updated in the Git repo:

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
cd /Applications/MAMP/htdocs/myresearch2
vendor/bin/drush story-pipeline:import-prompts
```

### API key and settings

**Configuration → Content authoring → Story Pipeline settings**  
Or: `/admin/config/content/story-pipeline`

**Two kinds of keys:**

| Key | Purpose |
|-----|---------|
| **Drupal API key** | Worker/Cursor uses this in header `X-Story-Pipeline-Key` to talk to Drupal |
| **Per story type keys** | DeepSeek, Anthropic, ElevenLabs — used when the worker runs pipelines |

**Per story type (General / Crime / English):**

| Field | Used for |
|-------|----------|
| **DeepSeek API key** | Storyboard pipeline (Stage A → B → C) |
| **Anthropic API key** | Script generation from YouTube (optional if DeepSeek used instead) |
| **ElevenLabs API key** | Text-to-speech (future audio step) |

The worker gets the correct keys automatically from  
`GET /api/story-pipeline/stories/{id}/bundle` → `"api_keys"` block (matched to the story’s type).

Check which keys are set (masked):

```bash
vendor/bin/drush story-pipeline:info
```

---

## Quick reference — important URLs

| What | URL |
|------|-----|
| Add story | `/node/add/story` |
| All stories | `/admin/content` (filter type: Story) |
| Story types / prompts | `/admin/structure/taxonomy/manage/story_type/overview` |
| Pipeline settings | `/admin/config/content/story-pipeline` |

---

## API endpoints (for curl / Cursor)

All requests need header: `X-Story-Pipeline-Key: <your key>`

| Action | Method | Path |
|--------|--------|------|
| Create story | POST | `/api/story-pipeline/stories` |
| Get story + status | GET | `/api/story-pipeline/stories/{id}` |
| Get prompts bundle (worker) | GET | `/api/story-pipeline/stories/{id}/bundle` |
| Generate script from YouTube | POST | `/api/story-pipeline/generate-story` |
| Run storyboard A→B→C | POST | `/api/story-pipeline/run-storyboard` |
| Worker saves outputs | POST | `/api/story-pipeline/stories/{id}/update` |

### Create story (JSON body)

```json
{
  "title": "London Case",
  "story_type": "crime",
  "youtube_urls": [
    "https://www.youtube.com/watch?v=VIDEO_ID_1",
    "https://www.youtube.com/watch?v=VIDEO_ID_2"
  ],
  "characters_info": "Optional notes about characters..."
}
```

Or with script already written:

```json
{
  "title": "London Case",
  "story_type": "crime",
  "full_story": "Paste full Hindi script here...",
  "characters_info": "..."
}
```

---

## Troubleshooting

### “Cannot connect” or site does not load
- Check MAMP — Apache and MySQL are green.
- Confirm URL matches your MAMP host/port.

### API returns 403 Forbidden
- Wrong or missing `X-Story-Pipeline-Key`.
- Run `vendor/bin/drush story-pipeline:info` and copy the key again.

### Storyboard stuck on “Storyboard running”
- The **Python worker** must be running to process queued jobs (separate from Drupal).
- If no worker is set up yet, outputs will not appear until something calls the API bundle and posts results back.

### Drush commands fail
Add MAMP MySQL to your path first:

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
```

### Full story empty after generate-story
- Check YouTube URLs are valid and public.
- Confirm worker is running and connected to the API.

---

## Typical day — London case example

1. Write raw notes / pick 2 YouTube references.
2. **Add story** → type Crime → paste URLs → Save.
3. **Generate script** (API) → review **Full story** in Drupal → tweak → Save.
4. **Run storyboard** (API) → wait for **Storyboard done**.
5. Download **Prompt file** → hand off to image/video production.

---

## More technical docs

- Module developer notes: `web/modules/custom/story_pipeline/README.md`
- Design doc (automation repo): `docs/drupal-story-pipeline/SIMPLE-FLOW.md`

---

## One-line cheat sheet

```bash
# API key
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
cd /Applications/MAMP/htdocs/myresearch2 && vendor/bin/drush story-pipeline:info

# Run storyboard for story ID 5
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/run-storyboard" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_KEY" \
  -d '{"story_id": "5", "max_step": 4}'
```
