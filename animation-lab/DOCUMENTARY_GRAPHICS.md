# Documentary graphics

Two standalone modules share one renderer. Neither is registered with the CMS, and neither changes the story or video pipeline.

- `cinematic_overlays` draws callouts, spotlights, fact panels, evidence insets, routes, and measurements on a copy of an existing video.
- `documentary_typography` draws location titles, impact words, impact phrases, dates, key numbers, chapter titles, and quotations.

The footage stays the picture. Each sample is its own MP4. Coordinates are fractions of the displayed frame: origin at the top-left, `x` to the right, `y` downward, both from 0 to 1.

## Render

From `animation-lab` this command completed and wrote every sample below:

```bash
.venv/bin/python -m documentary_graphics.cli render-samples
```

One sample:

```bash
.venv/bin/python -m documentary_graphics.cli render-samples --only prison-callout
```

The prison samples composite onto `general/152-priso-story-updated/video/scene_1.mp4`. That file is left untouched. The earlier annotated file `output/cinematic-overlays/scene-1-overlay.mp4` is not used as an input.

## Prison samples

All three are 1920×1088, 16 fps, 81 frames, 5.06 seconds, H.264 `yuv420p`, faststart, and no audio, matching the source. The source has no audio stream.

| Sample | Preset | What you see |
| --- | --- | --- |
| `output/documentary-graphics/prison-callout/prison-callout.mp4` | cinematic_minimal | Thin leader, dot on the main upper building, label `द्वीप पर स्थित जेल` |
| `output/documentary-graphics/prison-impact-phrase/prison-impact-phrase.mp4` | documentary_bold | `भागना मुश्किल था`, with `मुश्किल` in red |
| `output/documentary-graphics/prison-title/prison-title.mp4` | cinematic_minimal | `एक अलग दुनिया`, marked `प्रदर्शन` |

Contact sheets and reveal / hold / exit frames sit beside each MP4. `phone-hold.jpg` is the hold frame at 390 pixels wide.

The callout is a neutral label. It does not name a prison. The phrase is a visual demonstration, recorded as `factual_claim: false` in the plan and in `verification.json`. The title is an editorial demonstration, not a quotation.

The clean source is linked from `output/documentary-graphics/original-reference.json`, with stills in `output/documentary-graphics/original-stills/`.

## Fixture samples

These use generated blank plates, not the prison footage. On-screen text says `काल्पनिक प्रदर्शन` or `FICTIONAL CROP`. The values are not evidence.

| File | Treatment |
| --- | --- |
| `demo-location-title/demo-location-title.mp4` | Region `उत्तराखंड` over place `उत्तरकाशी` |
| `demo-date-year/demo-date-year.mp4` | Year `1854` and the note `काल्पनिक वर्ष` |
| `demo-key-number/demo-key-number.mp4` | `18` `किमी`, kind `distance` |
| `demo-portrait/demo-portrait.mp4` | Same location stack, centered, 1080×1920 |
| `demo-impact-word/demo-impact-word.mp4` | `लापता` |
| `demo-quote/demo-quote.mp4` | Supplied quotation and attribution |
| `demo-spotlight/demo-spotlight.mp4` | Focus rectangle with steady dimming |
| `demo-key-fact/demo-key-fact.mp4` | Small fact panel |
| `demo-evidence/demo-evidence.mp4` | Supplied crop and source label |
| `demo-route/demo-route.mp4` | Screen-space route and arrow |
| `demo-measurement/demo-measurement.mp4` | Bracket between two supplied points |

Fixture videos are 1920×1080, or 1080×1920 for the portrait, at 24 fps, 108 frames, 4.5 seconds, with no audio.

## Edit a sample

Open the JSON named in the table below, change the fields, and run `render-samples` again.

| Change | Field |
| --- | --- |
| Words | `text`, `runs`, `region`, `place`, `year`, `value`, `unit` |
| When it appears | `start_time`, `reveal_duration`, `hold_duration`, `exit_duration` |
| Callout label delay | `label_fade_duration` |
| Look | `preset`: `documentary_bold`, `cinematic_minimal`, or `archival_editorial` |
| Screen position | `label.x` and `label.y`, or `label_placement: "auto"` with `prefer` |
| Building position | `anchor_keyframes` entries `t`, `x`, `y` |

`documentary_bold` uses a gold accent and red only on an emphasized run. `cinematic_minimal` stays warm white and thin. `archival_editorial` uses a warmer backing. Token values live in `documentary_graphics/tokens.py`.

Emphasis is a text run with `"emphasis": true`. The renderer does not search the string for a word.

## Planning files

`documentary_graphics/prompts/policy.md`, `typography.md`, and `overlays.md` are the later planner instructions. This sample set does not call a model. A planner may choose the treatment, the supplied words, the emphasis, and a corner. It may not invent facts or coordinates. `tracked_anchor` and `scene_aligned` raise an error instead of falling back to a fixed point.

## Limits

- Hand-placed keyframes follow the building in the callout. That is not a tracker. The camera drifts, and a fixed screen point would leave the building.
- Automatic placement only avoids margins, the subtitle band, protected rectangles, and other graphics. It does not look at the picture. There is no face or object detector.
- Routes and measurements use screen coordinates. Pixel distance is not converted into a real-world length.
- `tracked_anchor` and `scene_aligned` are not implemented.
- Hindi is drawn as whole words and lines. The bundled fonts are Noto Sans and Noto Sans Devanagari Regular. Hierarchy is size and color.
- The state of every frame is `frame / fps`. The export keeps the source frame rate. Raising the frame rate would not add motion to the prison clip.
- A keyframe span that crosses a supplied scene cut is rejected. Cut times have to be supplied. The renderer does not detect cuts.
- No CMS controls and no worker dispatch were added.
