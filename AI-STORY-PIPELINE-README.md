# AI Story Pipeline README

This document is for AI agents (and developers) who need to understand how this codebase generates stories and image prompts through Drupal CMS + Python worker.

Use this as the first file to read before touching the pipeline.

---

## 1) What this system is

The system has two parts:

- Drupal module: `web/modules/custom/story_pipeline`
- Python worker: `story-pipeline-worker/`

The CMS (Drupal) is the control plane:

- stores stories
- stores per-type prompt templates (taxonomy)
- exposes API endpoints
- stores outputs/files/status

The worker is the execution plane:

- reads story + prompt bundle from Drupal
- runs generation logic (YouTube -> script, or script -> storyboard/image prompts)
- writes outputs back to Drupal

---

## 2) End-to-end flow (high level)

There are two main pipelines.

### Pipeline A: Generate Story (from YouTube inputs)

1. Story node has YouTube URLs.
2. CMS queue action writes `QUEUE:generate-story` into story meta.
3. Worker fetches bundle (`pipeline=generate`).
4. Worker gets transcripts/research, runs master prompt, builds full script.
5. Worker posts update to Drupal:
   - `full_story`
   - `story_meta`
   - `status=story_generated` (or `failed`)

### Pipeline B: Storyboard + Image Prompts (Stage A/B/C)

1. Story node has `full_story` text.
2. CMS queue action sets:
   - `field_status=storyboard_running`
   - `field_story_meta={"QUEUE":"run-storyboard","max_step":N}`
3. Worker fetches bundle (`pipeline=storyboard`) with:
   - story data
   - taxonomy prompts (stage A/B/C)
   - settings JSON
   - API keys
4. Worker builds temporary workspace and runs DeepSeek pipeline stages:
   - Stage A: story config
   - Stage B: scene breakdown
   - Stage C: image/motion prompt generation
5. Worker posts update to Drupal with outputs/files and marks done.

---

## 3) CMS data model (critical)

## 3.1 Taxonomy: Story Type (prompt/config source of truth in CMS)

Vocabulary: `story_type`

Default terms:

- General -> machine key `general`
- Crime -> `crime`
- English -> `english`
- God Story -> `god_story`

Prompt/config fields on each taxonomy term:

- `field_master_prompt` -> story-writing prompt (used in generate-story pipeline)
- `field_stage_a` -> Stage A template
- `field_stage_b` -> Stage B template
- `field_stage_c` -> Stage C template
- `field_default_characters` -> default character text
- `field_pipeline_settings` -> JSON settings (model, token budgets, batch sizes)
- `field_voice_id` -> ElevenLabs voice ID

Interpretation:

- Taxonomy term fully defines "how this story type should be generated."
- Story nodes only choose a type; worker bundle inherits prompts/settings from that type.

## 3.2 Story content type (per-episode runtime record)

Content type: `story`

Important fields:

- `field_story_type` -> taxonomy reference (General/Crime/English/God Story)
- `field_youtube_urls` -> source URLs for generate-story
- `field_full_story` -> Hindi script (primary storyboard input)
- `field_full_story_english` -> optional English script
- `field_characters_info` -> character/context notes
- `field_story_meta` -> queue metadata + diagnostics
- `field_status` -> workflow status
- `field_stage_a_output` -> saved Stage A output
- `field_stage_b_output` -> saved Stage B output
- `field_prompt_file` -> final `prompt.txt`
- `field_scene_file` -> final `scene.txt`
- `field_image_prompts_file` -> `image-prompts-only.txt`
- `field_eleven_labs_files` -> generated Hindi MP3 files
- `field_eleven_labs_files_english` -> generated English MP3 files

Status enum (used by worker/CMS):

- `draft`
- `story_generated`
- `storyboard_running`
- `storyboard_done`
- `live`
- `stopped`
- `failed`

---

## 4) API contract between CMS and worker

Header required for all requests:

- `X-Story-Pipeline-Key: <Drupal API key>`

Main endpoints:

