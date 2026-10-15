# Geographic storytelling (animation-lab)

Plain-language instruction → DeepSeek semantic plan → local geographic resolve →
optional candidate fallback → camera compile → isolated Playwright MP4.

Does **not** modify Flow generation or the main documentary video flow.
Map jobs can set `identity_fallback`. An uncertain name is sent to DeepSeek
only with up to 10 catalogue candidates. Accepted decisions are stored in
`assets/maps/catalog/resolution-cache.sqlite`. The key includes the name,
level, verified parents, passage, candidate ids, catalogue version, and
fallback version. A catalogue rebuild misses old rows. Cached ids are
checked again before use and are not saved as permanent aliases.

## First example

INDIA (country-centered open) → UTTAR PRADESH → GORAKHPUR DISTRICT → arrow callout (`गोरखपुर`)

Sample input: [`examples/gorakhpur-map.txt`](examples/gorakhpur-map.txt)

## Commands

Plan + render (DeepSeek):

```bash
cd animation-lab
python3 generate_map_video.py \
  --input examples/gorakhpur-map.txt \
  --env-file ../story-pipeline-worker/.env \
  --engine maplibre \
  --duration 18 \
  --output-dir output/gorakhpur-map
```

Plan only (validate + resolve + compile, no video):

```bash
python3 generate_map_video.py \
  --input examples/gorakhpur-map.txt \
  --env-file ../story-pipeline-worker/.env \
  --plan-only \
  --output-dir output/gorakhpur-map
```

Offline / no API (built-in Gorakhpur golden plan):

```bash
python3 generate_map_video.py --use-golden --engine maplibre \
  --output-dir output/gorakhpur-map
```

Re-render a saved semantic plan (no DeepSeek):

```bash
python3 generate_map_video.py \
  --plan output/gorakhpur-map/semantic-plan.json \
  --engine openlayers \
  --output-dir output/gorakhpur-map
```

Render resolved plan directly:

```bash
node map-story/render.mjs \
  --plan output/gorakhpur-map/resolved-plan.json \
  --engine maplibre \
  --output-dir output/gorakhpur-map
```

Tests:

```bash
python3 tests/test_map_story.py
```

## Outputs (`output/gorakhpur-map/`)

| File | Meaning |
|------|---------|
| `semantic-plan.json` | Validated DeepSeek (or golden) intent |
| `resolved-plan.json` | Feature refs + compiled camera/highlights/callout |
| `resolved-plan.json` → `composition` | Stage diagnostics (targets, camera, label placement, warnings) |
| `maplibre.mp4` / `openlayers.mp4` | 1920×1080 · 30 fps · H.264 yuv420p · silent |
| `qa/*.png` | Representative frames |
| `contact-sheet.png` | Frame strip |
| `manifest.json` | Probe + paths |

## Architecture

1. **Planner** (`map_story/planner.py`) — DeepSeek JSON mode; local schema validation; one repair attempt.
2. **Resolver** (`map_story/geo.py` + `registry.json`) — names/levels/parents → cached GeoJSON; rejects missing/ambiguous matches; district ≠ city.
3. **Compiler** (`map_story/compile.py`) — bbox framing, highlight persistence, callout anchors (interior point).
4. **Renderer** (`map-story/`) — deterministic timestamp draw; Playwright + FFmpeg.
5. **Verification** — full decode; resolution/duration/fps/frame count.

Use `?debugOverlay=1` on the map-story preview URL to visualize safe areas,
anchors, and composed label boxes for diagnostics (not part of exported MP4).

DeepSeek must **not** invent coordinates or polygons. Those come from data + compiler.

### Action persistence

- **highlight** — stays until superseded; `parent_context: "subdued"` demotes the parent fill.
- **show_label** — visible for its shot window (short fades).
- **zoom_to_boundary** — camera eases across the shot; short hold at the end.
- **show_callout** — appears at shot start; held through the shot (~3s in the example).
- **hold** — freezes camera/styles.

## Geographic coverage (honest)

The automatic map workflow reads the local catalogue, not a per-story place list.
Installed countries are India (`IN` / `IND`), Pakistan (`PK` / `PAK`), and
Afghanistan (`AF` / `AFG`): country outlines, first-level areas, and settlements
from the pinned Natural Earth, geoBoundaries, and GeoNames files.

Display labels stay country-specific. India uses “State / Union territory”.
Pakistan uses “Province / Territory”. Afghanistan uses “Administrative region”.
The stored level for those units remains `state`.

A name that exists in more than one country, or as both a city and a province,
stays unresolved until the story names the country or feature type, the identity
fallback chooses one supplied catalogue id, or someone picks it in the CMS.
Punjab in India does not satisfy a Pakistan constraint. Kabul city and Kabul
province stay separate records.

See `assets/maps/catalog/SOURCE.md` for versions, licences, the settlement cutoff,
and names that are left unmatched on purpose.

## Terrain limitations

Natural Earth II 50m shaded relief (public domain) provides the world background
and a South Asia raster covering India, Pakistan, and Afghanistan. This is not
high-resolution satellite imagery; district-scale texture is coarse. A country
outside that raster drops the regional layer and caps zoom. Flat atlas themes
do not use the relief raster. Oceans are graded toward dark navy for documentary
contrast.

## Style

Documentary look: dark navy oceans, natural terrain, translucent crimson India,
subdued India when UP focuses, red UP, yellow-green Gorakhpur, warm-white borders,
soft glow, large Hindi labels, minimal vignette. MapLibre uses modest pitch;
OpenLayers stays overhead with the same geography and timings.
