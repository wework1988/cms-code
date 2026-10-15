# Cinematic overlays

Standalone annotations on an existing MP4. The shared sample set, including typography, is in [DOCUMENTARY_GRAPHICS.md](DOCUMENTARY_GRAPHICS.md). This module is not registered with the CMS animation runner.

The renderer draws each frame from `time = frame / fps`. It does not record a video playing in real time. Playwright captures a transparent PNG (`omitBackground`), and FFmpeg composites that sequence over a copy of the source. The source file is left in place. Audio is copied when the source has an audio stream. This sample's source has no audio, so the export has no audio either. No narration is generated.

The sample uses the source frame rate, 16 fps, and the source frame count, 81. Frames are not duplicated.

## Render the sample

From `animation-lab`:

```bash
.venv/bin/python -m cinematic_overlays.cli render-sample
```

That reads `cinematic_overlays/samples/scene-1-callout.json` and writes:

- `output/cinematic-overlays/scene-1-overlay.mp4`
- `output/cinematic-overlays/contact-sheet.jpg`
- `output/cinematic-overlays/frames/reveal.jpg`
- `output/cinematic-overlays/frames/hold.jpg`
- `output/cinematic-overlays/frames/exit.jpg`
- `output/cinematic-overlays/sample-plan.json` (a copy of the plan that was rendered)
- `output/cinematic-overlays/verification.json`

To render a different plan into the same folder:

```bash
.venv/bin/python -m cinematic_overlays.cli render --plan cinematic_overlays/samples/scene-1-callout.json --output output/cinematic-overlays
```

## Edit the sample

Open `cinematic_overlays/samples/scene-1-callout.json`. Coordinates are fractions of the displayed frame. `x` and `y` run from 0 to 1. The building anchor and the label position are separate.

- Label text: `overlays[0].text`. The sample says `द्वीप पर स्थित जेल`. It does not name a prison.
- When it appears: `start_time` (seconds).
- Line draw: `reveal_duration` (0.5 seconds in the sample). The label stays hidden during the draw.
- Label fade: `label_fade_duration` (0.35 seconds).
- Readable hold: `hold_duration` (2 seconds, full opacity).
- Fade out: `exit_duration` (0.45 seconds).
- Label position: `label.x` and `label.y`. The sample places it in the upper-left sky, away from the building.
- Building position: `anchor_keyframes`. Each entry is `t`, `x`, and `y`. The renderer smoothsteps between those hand-placed points and holds the first point before the first time and the last point after the last time.

The camera drifts in this clip. The four keyframes were placed by eye at 0s, 1.5s, 3.0s, and 4.5s. That is not automatic tracking. A fixed screen point would slide off the building. `anchor_mode` may be `fixed` or `manual_keyframes`. A fixed anchor on a moving camera has to set `fixed_anchor_acknowledged` to true, and the plan then states that the point stays fixed in the frame.

Colors are `style.line`, `style.backing`, and `style.ink`.

## Overlay types

The renderer supports four types. The sample uses only `location_callout`.

- `location_callout`: anchor dot, leader line, then the label.
- `detail_highlight`: a rectangle in `rect` (`x`, `y`, `width`, `height`), drawn as a thin stroke.
- `date_label`: text at `label`, fading in over `reveal_duration`.
- `route_line`: a line through the supplied `points`, drawn by length over the reveal.

## Later planner

A future planner may choose the narration phrase, the overlay type, the label text, and the purpose. Timing should come from the scene's existing alignment. The planner must not invent `anchor`, `anchor_keyframes`, `label`, `rect`, or `points`. Those come from a manual selection, a visual measurement, or a tracker. A plan that sets `coordinate_source` to `deepseek`, `model`, `text`, or `narration` is rejected. This sample does not call a model.
