# Story Pipeline — Drupal module

Implements the **Simple Flow** design: Story Type taxonomy holds all prompts; Story content type holds episode data; REST API for worker/Cursor.

## Admin

- **Story Type terms:** `/admin/structure/taxonomy/manage/story_type/overview`  
  Edit General / Crime / English — paste or review prompts in each field.

- **Stories:** `/node/add/story`

- **Settings & API keys:** `/admin/config/content/story-pipeline`  
  - Drupal API key (worker auth header)  
  - **Shared keys:** DeepSeek, Anthropic, ElevenLabs (all story types)  
  - Worker folder path

- **Run / stop jobs (staff UI):** `/admin/content/story-pipeline/run`  
  Non-technical guide: `../../STORY-PIPELINE-RUN-JOBS-README.md`

- **Character library:** `/admin/content/story-pipeline/characters`  
  Shared locked character looks. Import from repo `character.txt` or add manually.

- **Story characters (per episode):** edit any Story node → **Characters** tab, or `/node/{id}/characters`  
  Paste the full planned file into **Story plan (with characters)** (TOP 10 CHARACTERS + FULL SCRIPT).  
  Leave **Full story** unchanged — that field is what the pipeline uses.  
  Then extract → save new looks to library → **Apply all to story pipeline**.

Keys are returned in the worker bundle under `api_keys` — never in public story GET.

## Drush

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
cd /Applications/MAMP/htdocs/myresearch2

vendor/bin/drush story-pipeline:info
vendor/bin/drush story-pipeline:import-prompts
vendor/bin/drush story-pipeline:import-keys
vendor/bin/drush story-pipeline:import-characters
vendor/bin/drush story-pipeline:import-characters --overwrite
vendor/bin/drush cr
```

## API

Send header on every request:

```
X-Story-Pipeline-Key: <key from drush story-pipeline:info>
```

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/story-pipeline/stories` | Create story |
| GET | `/api/story-pipeline/stories/{id}` | Get story + outputs |
| GET | `/api/story-pipeline/stories/{id}/bundle` | Worker bundle (prompts + settings) |
| POST | `/api/story-pipeline/generate-story` | Queue Pipeline 1 |
| POST | `/api/story-pipeline/run-storyboard` | Queue Pipeline 2 |
| POST | `/api/story-pipeline/stories/{id}/update` | Worker writes outputs |

### Create story

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/stories" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_KEY" \
  -d '{
    "title": "London Case",
    "story_type": "crime",
    "youtube_urls": ["https://www.youtube.com/watch?v=EXAMPLE"],
    "characters_info": "Chohan family..."
  }'
```

### Run storyboard

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/run-storyboard" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_KEY" \
  -d '{"story_id": "1", "max_step": 4}'
```

### Worker update (after pipeline completes)

```bash
curl -X POST "http://localhost:8888/myresearch2/web/api/story-pipeline/stories/1/update" \
  -H "Content-Type: application/json" \
  -H "X-Story-Pipeline-Key: YOUR_KEY" \
  -d '{
    "status": "storyboard_done",
    "stage_a_output": "...",
    "stage_b_output": "...",
    "prompt_file_content": "..."
  }'
```

## Database note (MAMP)

Drush needs MySQL client in PATH:

```bash
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
```

Database host in `settings.php` should be `127.0.0.1` (not `localhost`) for MAMP port 8889.

## Next step

Background worker: `/Applications/MAMP/htdocs/story-pipeline-worker` — started from **Run story jobs** UI or `./run.sh`.
