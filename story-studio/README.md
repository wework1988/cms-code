# Story Studio

Local-first web app for turning 1–5 trusted source transcripts into an **original Hindi documentary narration script**. For each source you can paste a transcript, fetch public YouTube captions from a video URL, or both. Fetching a transcript does not generate a story. Official YouTube OAuth remains available only for videos you own or manage.

Story Studio is intentionally **source-only**: it does not run external fact-checking or web research. It extracts neutral facts, merges them, plans a new narrative structure, writes Hindi narration, and runs an **editorial originality check** (not legal clearance).

## Requirements

- Node.js **18+** (Node 20+ recommended)
- npm
- Python 3, only if you want public YouTube caption fetch. Manual paste works without it.

## Setup

```bash
cd story-studio
cp .env.example .env
npm install
python3 -m pip install -r scripts/requirements-transcript.txt
npx prisma migrate dev
npm run db:seed
```

After pulling updates with schema changes:

```bash
npx prisma migrate dev
```

### LLM provider

Configure either DeepSeek (default) or OpenAI in `.env`:

```env
# DeepSeek (default)
LLM_PROVIDER="deepseek"
DEEPSEEK_API_KEY="your-key"
DEEPSEEK_MODEL="deepseek-v4-pro"
DEEPSEEK_DEEP_THINKING="true"
DEEPSEEK_REASONING_EFFORT="high"
# Per-section ceiling for long-form Hindi narration; keeps room for visible prose after reasoning.
LLM_NARRATION_MAX_TOKENS="65536"

# OpenAI
LLM_PROVIDER="openai"
OPENAI_API_KEY="your-key"
OPENAI_MODEL="gpt-4o-mini"
```

If no API key is set, the dashboard shows a setup banner and the **Demo project** still loads fixture data without calling an LLM.

### Transcripts

Each source can have a YouTube URL, a pasted transcript, or both. Fetching is explicit: it does not run when you type, when the page loads, or when you prepare fact bullets.

1. **Paste a transcript** and save it. This always works, including when Python or YouTube is unavailable.
2. **Fetch transcript** on a YouTube URL. Story Studio asks the maintained `youtube-transcript-api` Python library for public captions, prefers human captions in Hindi or English, then automatic captions in that same language, and will not silently switch languages or translate.
3. For **videos you own or manage**, connect YouTube OAuth at `/settings/youtube` and use **Fetch official captions**. OAuth is not a way to download captions from arbitrary videos.

A blocked or failed fetch leaves the URL and any saved transcript in place and keeps the paste box available. Replacing an existing transcript requires confirmation. Successful fetches are cached by video, language, and caption type. Requests run one at a time.

Public fetch can be rate-limited or blocked by YouTube. There is no guaranteed bypass. Optional proxy settings in `.env` are off by default. A rotating residential proxy is a paid third-party service, does not guarantee success, and is never purchased automatically. Proxy credentials stay on the server.

Generation and fact preparation stay blocked until every source has a saved transcript.

### YouTube OAuth (owned videos only)

```env
GOOGLE_CLIENT_ID="your-google-oauth-client-id"
GOOGLE_CLIENT_SECRET="your-google-oauth-client-secret"
GOOGLE_OAUTH_REDIRECT_URI="http://localhost:3000/api/youtube/oauth/callback"
```

Enable the **YouTube Data API v3** in Google Cloud Console. OAuth is used only for the official `captions.list` / `captions.download` endpoints — never for arbitrary third-party videos.

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Tests & build

```bash
npm test
npm run lint
npm run build
npm start
```

Integration tests use `prisma/test.db` (auto-created via `prisma db push` during test setup).

## Main flow

1. **Dashboard** — create a project or open the demo
2. **New story wizard** — topic, Hindi output, **prompt profile**, sources (YouTube URL, pasted transcript, or both)
3. **Research workspace tabs**
   - Sources (fetch a YouTube transcript, paste or edit it, or fetch official captions for a video you own)
   - Fact Bank (editable, pinnable — preserved across merges)
   - Narrative Plan (select or edit treatments)
   - Script (save edits, version history, paragraph regeneration)
   - Originality QA (PASS / WARN / BLOCK workflow)