- `POST /api/story-pipeline/stories` -> create story node
- `GET /api/story-pipeline/stories/{id}` -> read public story data/status/urls
- `GET /api/story-pipeline/stories/{id}/bundle?pipeline=generate|storyboard` -> worker input bundle
- `POST /api/story-pipeline/generate-story` -> queue generate pipeline
- `POST /api/story-pipeline/run-storyboard` -> queue storyboard pipeline
- `POST /api/story-pipeline/stories/{id}/update` -> worker callback writing outputs

Access model:

- API allowed if user has permission OR valid API header key matches config.

Important security behavior:

- `api_keys` are included in `bundle` payload for worker use.
- `api_keys` are not returned by normal story GET endpoint.

---

## 5) What "bundle" contains (worker input payload)

`buildBundle()` in Drupal manager returns:

- `story`:
  - id/title/story_type/full_story/full_story_english/characters_info/youtube_urls/story_meta/bilingual
- `prompts`:
  - master_prompt/stage_a/stage_b/stage_c/characters
- `settings`:
  - model + batch/token settings (taxonomy JSON merged with defaults, plus voice IDs)
- `api_keys`:
  - deepseek/anthropic/elevenlabs keys (from Drupal config, with fallback behavior)
- `pipeline`:
  - `generate` or `storyboard`
- `story_asset_path`:
  - persistent disk root for artifacts
- `prior_artifacts`:
  - previous stage outputs when present

---

## 6) Queue semantics (how jobs are "requested")

This system does not use a DB queue broker; queue intent is stored in story meta/status.

Generate queue marker:

- `field_story_meta = "QUEUE:generate-story"`

Storyboard queue marker:

- `field_story_meta = {"QUEUE":"run-storyboard","max_step":4}`
- `field_status = "storyboard_running"`

Worker auto-detection (`worker.py`) reads `story_meta` and chooses pipeline.

---

## 7) Worker internals (low-level)

Main worker files:

- `worker.py` -> entrypoint / auto pipeline detection
- `drupal_client.py` -> REST client wrapper
- `run_generate_story.py` -> YouTube/research -> script generation
- `run_storyboard.py` -> Stage A/B/C orchestration
- `workspace.py` -> creates temporary `--crime-root` structure for pipeline
- `asset_store.py` -> persistent artifact sync to disk layout
- `secrets.py` -> key resolution + DeepSeek key pool leasing

## 7.1 Storyboard path (run_storyboard.py)

1. GET story + bundle.
2. Resolve repo + keys + asset root.
3. Build temp workspace under `story-pipeline-worker/.workspace/story-<id>-*`.
4. Write prompts and story text files expected by `deepseek_pipeline.py`.
5. Run subprocess into automation engine (`crime-section/helper/deepseek_pipeline.py`).
6. Collect outputs:
   - `output_config_<slug>.md`
   - `output_story_breakdown_<slug>.md`
   - `prompt.txt`
   - `scene.txt`
   - `image-prompts-only.txt` (derived if missing)
7. Sync artifacts to disk root (if enabled).
8. POST update to Drupal.
9. On exception, POST `status=failed`.

Robustness behavior worth knowing:

- raises token ceilings for Stage B/C if too low
- sets sequential defaults for Stage B/C parallelism unless env overrides
- supports `--resume` and `--fill-prompt-gaps`
- runs periodic incremental asset sync while pipeline is executing

## 7.2 Generate path (run_generate_story.py)

1. GET generate bundle.
2. Resolve transcripts/research source:
   - uploaded transcripts
   - channel-first research mode
   - direct YouTube transcript fetch fallback
3. Build prompt from taxonomy master prompt + source text.
4. Call LLM (DeepSeek path currently implemented; Anthropic placeholder path not active).
5. Parse output to extract FULL SCRIPT + meta sections.
6. Apply quality guards (recovery pass, length checks, continuation).
7. POST story updates (`full_story`, `story_meta`, `status`).

---

## 8) Where prompts really come from

At runtime, prompt text is resolved with precedence:

