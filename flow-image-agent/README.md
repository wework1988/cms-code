# CMS Flow Image Agent

Generate Google Flow images for any CMS story folder and save them as `images/001.jpg` (or `.png` / `.webp`).

## Architecture choice

**Chrome extension + loopback Python helper** (no Drupal filesystem API).

- Flow requires your signed-in Chrome session and native clicks (`chrome.debugger`).
- Chrome cannot write into arbitrary CMS paths; the helper receives the completed download path and places files under configured story roots.
- Story layout already used by playright: `<story>/images/001.png` (etc.). This agent writes the same folder with the real decoded format extension.
- Pairing token + loopback bind + path sandbox keep the helper local-only.

## CMS Build storyboard integration

When you click **Build storyboard (+ Flow images)** in Drupal, the worker:

1. Finishes Stages A–C and writes `image-prompts/image-prompts-only.txt`
2. Calls this agent with `--all` to generate **every** scene image sequentially
3. Saves into `<story>/images/001.jpg`, `002.jpg`, …

Requirements on the worker Mac:

- Chrome signed into Google Flow (Chrome-FlowAgent profile / debug port — see below)
- `flow-image-agent` next to `story-pipeline-worker` (this folder)
- Optional escape hatch: `FLOW_IMAGES=0` in the worker `.env` skips image generation
- Soft-fail: if Flow errors mid-run, storyboard text still marks complete; re-run `--all` to resume

## One-command run (manual)

```bash
cd /Users/alokkumarverma/project/cms-code/flow-image-agent
# Smoke test (2 scenes)
./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
# All scenes (same as CMS storyboard hook)
./scripts/run_images.sh 164-how-captain-saved-video-done --all
```

That command:

1. Starts the local helper if needed  
2. Creates a job for the selected scenes  
3. Opens Chrome with your Flow login profile  
4. Configures Nano Banana 2.1 · Image · 16:9 · x1  
5. Generates, downloads **2K Upscaled**, saves into the story `images/` folder  

**Login:** Chrome blocks remote debugging on the default profile, so the runner clones your login into `~/Library/Application Support/Google/Chrome-FlowAgent` (one-time) and attaches via port 9222. It may quit/reopen Chrome once. To refresh cookies later:

```bash
CHROME_FLOW_REFRESH_LOGIN=1 ./scripts/start_chrome_debug.sh
```

The Flow project URL is saved to `.local/flow-project-url.txt` for later runs.

With `flow_accounts` configured, use a separate signed-in `profile_dir` for each Gmail. The runner checks Flow's account label against the configured email before saving the project URL or generating. Each account has its own saved project URL. A startup account change and quota rotation restart Chrome with the selected profile; an already open Chrome with the wrong Gmail stops with an identity error.

The default rotation threshold is 115. `.local/flow-account-state.json` counts confirmed new generations, including images whose download later fails; gallery reuse does not increment the counter. Quota errors mark that Gmail exhausted for the local tracking day, and rotation skips it. When every account is unavailable, the runner stops instead of cycling. Counters and exhaustion flags reset at UTC midnight, including during a running job. This is local tracking, not Flow's quota API: manual generations, older failed downloads, and Flow's actual reset schedule may differ. Run only one Flow image runner at a time; managed watchdog jobs share the Chrome lock, while direct `run_images.sh` invocations do not acquire it.

Or pass the project explicitly:

```bash
FLOW_PROJECT_URL='https://labs.google/fx/tools/flow/project/YOUR_ID' \
  ./scripts/run_images.sh 164-how-captain-saved-video-done --all
```

Other examples:

The CLI waits a random 10–30 seconds between scenes by default and logs each pause. Use `--delay N` to choose a fixed pause in seconds. Restart a running CLI process to load changes to this setting.

Generation failures (including timeouts and content rejections) can request up to two DeepSeek prompt revisions per scene, persisted in `images/prompt-revisions/`. Retries use the same scene number and pause between attempts. Exhausted or unavailable repair marks that scene failed and continues. Quota, unusual-activity, browser, settings, download, and save errors do not trigger prompt rewriting.

```bash
./scripts/run_images.sh 165-pakistan-army --from 1 --to 2
./scripts/run_images.sh 164-how-captain-saved-video-done --first-two --regenerate
```

## Manual extension UI (optional)

### 1. Install helper deps (once)

```bash
cd flow-image-agent
python3 -m pip install --target .python-libs -r requirements.txt
```

### 2. Start the helper

```bash
chmod +x scripts/run_helper.sh
./scripts/run_helper.sh
```

Creates `.local/pairing-token` (mode 0600). Do not put the token in URLs or commit it.

### 3. Load the Chrome extension

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select `flow-image-agent/extension`
4. Accept the **debugger** permission when prompted

### 4. Run a job

1. Open a signed-in [Google Flow](https://flow.google.com) **project** tab
2. Close DevTools / other debuggers on that tab
3. Click the extension icon
4. Paste the pairing token from `.local/pairing-token`
5. Select a story → Preview → Start (default test: first two scenes)

Progress and resume state live in:

`<story>/images/generation-manifest.json`

## Chrome permissions

| Permission | Why |
|---|---|
| `debugger` | Native mouse events (synthetic `click()` does not start Flow generation). **Must be required**, not optional ([Chrome docs](https://developer.chrome.com/docs/extensions/reference/api/debugger)). |
| `downloads` | Correlate and confirm the 2K Upscaled download (id + path), not “newest file in Downloads”. |
| `scripting` / `activeTab` | Inject the Flow runner into the open project tab. |
| `storage` | Remember helper URL + token locally in Chrome. |
| Host `http://127.0.0.1/*` | Talk to the local helper only. |
| Host Flow domains | Operate on Flow UI. |

## Configuration

Copy `config.example.json` → `config.json` (a repo default is already present). Example without secrets:

```json
{
  "host": "127.0.0.1",
  "port": 8765,
  "story_roots": [
    "../general",
    "../crime",
    "../cms-generate-stories/general",
    "../cms-generate-stories/crime"
  ],
  "model": "Nano Banana 2.1",
  "aspect_ratio": "16:9",
  "outputs_per_prompt": 1,
  "download_variant": "2K Upscaled",
  "min_landscape_width": 2048,
  "aspect_tolerance": 0.08,
  "token_file": ".local/pairing-token",
  "state_dir": ".local/state"
}
```

Override path with `FLOW_IMAGE_AGENT_CONFIG`.

## Another story

1. Ensure `<category>/<id>-<slug>/image-prompts/image-prompts-only.txt` exists under a configured root
2. Refresh stories in the extension
3. Choose scene range (or first two)
4. Start on an open Flow project

Output: `<story>/images/NNN.jpg` (or png/webp). Existing valid files are skipped unless **Regenerate** is checked.

## Tests

```bash
cd flow-image-agent
PYTHONPATH=".python-libs:." python3 -m pytest -q
```

## Offline acceptance seed (no new Flow credits)

If 2K downloads for scenes 1–2 already exist in `~/Downloads`:

```bash
PYTHONPATH=".python-libs:." python3 scripts/seed_acceptance_from_downloads.py
```

## Limits (honest)

- Flow DOM selectors can break when Google changes UI.
- Another debugger/DevTools session on the same tab conflicts with native clicks.
- Stop cannot cancel an in-flight Google generation.
- Gallery/result matching uses new `flow-image-tile` / batch controls; virtualized galleries can confuse detection — uncertain cases pause as `needs_review`.
- Live end-to-end generation still requires your signed-in Flow tab and credits.
- This agent does not call private Google APIs or handle passwords/CAPTCHAs.