4. **Generate original story** — runs the full pipeline via `POST /api/projects/:id/generate-original-story`

### URL → transcript → fact pointers → Copy master prompt

1. Create a project with one or more YouTube URLs. You can also paste a transcript at the same time.
2. Open the project, choose Hindi or English, and click **Fetch transcript**. Use **Fetch missing transcripts** to walk the empty sources one at a time. This does not write a story.
3. Edit the transcript if needed and click **Save transcript**. If the fetch is blocked, paste the transcript into the same box.
4. Click **Generate fact bullets**. Review, edit, or disable bullets in **Fact Bank**.
5. Click **Copy master prompt** and paste it into your external writing model.

Changing a saved transcript clears claim pointers that came from the old text. Pinned or edited bullets that depended on it are disabled so they are not copied as current. Generate fact bullets again after a transcript change.

### Write externally in ChatGPT or Claude

1. Save all source transcripts and select your prompt profile in story settings.
2. Click **Generate fact bullets** in the header or **Fact Bank** tab. This runs source normalization, claim extraction, and fact merging only. It stops before narrative planning and script generation.
3. Review the extracted bullets in **Fact Bank**; edit or disable any you do not want to include.
4. Click **Copy master prompt** to copy your selected profile, saved project settings, and enabled bullets into ChatGPT or Claude.

Fact preparation uses the configured LLM provider. Copying the prompt makes no writing-model call. Existing fact bullets are reused; copying is unavailable until at least one non-empty bullet is enabled.

The exported reference bank removes exact repeated bullets (after whitespace cleanup) and uses a stable content-derived order independent of the source/input order. Saved facts are unchanged. The writing instructions ask the external model to regroup claims by subject privately, consider three distinct routes within the selected settings, and write from its own outline rather than expand the bullet sequence. They preserve factual chronology and discourage copying source framing or a named creator's signature devices. This reduces ordering cues; it is not source verification or copyright clearance. Review the resulting script against the original sources for unusually similar wording and distinctive storytelling structure before publishing. Existing projects can use the updated export simply by copying a fresh master prompt; no story regeneration is needed inside Story Studio.

## Originality workflow

- **PASS** — proceed to export
- **WARN** — targeted rewrite recommended (`POST .../originality/rewrite` with `action: "rewrite"`)
- **BLOCK** — export blocked; re-plan narrative structure first (`action: "replan"`). Override via `POST .../export/override` (does **not** constitute legal clearance)

BLOCK automatically triggers up to 2 re-plan loops during full pipeline generation.

## Prompt profiles

Manage profiles at `/settings/prompts` (create, edit, duplicate). Select a profile in the New Story wizard. Profile instructions are passed to the narrative planner and Hindi writer. Source-isolation and originality rules remain in a non-editable system layer.

## Pipeline stages

`draft → sources_ready → claims_ready → fact_pack_ready → narrative_plan_ready → script_generated → originality_review_ready → complete`

Each stage can also be rerun individually through `/api/projects/:id/stages/:stage`.

## Architecture notes

- **Next.js App Router + TypeScript**
- **Prisma + SQLite** locally (schema portable to PostgreSQL)
- **Zod** validates API payloads and LLM JSON
- **Server-side ID validation** — claim/fact IDs assigned and validated server-side; LLM-returned IDs are never trusted
- **LLM abstraction** supports OpenAI-compatible providers server-side only
- **Manual paste** always available, including when public caption fetch is not installed or YouTube blocks the request
- **Public YouTube captions** through a server-side `TranscriptProvider` and `scripts/fetch_public_captions.py` (`youtube-transcript-api`). Cached, queued, and never started automatically
- **Official YouTube OAuth captions** for owned/authorized videos only (`/settings/youtube`)
- **Transcript segments** persisted with timestamps during normalization
- **All-source originality** — plans and scripts compared against every source fingerprint (lexical + semantic + structural)
- **Writer isolation** — final Hindi writer never receives raw transcript prose or support excerpts
- Prompt templates live in `src/lib/prompts/`

## Deferred production integrations

- Multi-user auth
- Background job queue (pipeline interface is stage-based and ready to swap)
- Playwright smoke tests
- PostgreSQL deployment profile