1. automation repo file in `.../bifuracted-template/` (if present/valid)
2. Drupal taxonomy field value

So CMS stores prompts, but worker may prefer automation repo templates when available.

`drush story-pipeline:import-prompts` can re-import repo templates into taxonomy terms.

---

## 9) API key resolution and fallback

Drupal config stores:

- `api_key` -> Drupal API auth key (for `X-Story-Pipeline-Key`)
- `pipeline_api_keys`:
  - `deepseek_api_key`
  - `anthropic_api_key`
  - `elevenlabs_api_key`

Worker key priority:

1. bundle `api_keys` from Drupal
2. worker `.env`
3. automation repo `.env`

DeepSeek also supports pool mode via `DEEPSEEK_API_KEYS=key1,key2,...` and lease tracking to spread concurrent jobs.

---

## 10) Artifact storage model

Outputs can be stored in two places:

- Drupal managed files (`public://story-pipeline/...`)
- External story asset root (`story_asset_path` / `STORY_ASSET_ROOT`)

Preferred modern pattern is disk asset root with per-story folder:

`{STORY_ASSET_ROOT}/{story_type}/{node-id}-{title-slug}/`

Subfolders:

- `meta/`
- `script/`
- `prompts/`
- `scenes/`
- `image-prompts/`
- `audio/`
- `audio/english/`

When assets are on disk, worker can omit huge file payload fields in Drupal update to avoid PHP post size issues; Drupal then syncs files from disk.

---

## 11) Story type taxonomy and stage prompt intent

For your requested understanding:

- "Config A" corresponds to taxonomy `field_stage_a` and output `field_stage_a_output`.
- "Config stage B" corresponds to taxonomy `field_stage_b` and output `field_stage_b_output`.
- "Image prompts config" corresponds mainly to taxonomy `field_stage_c`, which generates `prompt.txt` plus `image-prompts-only.txt`.
- Per-taxonomy prompt differences are what make Crime/General/English behave differently without changing worker code.

In short: taxonomy terms are the configuration layer; worker code is a shared execution engine.

---

## 12) Admin touchpoints in CMS

Useful URLs:

- Story type terms: `/admin/structure/taxonomy/manage/story_type/overview`
- Story list: `/admin/content` (defaults to Story filter)
- Settings/API keys: `/admin/config/content/story-pipeline`
- Run jobs UI: `/admin/content/story-pipeline/run`

Key drush commands:

- `vendor/bin/drush story-pipeline:info`
- `vendor/bin/drush story-pipeline:import-prompts`
- `vendor/bin/drush story-pipeline:import-keys`

---

## 13) Fast mental model for AI agents

If you need to debug or extend behavior, think in this order:

1. Story node state (`field_status`, `field_story_meta`, story type, full story present?)
2. Taxonomy prompt/config values for that story type
3. Bundle payload correctness (`/bundle`)
4. Worker run path (`generate` vs `storyboard`)
5. Artifact sync (disk + Drupal file fields)
6. Final status/update callback

Most "wrong prompt" bugs are taxonomy/template source issues.  
Most "job stuck" bugs are queue marker or worker runtime failures.  
Most "missing files" bugs are asset sync/payload size path issues.

---

## 14) File map (where to read next)

CMS core:

- `web/modules/custom/story_pipeline/src/Service/StoryPipelineManager.php`
- `web/modules/custom/story_pipeline/src/Controller/StoryPipelineApiController.php`
- `web/modules/custom/story_pipeline/story_pipeline.install`
- `web/modules/custom/story_pipeline/src/Form/StoryPipelineSettingsForm.php`

Worker core:

- `story-pipeline-worker/worker.py`
- `story-pipeline-worker/run_storyboard.py`
- `story-pipeline-worker/run_generate_story.py`
- `story-pipeline-worker/workspace.py`
- `story-pipeline-worker/asset_store.py`
- `story-pipeline-worker/secrets.py`

User guide:

- `STORY-PIPELINE-USER-GUIDE.md`

