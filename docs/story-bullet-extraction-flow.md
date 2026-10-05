# Story Bullet Extraction — Flow Diagram

How the CMS creates bullet pointers from a story (transcript → LLM extract → ledger → optional full script).

---

## High-level flow

```mermaid
flowchart TD
    A[Drupal Story Node] --> B{User action}
    B -->|Prepare bullets from transcript| C[Job: generate_pointers]
    B -->|Write story from YouTube| D[Job: generate]
    B -->|Full pipeline| E[Job: full_pipeline]

    C --> F[WorkerLauncher]
    D --> F
    E --> F

    F --> G["run.sh generate --pointers-only<br/>or run.sh generate"]
    G --> H[run_generate_story.py]

    H --> I{Transcript source}
    I -->|field_transcript pasted| J[uploaded_transcript.txt]
    I -->|Existing on disk| K[Resume transcript]
    I -->|Channel research enabled| L[COMBINED_RESEARCH.txt]
    I -->|YouTube URLs| M[Fetch transcripts per URL]

    J --> N[combined_transcript.txt saved]
    K --> N
    L --> N
    M --> N

    N --> O{STORY_SOURCE_MODE<br/>default: bullets}
    O -->|bullets or --pointers-only| P[extract_bullet_ledger]
    O -->|transcript| Q[Skip extract — use raw transcript]

    P --> R[Split by source<br/>=== YouTube ID ===]
    R --> S[For each source: DeepSeek LLM]
    S --> T[Prompt: extract_bullets_and_flow.txt]
    T --> U[Parse 20–25 POINTER blocks<br/>Explains + How]
    U --> V[Build BULLET_LEDGER.txt]
    V --> W[Save source_bullets.json<br/>+ bullet_extract_raw/]

    W --> X{Run mode}
    X -->|--pointers-only| Y[POST Drupal: research_done]
    X -->|full generate| Z[Master story prompt<br/>ledger as sole source]

    Y --> AA[field_bullet_ledger updated]
    Z --> AB[FULL_STORY.txt generated]
    AB --> AC[POST Drupal: story_generated]

    Q --> Z
```

---

## CMS → Worker trigger

```mermaid
sequenceDiagram
    participant User
    participant Drupal as Drupal Story Node
    participant WL as WorkerLauncher
    participant Worker as story-pipeline-worker
    participant API as Drupal API

    User->>Drupal: Run pipeline job
    Drupal->>WL: launch(node, job)

    alt generate_pointers
        WL->>Worker: ./run.sh generate {nid} --pointers-only
        Note over WL: Syncs field_transcript if pasted
    else generate / full_pipeline
        WL->>Worker: ./run.sh generate {nid}
    end

    Worker->>API: GET story bundle (URLs, transcript, prompts)
    Worker->>Worker: Fetch / load transcripts
    Worker->>Worker: extract_bullet_ledger()
    Worker->>Worker: Save script/BULLET_LEDGER.txt

    alt pointers-only
        Worker->>API: POST update (status=research_done, story_plan_raw=ledger)
        API->>Drupal: field_bullet_ledger = ledger text
    else full generate
        Worker->>Worker: LLM write script from ledger
        Worker->>API: POST update (status=story_generated, full_story=...)
    end
```

---

## Per-source bullet extraction (bullet_ledger.py)

```mermaid
flowchart LR
    subgraph Input
        T[Combined transcript]
    end

    subgraph Split
        S1[Source 1: YouTube abc123]
        S2[Source 2: YouTube def456]
        SN[Source N ...]
    end

    subgraph LLM["DeepSeek (per source)"]
        P[extract_bullets_and_flow.txt]
        R[Raw POINTER output]
    end

    subgraph Parse
        PT[parse_extraction_output]
        PTR[pointers: title, explains, how]
        BUL[flat bullets: title | Explains | How]
    end

    subgraph Output
        LED[BULLET_LEDGER.txt]
        JSON[source_bullets.json]
        RAW[bullet_extract_raw/*.txt]
    end

    T --> S1 & S2 & SN
    S1 --> P --> R --> PT --> PTR --> BUL
    PTR --> LED
    BUL --> JSON
    R --> RAW
```

---

## Pointer format (what the LLM returns)

Each source yields **20–25 pointers** in this structure:

```
Story Topic: [one line]

Total Pointers: [20–25]

### POINTER 01 — [SHORT TITLE]

**Explains:**
Why this beat matters in the story.

**How:**
What happened — names, dates, places, numbers from transcript.

### POINTER 02 — ...
```

Parsed into JSON (`source_bullets.json`):

```json
{
  "source_id": "XmGO4O2vpJw",
  "source_title": "YouTube XmGO4O2vpJw",
  "story_topic": "...",
  "pointers": [
    {
      "number": 1,
      "title": "INDIA WAS ENSLAVED BY A PRIVATE COMPANY",
      "explains": "...",
      "how": "..."
    }
  ],
  "pointer_count": 25,
  "bullets": ["title | Explains: ... | How: ..."],
  "story_flow": ["title1", "title2", "..."]
}
```

---

## Quality gates

```mermaid
flowchart TD
    A[LLM response per source] --> B{≥ 15 pointers?}
    B -->|No| C[Retry up to 3 attempts]
    C --> A
    B -->|Yes| D[Accept source]
    D --> E{≥ 75% sources usable?}
    E -->|No| F[Fail job — status failed]
    E -->|Yes| G[Ledger ready]
```

---

## File locations

| Artifact | Path |
|----------|------|
| Combined transcript | `{asset_root}/{type}/{slug}/script/combined_transcript.txt` |
| Channel research transcript | `.../script/COMBINED_RESEARCH.txt` |
| Pasted transcript | `.../script/uploaded_transcript.txt` |
| **Bullet ledger** | `.../script/BULLET_LEDGER.txt` |
| Structured bullets | `.../script/source_bullets.json` |
| Raw LLM extracts | `.../script/bullet_extract_raw/{source_id}.txt` |
| Full script (after generate) | `.../script/FULL_STORY.txt` |

Example: `cms-generate-stories/general/162-the-east-india-company-.../script/`

---

## Drupal fields

| Field | When populated |
|-------|----------------|
| `field_transcript` | User pastes transcript (input) |
| `field_bullet_ledger` | After `generate_pointers` → `research_done` |
| `field_full_story` | After `generate` → `story_generated` |
| `field_status` | `research_done` (bullets only) or `story_generated` |

---

## Environment toggles

| Variable | Default | Effect |
|----------|---------|--------|
| `STORY_SOURCE_MODE` | `bullets` | Use ledger for script generation |
| `STORY_SOURCE_MODE=transcript` | — | Skip ledger; pass raw transcript to master prompt |
| `STORY_BULLET_PROMPT_PATH` | — | Override extract prompt file |
| `STORY_ASSET_ROOT` | from Drupal config | Where `cms-generate-stories/` files are written |

---

## Key source files

| Component | File |
|-----------|------|
| CMS job launcher | `web/modules/custom/story_pipeline/src/Service/WorkerLauncher.php` |
| CMS field sync | `web/modules/custom/story_pipeline/src/Service/StoryPipelineManager.php` |
| Orchestration | `story-pipeline-worker/run_generate_story.py` |
| Bullet extraction | `story-pipeline-worker/bullet_ledger.py` |
| Extract prompt | `story-pipeline-worker/prompts/extract_bullets_and_flow.txt` |

---

## One-line summary

**Transcripts → split by YouTube source → DeepSeek extracts 20–25 story pointers each → merged into BULLET_LEDGER.txt → (optional) full script written from ledger only, not raw transcripts.**
