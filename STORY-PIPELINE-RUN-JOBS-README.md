# Story Pipeline — Run & Stop Jobs (non-technical guide)

How to start, monitor, and stop story jobs **from the Drupal website** — no Terminal required.

---

## Before you start

1. **MAMP must be running** (Apache + MySQL).
2. **Log in** to Drupal as a user with permission **Run Story Pipeline jobs**.
3. Open the site: `http://localhost:8888/myresearch2/web`

---

## Main page — Run story jobs

**Menu:** Content → **Run story jobs**

Direct link:

```
http://localhost:8888/myresearch2/web/admin/content/story-pipeline/run
```

This page lists all stories and lets you **start** or **stop** background jobs.

---

## What each button does

| Button | When to use |
|--------|-------------|
| **Write story from YouTube** | Story has YouTube URLs but no script yet |
| **Build storyboard** | Full script is saved — creates scenes + image prompts (~10–20 min) |
| **Build storyboard + narration audio** | Storyboard + ElevenLabs MP3s in one job |
| **Full pipeline (all steps + audio)** | YouTube → script → storyboard → MP3s in one job (best for bulk) |
| **Create narration audio only** | Storyboard already done — MP3s from script only |
| **Stop job** | Appears while a job is running — cancels the background process |

---

## Typical workflow

### A — You already have a script

1. **Content → Add content → Story** — paste script in **Full story**, pick **Story type** (Crime / General / English), Save.
2. Go to **Content → Run story jobs**.
3. Click **Build storyboard** (or **+ narration audio** if you want MP3s too).
4. Message: *“Job started…”* — **you can close the browser tab**; work continues on the server/Mac.
5. Refresh the Run jobs page every few minutes.
6. When **Status** = **Complete**, download files from **Outputs** (Prompts, Scenes, Image prompts, Audio).

### B — Start from YouTube

1. Create Story with **YouTube URLs** (no script yet).
2. **Run story jobs** → **Write story from YouTube**.
3. When status shows script ready → **Build storyboard**.

### C — Run several stories at once (bulk)

Use this when you want **every step including audio** on multiple stories without clicking each row.

1. Go to **Content → Run story jobs**.
2. Tick the **Select** checkbox on each story (or use **Select all on page** in the bulk box).
3. Click **Run full pipeline on selected (all steps + audio)**.
   - For each story: if it only has YouTube URLs, the worker writes the script first, then storyboard, then ElevenLabs MP3s.
   - If the script is already saved, it skips YouTube and runs storyboard + audio.
4. Each selected story starts its **own** background job (they can run in parallel). Progress bars update automatically.
5. When all show **Complete**, download **Outputs** for each story.

Other bulk buttons:

| Bulk button | Effect |
|-------------|--------|
| **Run storyboard + audio on selected** | Storyboard + MP3s (needs script already) |
| **Run storyboard only on selected** | Scenes + image prompts only |
| **Stop selected jobs** | Stops running jobs for ticked stories |

**Tip:** Running many stories at once uses more API quota and CPU. Your Mac should stay on until jobs finish.

---

## How to see if a job is running

On **Run story jobs**:

| Column | Meaning |
|--------|---------|
| **Progress** | Bar + **10%**, **45%**, etc. — updates every ~8 seconds automatically |
| **Status** | Short text: running / complete / stopped / failed |
| **Job log** | **View log** — full terminal output |
| **Outputs** | Download links when finished |

**Progress bar colours:**
- **Blue** — job running
- **Green** — complete (100%)
- **Red** — error (read the message under the bar)
- **Orange** — stopped by user

You can also open the story: **Content → edit the story** → check **Status** field.

---

## How to stop a job

1. Go to **Content → Run story jobs**.
2. Find the story with status **Job running…**
3. Click the red **Stop job** button.
4. Status changes to **Stopped**. You can start a new job when ready.

**Note:** Stop ends the background worker on your Mac. It does not undo files already uploaded to Drupal.

---

## How jobs actually run (simple explanation)

```
You click a button in Drupal
        ↓
Drupal starts a background script on your Mac (story-pipeline-worker)
        ↓
Python reads the story from Drupal, calls AI (DeepSeek / ElevenLabs)
        ↓
Python uploads results back to Drupal
        ↓
You refresh Run story jobs → see Complete + download links
```

The browser **does not** run AI — it only starts and monitors jobs.

**Requirements:**

- MAMP running
- Mac stays on during the job
- API keys set in **Configuration → Story Pipeline** (admin)

---

## Settings (admin only)

**Configuration → Story Pipeline**

| Setting | Purpose |
|---------|---------|
| **Drupal API key** | Worker authentication (also in worker `.env`) |
| **Worker folder path** | Usually `/Applications/MAMP/htdocs/story-pipeline-worker` |
| **Pipeline API keys** | DeepSeek, Anthropic, ElevenLabs — used for all story types |

Import keys from automation repo `.env`:

```bash
cd /Applications/MAMP/htdocs/myresearch2
export PATH="/Applications/MAMP/Library/bin/mysql80/bin:$PATH"
vendor/bin/drush story-pipeline:import-keys
vendor/bin/drush story-pipeline:info
```

---

## Log files (if View log is missing)

Folder on disk:

```
web/sites/default/files/story-pipeline/logs/
```

Example URL:

```
http://localhost:8888/myresearch2/web/sites/default/files/story-pipeline/logs/story-1-storyboard-20260609-120000.log
```

---

## Permissions

| Permission | Who needs it |
|------------|----------------|
| **Run Story Pipeline jobs** | Staff who start/stop jobs from the UI |
| **Administer Story Pipeline** | Admins — API keys, worker path |

Set at: **People → Permissions** (`/admin/people/permissions`)

---

## Troubleshooting

| Problem | What to do |
|---------|------------|
| Status stuck on **Job running…** | Click **Stop job**, then start again; open **View log** |
| **Could not start job** | Admin: check **Worker folder path** in settings |
| No MP3s | Run **Create narration audio only**; check ElevenLabs key in settings |
| Job fails immediately | Open log; admin can test manually: `cd story-pipeline-worker && ./run.sh storyboard 1` |

---

## Related docs

- Full user guide: `STORY-PIPELINE-USER-GUIDE.md`
- Worker (technical): `/Applications/MAMP/htdocs/story-pipeline-worker/README.md`
- Module API: `web/modules/custom/story_pipeline/README.md`
