# Local documentary animation sample

## Parchment map: India → Bangladesh → arrow and text

Run this offline map template; it needs no DeepSeek or Flow credits:

```bash
python3 map_video.py
```

Output: `output/maps/india-bangladesh.mp4` (silent 10 seconds, Full HD, 30 FPS).
It starts with India highlighted, zooms toward Bangladesh between seconds 3 and 6.5,
then draws an arrow and reveals the Hindi label and caption.

Edit `examples/india-bangladesh-map.json` to change text and timing. Coordinates are
`[longitude, latitude]`. `longitude_span` controls framing: smaller means closer.
`callout.anchor` is the geographic point the arrow identifies. This is a label leader,
not a military route. `first_country` and `target_country` match Natural Earth ADMIN
names. The bundled renderer currently covers South Asia and neighboring countries.
Changing the region outside 45–120° E, 10° S–55° N requires updating its geometry filter.

```bash
python3 map_video.py --config examples/india-bangladesh-map.json \
  --output output/maps/my-map.mp4
```

Use actual voiceover timings for `zoom.start`, `zoom.end`, and `callout.start` to align
the animation with your first and second narration lines. Audio is not embedded.
Geography and dataset provenance are recorded in `assets/maps/SOURCE.md`.

## Generate actual MP4 clips

`generate_video.py` is now implemented. It automatically uses the existing `.venv`
for Pillow and FFmpeg, even when launched with system `python3`.

Render your existing plan without another API call:

```bash
python3 generate_video.py --plan output/my-plan.json
```

Or select scenes and render from a story in one command:

```bash
python3 generate_video.py --story examples/iran-story.txt
```

For your own story, create the UTF-8 text file first, then use `--story my-story.txt`.
The default API key file is `../story-pipeline-worker/.env`. Plans generated from a
story are cached under the output directory; an unchanged story/model reuses its plan.

Output: `output/videos/clip_01-storyboard.mp4`, `clip_02-timeline.mp4`, PNG previews
and `videos.json`. Use `--output-dir output/another-story` for a separate project.
Default is silent Full HD, 30 FPS, 10 seconds per clip. `--duration 15` changes pacing.

Without supplied images, the default provider generates realistic scene artwork with
an isolated Flow adapter, then renders full-screen camera movement and cross-dissolves.
Flow requires an existing signed-in Chrome session with CDP enabled (normally port 9222).
It uses image credits. It never quits Chrome or clones your profile. Use the browser
when it is idle; avoid running the existing pipeline at the same time.

All prompts, downloaded images, jobs, pairing token and adapter state are under
animation-lab. The original flow-image-agent is only read to build a local code snapshot
under `.runtime`; it is not modified or executed from its original directory. Existing
Playwright dependencies are read through a symlink. Source code must remain available
for first-time setup. Flow opens its own project and keeps its project URL separately.

Timeline clips animate the plan's labels and event sequence directly. Flat artwork uses
pan/zoom, not independent actor movement. `--image-provider preview` is an explicit
offline geometric placeholder mode; it is no longer the default.

Prepare prompts without generating images or spending Flow credits:

```bash
python3 generate_video.py --plan output/my-plan.json --prepare-only
```

Replay the included two-shot Iran sample without DeepSeek or Flow:

```bash
python3 generate_video.py --plan examples/iran-cinematic-plan.json \
  --images-dir assets/iran-cinematic --output-dir output/iran-cinematic
```

The included sample artwork was generated with the built-in imagegen tool. Its exact
prompts are saved in `assets/iran-cinematic/prompts.json`. Future automatic runs use Flow.
This is an artistic reconstruction; costumes, architecture and religious details need
editorial review before publication.

For actual scene artwork, generate images using the JSON image prompts, then save
them as `assets/clip_01-01.png`, `assets/clip_01-02.png`, etc. JPG/WebP also work:

```bash
python3 generate_video.py --plan output/my-plan.json --images-dir assets
```

All storyboard scene images must exist when `--images-dir` is supplied. Pan/zoom
supports flat images; parallax falls back to zoom. Crossfade uses a true overlap within
the stated clip duration. Videos have no audio. Rendering needs macOS Swift command-line
tools for Hindi text. Image prompts determine cached Flow job identities: changing a
prompt produces a new job; existing completed shots are reused for an unchanged job.

## Generate an animation plan from any story with DeepSeek

`plan_animations.py` reads a UTF-8 story and selects two useful inserts by default:
one illustrated storyboard and one chronological timeline. It produces source excerpts,
scene durations, Hindi captions, camera movements, English image-generation prompts,
layer suggestions, timeline events, and editorial verification notes.

