# CMS Flow Image Agent

Generate Google Flow images for any CMS story folder and save them as `images/001.jpg` (or `.png` / `.webp`).

## Architecture choice

**Chrome extension + loopback Python helper** (no Drupal filesystem API).

- Flow requires your signed-in Chrome session and native clicks (`chrome.debugger`).
- Chrome cannot write into arbitrary CMS paths; the helper receives the completed download path and places files under configured story roots.
- Story layout already used by playright: `<story>/images/001.png` (etc.). This agent writes the same folder with the real decoded format extension.
- Pairing token + loopback bind + path sandbox keep the helper local-only.

## One-command run (recommended)

```bash
cd /Users/alokkumarverma/project/cms-code/flow-image-agent
./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
```

That single command:

1. Starts the local helper if needed  
2. Creates a job for scenes 1–2  
3. Opens Chrome (dedicated profile under `.local/chrome-profile`)  
4. Configures Nano Banana 2.1 · Image · 16:9 · x1  
5. Generates, downloads **2K Upscaled**, saves into the story `images/` folder  

**Login:** Chrome blocks remote debugging on the default profile, so the runner clones your login into `~/Library/Application Support/Google/Chrome-FlowAgent` (one-time) and attaches via port 9222. It may quit/reopen Chrome once. To refresh cookies later:

```bash
CHROME_FLOW_REFRESH_LOGIN=1 ./scripts/start_chrome_debug.sh
```

The Flow project URL is saved to `.local/flow-project-url.txt` for later runs.

Or pass the project explicitly:

```bash
FLOW_PROJECT_URL='https://labs.google/fx/tools/flow/project/YOUR_ID' \
  ./scripts/run_images.sh 164-how-captain-saved-video-done --first-two
```

Other examples:

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
