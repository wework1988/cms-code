# Documentary animations

Map and Timeline stay on their own workers and prompts. These seven types share one browser renderer in `documentary-browser/`. DeepSeek may choose a passage, an approved template, and a structured plan. It does not return JavaScript, HTML, CSS, or shell commands. Sample renders do not call DeepSeek.

The frame clock is explicit: frame N is at `N * 1000 / fps`. `renderAt` sets that state directly, including when the same time is requested twice. Playwright captures still frames. FFmpeg encodes them. A failed encode does not replace a verified MP4.

Default sample output is 1920×1080, 30 fps, H.264, yuv420p, faststart, 12 seconds, with a 2 second hold and no narration or music.

## Templates

| Type | Templates | Sample rendered |
| --- | --- | --- |
| text_highlighting | editorial_statement, quote_annotation, contrast_reveal | editorial_statement |
| photo_sequences | fullscreen_caption, archival_frame, paired_annotation | archival_frame |
| before_after | split_divider, matched_crossfade, editorial_panels | editorial_panels |
| document_highlighting | archival_desk, full_frame, excerpt_panel | excerpt_panel |
| relationship_diagrams | chain, radial, hierarchy | chain |
| data_animations | bar_comparison, line_trend, number_counter | bar_comparison |
| storyboard_reconstructions | cinematic_sequence, panel_expand, detail_focus | detail_focus |

Style presets are `cinematic_dark`, `archival_paper`, and `clean_editorial`.

## Samples

Comparison index: `output/animation-samples/INDEX.md`

| Type | MP4 | Contact sheet |
| --- | --- | --- |
| text_highlighting | `output/animation-samples/text_highlighting/sample.mp4` | `output/animation-samples/text_highlighting/contact-sheet.jpg` |
| photo_sequences | `output/animation-samples/photo_sequences/sample.mp4` | `output/animation-samples/photo_sequences/contact-sheet.jpg` |
| before_after | `output/animation-samples/before_after/sample.mp4` | `output/animation-samples/before_after/contact-sheet.jpg` |
| document_highlighting | `output/animation-samples/document_highlighting/sample.mp4` | `output/animation-samples/document_highlighting/contact-sheet.jpg` |
| relationship_diagrams | `output/animation-samples/relationship_diagrams/sample.mp4` | `output/animation-samples/relationship_diagrams/contact-sheet.jpg` |
| data_animations | `output/animation-samples/data_animations/sample.mp4` | `output/animation-samples/data_animations/contact-sheet.jpg` |
| storyboard_reconstructions | `output/animation-samples/storyboard_reconstructions/sample.mp4` | `output/animation-samples/storyboard_reconstructions/contact-sheet.jpg` |

Each verified file is 1920×1080, 30 fps, 12.0 seconds, 360 frames, H.264, yuv420p, faststart.

Fixture pictures and the PDF are marked synthetic. They live in `examples/documentary/assets/`. Originals are only read.

## Commands that were run

From `animation-lab`, with `animation-lab/.venv`:

```bash
.venv/bin/python animation_types/text_highlighting/cli.py render-sample
.venv/bin/python animation_types/photo_sequences/cli.py render-sample
.venv/bin/python animation_types/before_after/cli.py render-sample
.venv/bin/python animation_types/document_highlighting/cli.py render-sample
.venv/bin/python animation_types/relationship_diagrams/cli.py render-sample
.venv/bin/python animation_types/data_animations/cli.py render-sample
.venv/bin/python animation_types/storyboard_reconstructions/cli.py render-sample
```

Plan a story locally, without an API key:

```bash
.venv/bin/python -m animation_types.documentary.cli plan-local \
  --type text_highlighting \
  --story examples/documentary/text-story.txt \
  --output output/animation-samples/text_highlighting/local-plan
```

Render a compiled plan that is already on disk:

```bash
.venv/bin/python -m animation_types.documentary.cli render-plan \
  --type text_highlighting \
  --plan output/animation-samples/text_highlighting/compiled-plan.json \
  --output output/animation-samples/text_highlighting-from-plan
```

Run the worker on a local snapshot. This does not call DeepSeek:

```bash
animation-lab/.venv/bin/python story-pipeline-worker/run_animations.py \
  --snapshot animation-lab/output/animation-samples/text-worker/snapshot.json
```

That job finished as `completed`. The clip is `output/animation-samples/text-worker/clips/clip_01/sample.mp4`.

CMS jobs use the same dispatcher (`story-pipeline-worker/run.sh animations --snapshot PATH`) with `planner` set to `deepseek`. A DeepSeek call was not made for these samples.

Tests that passed:

```bash
.venv/bin/python -m unittest tests.test_documentary tests.test_timeline tests.test_map_story tests.test_geography_catalog
```

## CMS prompts

Each type has its own revision history. Map rows were left unchanged (prompt ids 1 and 2). Timeline stayed id 3. Update `story_pipeline` 9034 inserted ids 4–10.

Edit a prompt at:

`/admin/config/content/story-pipeline/animation-prompt?animation_type=TYPE`

`TYPE` is one of `map`, `timeline`, `text_highlighting`, `photo_sequences`, `before_after`, `document_highlighting`, `relationship_diagrams`, `data_animations`, `storyboard_reconstructions`.

Generate from `/node/{nid}/animations`. The form shows only the controls for the selected type: style, image paths, before/after files, document page and region, relationship JSON, data JSON, or reconstruction images. Empty required assets finish as `needs_assets` or `needs_review`. They are not replaced with a generic picture.

## Limits

- The sample MP4 for each type uses one template. The other templates are in the renderer and are accepted by validation.
- The document sample highlights a supplied region on a synthetic PDF rendered with PDF.js. It does not extract text positions, and it does not treat a scan as selectable PDF text. OCR without a confidence value returns `needs_review`.
- Photo motion is a small 2D scale and pan. It is not parallax, and it does not invent hidden parts of a picture.
- Bar charts use a zero baseline. Axis tick marks are the scale, not extra observations.
- Storyboard samples use local fixture images and show “Illustrative reconstruction”. This renderer does not launch Flow or any image generator.
- Hindi is revealed by phrase, line, or label. Characters are not animated separately. Fonts are Noto Sans and Noto Sans Devanagari (SIL Open Font License) in `documentary-browser/assets/fonts/`.
- DeepSeek planning code is in each module, with thinking disabled and a repair pass. It was not executed against the API in this run.