This script uses Python's standard library; it needs no additional pip packages.
It sends the supplied story to DeepSeek and uses your API quota. Copy `.env.example`
to `.env` and enter your key locally, or supply DEEPSEEK_API_KEY in your environment.
You can also point at an existing project dotenv file without copying its key:

```bash
cd /Users/alokkumarverma/project/cms-code/animation-lab
python3 plan_animations.py --story examples/iran-story.txt \
  --env-file ../story-pipeline-worker/.env --output output/iran-plan.json
```

For your own input, save narration as `my-story.txt` and run:

```bash
python3 plan_animations.py --story my-story.txt --output output/my-plan.json
```

Options: `--clips 4`, `--language en`, `--style "archival ink illustration"`,
`--model MODEL_ID`, `--max-tokens 8000`. DEEPSEEK_MODEL from the process environment
also selects the model; `.env` loading reads only DEEPSEEK_API_KEY.
Default model is `deepseek-flash`, as shown in DeepSeek's current JSON-mode example.
Reference: https://api-docs.deepseek.com/guides/json_mode/

Preview the API request without sending anything or needing a key:

```bash
python3 plan_animations.py --story examples/iran-story.txt --dry-run \
  --output output/request-preview.json
```

Validate an edited plan without calling DeepSeek:

```bash
python3 plan_animations.py --story examples/iran-story.txt \
  --validate output/iran-plan.json
```

The planner validates exact source excerpts, clip counts, supported motions, durations,
timeline reveal order, evidence quotes, and year references. It allows one repair call
for invalid output and bounded retries for rate limits/server errors. Output is replaced
only after validation succeeds. API keys are never saved in generated JSON.
Thinking is explicitly disabled to reserve the token budget for JSON. The default
output budget is 8,000 tokens. A truncated response is retried once from the original
story with double the budget (up to 32,768 tokens), rather than repairing partial JSON.

**This is a planning format, not the existing map renderer's input.** Use generate_video.py
for storyboard/timeline rendering. Images are null until you generate or
choose actual assets using the image prompts. Durations are editorial suggestions,
not voiceover alignment. `parallax` needs separate image layers; a flat image only
supports pan/zoom. Transition durations must eventually be handled by the renderer
within the stated clip duration. Timeline cards are equally spaced sequence steps,
not a proportional historical axis.

Historical facts are not independently verified. Exact dates must come from the input;
other periods remain approximate. Every timeline event is marked for verification.
The included Iran story is the user's original draft, not an endorsed factual account.
Review generated warnings, chronology, depictions and captions before production.

Tests (no API calls): `python3 -m unittest discover -s . -p 'test_plan_animations.py'`.

This isolated experiment renders a silent 10-second, 1280×720, 30 FPS H.264 MP4. It combines Hindi location reveals, coordinate-based city placement, a slow camera zoom, animated connections and a reveal timeline. The regional backdrop is schematic, not an authoritative map. Reveal timings are editorial timings, not historical event dates; connections illustrate spread, not verified troop movements.

## Run on your Mac

```bash
cd /Users/alokkumarverma/project/cms-code/animation-lab
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python render.py
```

After initial installation rendering works offline. FFmpeg is provided by imageio-ffmpeg; Homebrew is unnecessary. This sample targets macOS and uses its native text shaping through a small Swift/AppKit helper. Swift command-line tools must be available (`swiftc`). The fonts are macOS Arial and Devanagari Sangam MN.

Open `output/1857-sample.mp4` in your video editor. `output/1857-sample.png` is a still preview. There is no voiceover or music, so you can test against your existing narration.

## Change the sample

Edit `sample.json` to change labels, city coordinates, reveal timings, connections and resolution. For Full HD use width 1920 and height 1080. The current geographic framing is for northern India; adapting it to another region requires changing the projection centre and scale in render.py.

```bash
.venv/bin/python render.py --config sample.json --output output/my-scene.mp4
```

Frames use explicit timestamps and are streamed to the encoder instead of saved as hundreds of images. This provides a simple future pipeline interface: scene JSON → render command → MP4 asset. Nothing has been connected to the CMS pipeline yet. After reviewing this sample, accurate licensed geographic data, narration-aligned timing and additional templates can be added.

## Map engine comparison (MapLibre / OpenLayers / Cesium)

Three silent 10s Full HD samples from one shared story JSON, rendered with an isolated Playwright Chromium (not Chrome :9222):

```bash
cd map-comparison
npm install
npm run install-browser
npm run render -- --engine all
```

Outputs: `output/map-comparison/{maplibre,openlayers,cesium}.mp4`, previews, contact sheet, `manifest.json`.
Edit `map-comparison/story.json` for future stories. Preview with `npm run preview`.
