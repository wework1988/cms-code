# Timeline animation

Timeline is the second animation type. Map generation is unchanged and still runs through `run_map_animations.py`.

Story text still goes to DeepSeek when the job planner is `deepseek`. The timeline compiler, not the model, sets reveal times and horizontal positions. There is no geographic lookup and no Flow image generation.

## What is shared

`animation-lab/animation_core/` holds the type registry, the job/clip field list, progress files, clip-directory checks, and MP4 verification.

`story-pipeline-worker/run_animations.py` reads `animation_type` and dispatches:

- missing or `map` → existing map worker
- `timeline` → `animation_types/timeline/runner.py`
- anything else → a failed job, without importing the map catalogue

## What is timeline-specific

`animation-lab/animation_types/timeline/` validates the plan, compiles equal-step reveals, shapes Hindi with the local Devanagari Sangam MN font (CoreText), and draws frames with Pillow into a silent H.264 file.

The older `cinematic.py` / `generate_video.py` timeline remains the storyboard experiment. CMS timeline jobs do not use it.

## Sample

```bash
cd animation-lab
.venv/bin/python animation_types/timeline/cli.py render-sample
```

Input: `animation-lab/examples/timeline-story.txt`

Output: `animation-lab/output/timeline-sample/timeline.mp4` and `contact-sheet.png`.

## Worker

```bash
cd story-pipeline-worker
./run.sh animations --snapshot /path/to/snapshot.json
```

A timeline snapshot sets `"animation_type": "timeline"`. `"planner": "local"` skips DeepSeek and is for tests. CMS jobs use `deepseek` and the saved timeline prompt.

Retry one clip without a new plan call:

```bash
./run.sh animations --snapshot /path/to/snapshot.json --retry-clip clip_01
```

`--replan` asks DeepSeek again. A failed new render does not replace a verified MP4.

## CMS

1. Run `drush updatedb -y` and `drush cr` so prompt and job rows gain `animation_type`.
2. Open `/node/{nid}/animations`.
3. Choose Timeline. MapLibre / OpenLayers stay hidden.
4. Generate animation videos.
5. Edit the timeline prompt at `/admin/config/content/story-pipeline/animation-prompt?animation_type=timeline`. The map prompt stays on its own history.

Clips are not inserted into the final documentary.

## Limits

- Years and undated narrative stages only. No exact dates, ranges, decades, or BCE/CE.
- 3 or 4 events. Fewer is an error, not a reason to invent one.
- Equal steps are milestone order, not elapsed historical time.
- Captions that do not fit the horizontal boxes fail validation instead of being shrunk.
- A matching quote means the script supports the line. It is not an independent fact check, and that note is metadata, not a caption on the video.

## Adding the next type later

1. Add a package under `animation_types/<name>/` with validation, compile, and render.
2. Register it in `animation_core/registry.py` `IMPLEMENTED`. Until then it stays in `FUTURE_TYPES` and is not a CMS option.
3. Teach `run_animations.py` to call that runner without importing unrelated types.
4. Add a prompt constant and a CMS option only when a sample video has been checked.
