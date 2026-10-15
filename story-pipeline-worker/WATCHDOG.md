# Durable story pipeline

Normal `run.sh storyboard ID`, `full ID`, and `elevenlabs ID` commands now create a durable job and wait for its terminal status. A macOS LaunchAgent is configured to check jobs every 300 seconds. The waiting launcher also checks every 300 seconds. Both paths share a lock. Advanced storyboard flags still use the existing direct runner.

## Start the background service

The LaunchAgent was activated and verified on 12 October 2026. To activate it again if it is unloaded, run this in macOS Terminal:

```sh
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.cms.story-pipeline-watchdog.plist"
launchctl print "gui/$(id -u)/com.cms.story-pipeline-watchdog"
```

Confirm the printed service has `run interval = 300 seconds`. It runs at login and at five-minute intervals while the Mac is awake and the user is logged in. It cannot run while the Mac is asleep or powered off. Chrome, browser sign-in, and Drupal must remain available for their stages. No existing unmanaged jobs are automatically imported.

## Behavior

- Each stage has its own durable status, attempts, last progress time, validation report, error and log path.
- One initial stage attempt plus at most TWO stage retries. Restarting the monitor or pressing Run again does not reset the budget. This is a stage-attempt limit, not a promise that external SDKs make only three HTTP requests.
- Five minutes without observed changes to output files or meaningful log content makes an owned runner eligible for termination. The next poll retries, subject to the limit. Poll timing means a stall may take five to ten minutes to detect, followed by the retry delay.
- Routine `[assets]` copy/mirror messages and heartbeat/wait messages do not count as generation progress.
- On macOS, active jobs renew a timed `caffeinate -i` assertion each poll to prevent idle system sleep, including retry delays. The display can sleep and the screen can remain locked. Assertions expire within eleven minutes after monitoring stops or all jobs become terminal. Closing a laptop lid, explicit sleep, logout or power loss can still interrupt work.
- Completed scene sets are reused. Storyboard retries use saved A/B outputs and prompt-gap filling when available. Digen uses missing-only mode. Failed/configuring Flow scenes can be requeued; uncertain submitted results require review.
- Script/storyboard/audio stages may rerun an incomplete stage; there is no guaranteed resume inside an interrupted API response or audio chunk. Completed audio stages are retained.
- All managed jobs share one execution lease to prevent duplicate browser work. This does not control manually started external browser agents.
- An explicit CMS Stop persists before killing the worker and prevents automatic restart. An orphaned worker retaining the lease pauses recovery for review.
- Policy rejection, uncertain Flow submissions, invalid files and exhausted retries become `needs_attention`; Drupal maps this to its existing `failed` status.
- Drupal completion is published only when all enabled stages pass their checks. Disabled stages are recorded as skipped.

## Checks and limits

Storyboard checks compare scene IDs in scene breakdown, image prompts, and motion prompts. Images require the exact expected scene IDs, a single file per ID, readable dimensions, width at least 2000 pixels and approximately 16:9. Videos require exact expected scene IDs, complete MP4 container boxes, a video track, positive duration and media data; this is not a full frame decode. Audio requires successful stage exit and readable, nonempty MP3 files; narration text coverage is not measured. Existing assets are not matched to content hashes of revised prompts: use a new story for revised content instead of silently reusing an old job.

## Inspect and control

Run from `/Users/alokkumarverma/project/cms-code/story-pipeline-worker`:

```sh
./run.sh watchdog status 170
./run.sh watchdog stop 170
./run.sh watchdog resume 170
```

Resume preserves attempt counts and refuses exhausted stages or unresolved Flow submissions. A completed job cannot be reset through Resume. Replace 170 with the Drupal node ID, not the asset-folder number unless they are the same.

Authoritative state: `.pipeline-jobs/story-ID.json`. Per-story mirror: `meta/pipeline-status.json`. Per-stage logs and result records are in `.pipeline-jobs/`. Drupal also receives the stage data in `story_meta.pipeline`; the existing CMS progress bar has not been redesigned to display it.

The normal queue launcher waits until completion/failure, preserving sequential queue behavior. Managed browser stages are serialized even when the old parallel launcher is used.

## Verification

```sh
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover retry persistence, completed-output reuse, missing/duplicate IDs, truncated MP4s, stalled workers, ongoing progress, explicit Stop, occupied execution lease, retry delays, and an actual harmless subprocess completing through the wrapper. No paid image/video/audio generation was run during this change.
