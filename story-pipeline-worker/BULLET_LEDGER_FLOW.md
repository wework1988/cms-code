# Story generate — pointer ledger flow

How `./run.sh generate <story_id>` works when `STORY_SOURCE_MODE=bullets` (default).

## High-level

```mermaid
flowchart TD
  A[Drupal story node<br/>YouTube URLs + duration + master prompt] --> B[Worker: run_generate_story.py]
  B --> C{Research mode?}
  C -->|channel_first| D[Channel research engine<br/>COMBINED_RESEARCH.txt]
  C -->|transcript_only| E[Fetch each YouTube transcript<br/>combined_transcript.txt]
  D --> F[Save combined research/transcript<br/>under story/script/]
  E --> F
  F --> G{STORY_SOURCE_MODE?}
  G -->|transcript legacy| H[Pass raw combined text<br/>into master prompt placeholder]
  G -->|bullets default| I[Pointer extract stage]
  I --> J[For EACH source video]
  J --> K[LLM: extract_bullets_and_flow.txt<br/>20–25 POINTER Explains/How]
  K --> L[Build BULLET_LEDGER.txt<br/>+ source_bullets.json]
  L --> M[Inject ledger into master prompt<br/>as COMBINED_RESEARCH — NO raw transcript]
  H --> N[LLM: generate full documentary script]
  M --> N
  N --> O[Parse FULL SCRIPT vs POST-WRITE meta]
  O --> P[Length expand / continue if usable Hindi script]
  P --> Q[Write FULL_STORY.txt + story_meta.txt]
  Q --> R[POST update to Drupal<br/>status story_generated]
```

## Pointer extract (detail)

Prompt source: `prompts/extract_bullets_and_flow.txt`  
(optional override via `STORY_BULLET_PROMPT_PATH`, e.g. the edited `cms-generate-stories/bullet promt` file)

```mermaid
flowchart LR
  subgraph Input
    CT[combined_transcript.txt<br/>or COMBINED_RESEARCH.txt]
  end

  CT --> S1[Split on headers<br/>=== YouTube id ===]

  S1 --> V1[Source 1]
  S1 --> V2[Source 2]
  S1 --> Vn[Source N]

  V1 --> E1[DeepSeek POINTER extract]
  V2 --> E2[DeepSeek POINTER extract]
  Vn --> En[DeepSeek POINTER extract]

  E1 --> L[BULLET_LEDGER.txt]
  E2 --> L
  En --> L

  L --> P[Master story prompt]
  P --> G[FULL SCRIPT generation]
```

## Per-source extraction output shape

```text
**Story Topic:** …
**Total Pointers:** 20–25

### POINTER 01 — SHORT TITLE

**Explains:**
…

**How:**
…

### POINTER 02 — …
…
```

## Artifacts on disk

```text
cms-generate-stories/{type}/{id}-{slug}/
  script/
    combined_transcript.txt   # raw transcripts (debug only)
    BULLET_LEDGER.txt         # sole research fed to master prompt
    source_bullets.json       # structured pointers
    bullet_extract_raw/       # raw DeepSeek extracts per source
    FULL_STORY.txt            # final narration only
    story_meta.txt            # post-write / validator meta
  prompts/
    story-builder-input.txt   # full prompt sent to LLM (includes ledger, not raw)
```

## Modes

| Mode | How to run | What master prompt receives |
|------|------------|-----------------------------|
| **bullets** (default) | `./run.sh generate 126` | `BULLET_LEDGER.txt` only (POINTER format) |
| **transcript** (legacy) | `./run.sh generate 126 --source-mode transcript` | Full combined raw transcripts |

Env overrides:
- `STORY_SOURCE_MODE=bullets|transcript`
- `STORY_BULLET_PROMPT_PATH=/path/to/bullet promt` (optional)

## Sequence (happy path)

```mermaid
sequenceDiagram
  participant CMS as Drupal
  participant W as Worker
  participant YT as YouTube transcripts
  participant DS as DeepSeek

  CMS->>W: GET bundle (URLs, master prompt, duration)
  W->>YT: Fetch transcripts for all node URLs
  W->>W: Save combined_transcript.txt
  loop Each source
    W->>DS: POINTER extract (20–25 Explains/How)
    DS-->>W: Structured pointers
  end
  W->>W: Write BULLET_LEDGER.txt
  W->>DS: Generate story (master prompt + ledger only)
  DS-->>W: FULL SCRIPT + POST-WRITE
  W->>W: Parse, strip meta, length guard (Hindi-only)
  W->>CMS: POST full_story + meta + status
```

## Safety (why #126 broke before)

- Length expansion already refused stubs under 25% of target.
- Length-guard continuation now also refuses:
  - stubs under 25% of target
  - bodies that are not usable Hindi narration (English planning/meta)
- Jobs with a bad first pass should fail length guard instead of appending junk.
