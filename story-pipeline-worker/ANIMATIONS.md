# Map animation inserts

Separate from storyboard, Flow, Digen, and narration. A story job starts only from
**Generate animation videos** on the story.

## CMS

- Action: `/node/{nid}/animations` (permission `generate story animations`)
- Prompt editor: `/admin/config/content/story-pipeline/animation-prompt`
  (permission `administer animation prompt`)
- Prompt history is the `story_pipeline_anim_prompt` table, not config export.
- Job snapshots are `story_pipeline_anim_job` plus `animations/{job_id}/snapshot.json`
  under the story asset folder.

## Update an existing site

```bash
drush updatedb -y
drush cr
```

Restart any long-running pipeline worker only if it was started before this change.
Animation jobs are launched on demand and do not join the full-pipeline queue.

Install animation runtime dependencies once:

```bash
cd animation-lab
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cd map-story && npm install
```

Grant the two new permissions to the roles that should use them.

## Reproduce a job locally

```bash
cd story-pipeline-worker
./run.sh animations --snapshot /path/to/snapshot.json
# retry one clip without replanning completed clips:
./run.sh animations --snapshot /path/to/snapshot.json --retry-clip clip_01
# recompile + re-render every clip with the current map presentation (ignores completed skip):
./run.sh animations --snapshot /path/to/snapshot.json --regenerate-presentation
```

New CMS jobs snapshot `presentation_version` and `opening_policy_default` (`country_centered`).
Model-proposed `establish_view` / `world` scopes are normalized locally unless the snapshot sets
`opening_override` to `world_overview`.

`planner` in the snapshot is `deepseek` for CMS jobs. Set `planner` to `local` only
for offline tests. Rendering uses isolated Playwright (not Chrome port 9222) and a
per-clip `--cache-dir`, so two jobs do not share `plan.json`.

## Coverage

The worker resolves names against the local catalogue in `animation-lab`.
DeepSeek sees the script and short verified place summaries, not polygons or
the settlement table. Build the catalogue once, outside any page request:

```bash
cd animation-lab
.venv/bin/python geography_catalog.py import-boundaries
.venv/bin/python geography_catalog.py import-geonames --country IN
.venv/bin/python geography_catalog.py lookup "Vadnagar" --state "Gujarat"
.venv/bin/python geography_catalog.py lookup "वडनगर" --country IN
.venv/bin/python geography_catalog.py status
```

`refresh` rebuilds both layers and leaves previous animation plans unchanged.
Dataset licences and versions are in `assets/maps/catalog/SOURCE.md`.
Catalogue status in the CMS is `/admin/config/content/story-pipeline/animation-geography`.

Installed boundaries are India, states and union territories, and districts,
plus GeoNames populated-place points. Delhi’s state polygon is the National
Capital Territory. Vadnagar is a point marker, not an invented city polygon.
An exact alias resolves locally and does not call DeepSeek. A miss or an
ambiguous name is sent to DeepSeek only with up to 10 catalogue candidates.
The model may select one of those ids. It cannot invent geometry. Accepted
choices are cached in `animation-lab/assets/maps/catalog/resolution-cache.sqlite`.
The cache key includes the requested name, level, verified parents, passage,
candidate ids, catalogue version, and fallback version `2026.10-identity-fallback-v1`.
A catalogue rebuild changes that version, so old rows are not reused. Cached
ids are checked against the current record before use. They are not written
back as permanent aliases. Set `identity_fallback` on the job snapshot;
CMS map jobs set it to true, with at most 24 fallback calls. An API failure
is `fallback_unavailable`, which is separate from `needs_geographic_data`.
A parent name from the planner is context, not proof the place belongs to that
parent. A user-confirmed state or district is kept even when it removes every
candidate. Devanagari names are transliterated only to find candidates; the
spelling is not accepted by itself. On the story Animations page, unresolved
required places can be mapped to a catalogue id or a custom point and the same
job resumes with `--resume-locations`. Overrides are stored in the job folder
as `location-overrides.json` and in `story_pipeline_anim_override`. Remembered
spellings live in `animation-lab/assets/maps/catalog/confirmed-aliases.sqlite`
and can be disabled at `/admin/config/content/story-pipeline/location-aliases`.
Places that still do not resolve are `needs_geographic_data`,
`needs_location_clarification`, or `needs_review`, and do not block clips
that do resolve.

## Timeline

Timeline is a separate type on the same Generate animation videos form.
It does not import the geographic catalogue. Planning still uses DeepSeek
unless the snapshot says `"planner": "local"`.

See `animation-lab/TIMELINE.md` for the sample command, prompt URL, and
how to add a later animation type. Map commands keep working:

```bash
cd story-pipeline-worker
./run.sh animations --snapshot /path/to/map-snapshot.json
```

A snapshot without `animation_type` stays a map job.

## Documentary types

Text highlighting, photo sequences, before/after, document highlighting,
relationship diagrams, data animations, and storyboard reconstructions use
the same dispatcher. Each type has its own CMS prompt. Samples, commands,
and the prompt editor query are in `animation-lab/DOCUMENTARY.md`.


