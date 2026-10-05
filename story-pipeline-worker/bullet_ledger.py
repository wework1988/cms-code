"""Extract per-source story pointers, then build a ledger for generation.

Flow (STORY_SOURCE_MODE=bullets, default):
  Drupal YouTube URLs → download transcripts → DeepSeek POINTER extract (20–25/source)
  → BULLET_LEDGER.txt → master story prompt → FULL SCRIPT

Generation uses the ledger only — raw transcripts are not passed to the master prompt.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from asset_store import mirror_story_folder

LogFn = Callable[[str], None]

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
EXTRACT_PROMPT_PATH = PROMPTS_DIR / "extract_bullets_and_flow.txt"

# Optional override: path to the human-edited bullet prompt file.
_BULLET_PROMPT_ENV = "STORY_BULLET_PROMPT_PATH"

_SOURCE_HEADER_RE = re.compile(
    r"(?m)^===\s*(?:YouTube\s+(\S+)|SOURCE\s+(\d+)\s*:\s*(.+?))\s*===\s*$"
)

_POINTER_RE = re.compile(
    r"(?im)^###\s*POINTER\s+(\d+)\s*[—–\-]\s*(.+?)\s*$"
)
_EXPLAINS_RE = re.compile(r"(?im)^\*{0,2}\s*Explains\s*:?\*{0,2}\s*$")
_HOW_RE = re.compile(r"(?im)^\*{0,2}\s*How\s*:?\*{0,2}\s*$")
_TOPIC_RE = re.compile(r"(?im)^\*{0,2}\s*Story\s+Topic\s*:?\*{0,2}\s*(.+)$")
_TOTAL_RE = re.compile(r"(?im)^\*{0,2}\s*Total\s+Pointers\s*:?\*{0,2}\s*(\d+)")

# Minimum usable extract — below this we retry / fail the job.
MIN_POINTERS_PER_SOURCE = 15
MIN_SOURCES_WITH_POINTERS_RATIO = 0.75
# Back-compat aliases used by older call sites / docs.
MIN_BULLETS_PER_SOURCE = MIN_POINTERS_PER_SOURCE
MIN_FLOW_BEATS = 0


def source_mode() -> str:
    """bullets (default) | transcript — how generate feeds the master prompt."""
    raw = (os.environ.get("STORY_SOURCE_MODE") or "bullets").strip().lower()
    if raw in ("transcript", "raw", "full", "legacy"):
        return "transcript"
    return "bullets"


def load_extract_prompt_template() -> str:
    override = (os.environ.get(_BULLET_PROMPT_ENV) or "").strip()
    if override:
        path = Path(override).expanduser()
        if path.is_file():
            return path.read_text(encoding="utf-8")
    if EXTRACT_PROMPT_PATH.is_file():
        return EXTRACT_PROMPT_PATH.read_text(encoding="utf-8")
    return (
        "Extract 20 to 25 story pointers from the transcript.\n"
        "SOURCE_ID: {source_id}\nSOURCE_TITLE: {source_title}\n\n"
        "## TRANSCRIPT\n\n{transcript}\n"
    )


def split_transcript_sources(combined: str) -> list[dict]:
    """Split combined_transcript / COMBINED_RESEARCH into per-source blocks."""
    text = (combined or "").strip()
    if not text:
        return []

    matches = list(_SOURCE_HEADER_RE.finditer(text))
    if not matches:
        return [
            {
                "source_id": "SOURCE_1",
                "source_title": "Combined transcript",
                "body": text,
            }
        ]

    sources: list[dict] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        yt_id = (match.group(1) or "").strip()
        src_num = (match.group(2) or "").strip()
        src_title = (match.group(3) or "").strip()
        if yt_id:
            source_id = yt_id
            title = f"YouTube {yt_id}"
        else:
            source_id = f"SOURCE_{src_num or (i + 1)}"
            title = src_title or source_id
        if not body:
            continue
        sources.append(
            {
                "source_id": source_id,
                "source_title": title,
                "body": body,
            }
        )
    return sources


def _truncate(text: str, max_chars: int = 90000) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n\n[…truncated for extraction…]"


def _strip_noise(raw: str) -> str:
    """Drop thinking fences / preamble before the structured extract."""
    text = (raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"(?is)<think>.*?</think>", "", text)
    text = re.sub(r"(?is)<thinking>.*?</thinking>", "", text)
    for pat in (
        r"(?im)^\*{0,2}\s*Story\s+Topic\s*:",
        r"(?im)^###\s*POINTER\s+\d+",
        r"(?im)^\*{0,2}\s*Total\s+Pointers\s*:",
    ):
        m = re.search(pat, text)
        if m:
            return text[m.start() :].strip()
    return text


def _pointer_to_bullet(pointer: dict) -> str:
    title = (pointer.get("title") or "").strip()
    explains = (pointer.get("explains") or "").strip()
    how = (pointer.get("how") or "").strip()
    parts = []
    if title:
        parts.append(title)
    if explains:
        parts.append(f"Explains: {explains}")
    if how:
        parts.append(f"How: {how}")
    return " | ".join(parts) if parts else ""


def parse_extraction_output(raw: str, *, source_id: str, source_title: str) -> dict:
    """Parse POINTER 01…N output into structured pointers (+ flat bullets for ledger)."""
    text = _strip_noise(raw)
    topic = ""
    topic_m = _TOPIC_RE.search(text)
    if topic_m:
        topic = topic_m.group(1).strip().strip("*").strip()

    starts = list(_POINTER_RE.finditer(text))
    pointers: list[dict] = []
    for i, match in enumerate(starts):
        block_end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        block = text[match.end() : block_end]
        title = match.group(2).strip()
        explains = ""
        how = ""

        explains_m = _EXPLAINS_RE.search(block)
        how_m = _HOW_RE.search(block)
        if explains_m and how_m and how_m.start() > explains_m.end():
            explains = block[explains_m.end() : how_m.start()].strip()
            how = block[how_m.end() :].strip()
        elif explains_m:
            explains = block[explains_m.end() :].strip()
        elif how_m:
            how = block[how_m.end() :].strip()
        else:
            # Fallback: whole block as How if model skipped labels.
            how = block.strip()

        explains = re.sub(r"\n{3,}", "\n\n", explains).strip()
        how = re.sub(r"\n{3,}", "\n\n", how).strip()
        if not title and not explains and not how:
            continue
        pointers.append(
            {
                "number": int(match.group(1)),
                "title": title,
                "explains": explains,
                "how": how,
            }
        )

    # Cap at 25 as per prompt.
    pointers = pointers[:25]
    bullets = [b for b in (_pointer_to_bullet(p) for p in pointers) if b]

    return {
        "source_id": source_id,
        "source_title": source_title,
        "story_topic": topic,
        "pointers": pointers,
        "bullets": bullets,
        "story_flow": [p.get("title") or f"Pointer {p.get('number')}" for p in pointers],
        "raw": (raw or "").strip(),
    }


def format_source_block(entry: dict) -> str:
    lines = [
        f"═══ SOURCE: {entry.get('source_id')} — {entry.get('source_title')} ═══",
        "",
    ]
    topic = (entry.get("story_topic") or "").strip()
    if topic:
        lines.append(f"Story Topic: {topic}")
        lines.append("")
    pointers = entry.get("pointers") or []
    lines.append(f"POINTERS ({len(pointers)}):")
    lines.append("")
    if not pointers:
        lines.append("(none extracted)")
        lines.append("")
        return "\n".join(lines)

    for p in pointers:
        num = int(p.get("number") or 0)
        title = (p.get("title") or "").strip() or f"Pointer {num}"
        lines.append(f"### POINTER {num:02d} — {title}")
        lines.append("")
        lines.append("**Explains:**")
        lines.append((p.get("explains") or "").strip() or "(missing)")
        lines.append("")
        lines.append("**How:**")
        lines.append((p.get("how") or "").strip() or "(missing)")
        lines.append("")
    return "\n".join(lines)


def build_bullet_ledger_text(entries: list[dict], *, topic: str = "") -> str:
    header = [
        "══════════════════════════════════════════════════════════════════",
        "STORY POINTER LEDGER — SOLE FACTUAL SOURCE (NO RAW TRANSCRIPTS)",
        "══════════════════════════════════════════════════════════════════",
        "Use ONLY the story pointers below as research input.",
        "Do NOT invent details that are not listed. Do NOT request transcripts.",
        "Treat this block as COMBINED_RESEARCH / SOURCE TRANSCRIPTS for the master prompt.",
        "",
    ]
    if topic.strip():
        header.append(f"TOPIC: {topic.strip()}")
        header.append("")
    header.append(f"SOURCES IN LEDGER: {len(entries)}")
    header.append("")
    header.append("── PER-SOURCE STORY POINTERS ──")
    header.append("")
    body = "\n".join(format_source_block(e) for e in entries)
    return "\n".join(header) + body


def _fill_prompt_template(template: str, *, source_id: str, source_title: str, transcript: str) -> str:
    """Fill placeholders. Support both {transcript} and [PASTE TRANSCRIPT HERE]."""
    text = template
    text = text.replace("{source_id}", source_id)
    text = text.replace("{source_title}", source_title)
    text = text.replace("{transcript}", transcript)
    text = text.replace("[PASTE TRANSCRIPT HERE]", transcript)
    # If template has no transcript slot, append it.
    if transcript and transcript not in text:
        text = text.rstrip() + "\n\n## TRANSCRIPT\n\n" + transcript + "\n"
    return text


def _call_extract(
    *,
    call_llm: Callable[..., tuple[str, str | None]],
    api_key: str,
    model: str,
    system: str,
    user: str,
    request_timeout_s: int,
    deadline_ts: float | None,
    attempt: int,
) -> str:
    """Highest-quality extract: thinking ON (max). Parser/retry handle empty content."""
    max_tokens = 16384
    timeout_s = min(1800, max(300, request_timeout_s))
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "request_timeout_s": timeout_s,
        "retries": 4,
        "deadline_ts": deadline_ts,
        "best_quality": True,
    }
    try:
        raw, _finish = call_llm(api_key, system, user, **kwargs)
    except TypeError:
        raw, _finish = call_llm(
            api_key,
            system,
            user,
            model=model,
            max_tokens=max_tokens,
            request_timeout_s=timeout_s,
            retries=4,
            deadline_ts=deadline_ts,
        )
    return (raw or "").strip()


def extract_one_source(
    *,
    src: dict,
    template: str,
    api_key: str,
    model: str,
    call_llm: Callable[..., tuple[str, str | None]],
    log: LogFn,
    deadline_ts: float | None,
    request_timeout_s: int,
) -> dict:
    sid = src["source_id"]
    title = src["source_title"]
    body = _truncate(src["body"])
    system = (
        "You extract 20–25 detailed story pointers from one transcript for a documentary writer. "
        "Think carefully for accuracy, then output ONLY Story Topic, Total Pointers, and POINTER blocks "
        "in the required format. No markdown fences. No documentary script. No titles/thumbnails/hooks/CTAs."
    )
    base_user = _fill_prompt_template(
        template, source_id=sid, source_title=title, transcript=body
    )

    entry: dict | None = None
    for attempt in range(1, 4):
        user = base_user
        if attempt > 1:
            user = (
                "RETRY: Previous answer was empty or incomplete.\n"
                "Return EXACTLY the required format: Story Topic, Total Pointers, then "
                "### POINTER 01 … through at least 20 pointers with **Explains:** and **How:**.\n"
                "No other text before Story Topic.\n\n"
                + base_user
            )
        raw = _call_extract(
            call_llm=call_llm,
            api_key=api_key,
            model=model,
            system=system,
            user=user,
            request_timeout_s=request_timeout_s,
            deadline_ts=deadline_ts,
            attempt=attempt,
        )
        entry = parse_extraction_output(raw, source_id=sid, source_title=title)
        n_p = len(entry.get("pointers") or [])
        log(
            f"[pointers] id={sid} attempt={attempt}/3 "
            f"raw_chars={len(raw):,} pointers={n_p}"
        )
        if n_p >= MIN_POINTERS_PER_SOURCE:
            return entry

    assert entry is not None
    return entry


def _entry_from_saved(item: dict) -> dict:
    return {
        "source_id": item.get("source_id"),
        "source_title": item.get("source_title"),
        "story_topic": item.get("story_topic") or "",
        "pointers": item.get("pointers") or [],
        "bullets": item.get("bullets") or [],
        "story_flow": item.get("story_flow") or [],
        "raw": "",
    }


def load_saved_pointer_entries(slug_folder: Path | None) -> dict[str, dict]:
    """Load per-source pointer extracts saved from a prior partial run."""
    if slug_folder is None:
        return {}
    path = slug_folder / "script" / "source_bullets.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, list):
        return {}
    saved: dict[str, dict] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("source_id") or "").strip()
        if not sid:
            continue
        count = int(item.get("pointer_count") or len(item.get("pointers") or []))
        if count >= MIN_POINTERS_PER_SOURCE:
            saved[sid] = _entry_from_saved(item)
    return saved


def assert_ledger_usable(entries: list[dict]) -> None:
    if not entries:
        raise RuntimeError("Pointer extract failed: no sources.")
    ok = sum(
        1
        for e in entries
        if len(e.get("pointers") or e.get("bullets") or []) >= MIN_POINTERS_PER_SOURCE
    )
    ratio = ok / len(entries)
    if ratio < MIN_SOURCES_WITH_POINTERS_RATIO:
        detail = ", ".join(
            f"{e.get('source_id')}={len(e.get('pointers') or e.get('bullets') or [])}"
            for e in entries
        )
        raise RuntimeError(
            f"Pointer extract too weak ({ok}/{len(entries)} sources usable). "
            f"Per-source pointer counts: {detail}. "
            "Refusing to generate from an empty/missing ledger."
        )


def extract_bullet_ledger(
    *,
    combined_transcripts: str,
    api_key: str,
    model: str,
    call_llm: Callable[..., tuple[str, str | None]],
    log: LogFn,
    topic: str = "",
    deadline_ts: float | None = None,
    request_timeout_s: int = 600,
    slug_folder: Path | None = None,
) -> tuple[str, list[dict]]:
    """
    For each source in the combined file, extract 20–25 story pointers via LLM.
    Returns (ledger_text, structured_entries).
    """
    sources = split_transcript_sources(combined_transcripts)
    if not sources:
        raise RuntimeError("No transcript sources found to extract pointers from.")

    template = load_extract_prompt_template()
    saved_entries = load_saved_pointer_entries(slug_folder)
    entries: list[dict] = []
    log(f"[pointers] extracting from {len(sources)} source(s) (thinking=on, quality=max)")

    for idx, src in enumerate(sources, 1):
        sid = src["source_id"]
        if sid in saved_entries:
            entry = saved_entries[sid]
            n_p = len(entry.get("pointers") or [])
            log(
                f"[pointers] source {idx}/{len(sources)} "
                f"id={sid} skip=resume pointers={n_p}"
            )
            entries.append(entry)
            continue

        log(
            f"[pointers] source {idx}/{len(sources)} "
            f"id={sid} chars={len(src['body']):,}"
        )
        entry = extract_one_source(
            src=src,
            template=template,
            api_key=api_key,
            model=model,
            call_llm=call_llm,
            log=log,
            deadline_ts=deadline_ts,
            request_timeout_s=request_timeout_s,
        )
        entries.append(entry)
        if slug_folder is not None:
            ledger = build_bullet_ledger_text(entries, topic=topic)
            save_bullet_artifacts(slug_folder, ledger, entries)

    ledger = build_bullet_ledger_text(entries, topic=topic)
    return ledger, entries


def save_bullet_artifacts(slug_folder: Path | None, ledger: str, entries: list[dict]) -> None:
    if slug_folder is None:
        return
    script_dir = slug_folder / "script"
    raw_dir = script_dir / "bullet_extract_raw"
    script_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    (script_dir / "BULLET_LEDGER.txt").write_text(ledger.rstrip() + "\n", encoding="utf-8")
    serializable = []
    for e in entries:
        sid = str(e.get("source_id") or "source")
        raw = (e.get("raw") or "").strip()
        if raw:
            safe = re.sub(r"[^\w.\-]+", "_", sid)[:80]
            (raw_dir / f"{safe}.txt").write_text(raw + "\n", encoding="utf-8")
        pointers = e.get("pointers") or []
        serializable.append(
            {
                "source_id": e.get("source_id"),
                "source_title": e.get("source_title"),
                "story_topic": e.get("story_topic") or "",
                "pointers": pointers,
                "pointer_count": len(pointers),
                # Flat bullets kept for debugging / older tooling.
                "bullets": e.get("bullets") or [],
                "bullet_count": len(e.get("bullets") or []),
                "story_flow": e.get("story_flow") or [],
                "flow_count": len(e.get("story_flow") or []),
            }
        )
    (script_dir / "source_bullets.json").write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    mirror_story_folder(slug_folder)
