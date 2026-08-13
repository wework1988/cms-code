#!/usr/bin/env python3
"""
Generate full_story from YouTube URLs using Drupal master prompt + LLM.

Uses api_keys from Drupal bundle (Anthropic or DeepSeek). Does not modify automation repo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import time
import sys
import urllib.request
import urllib.error

from pathlib import Path

from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi

from asset_store import mirror_story_folder, story_folder, sync_script
from bullet_ledger import (
    assert_ledger_usable,
    extract_bullet_ledger,
    save_bullet_artifacts,
    source_mode,
)
from drupal_client import DrupalStoryClient
from secrets import apply_asset_root_from_bundle, leased_deepseek_key, load_all_env, resolve_keys
from workspace import slugify, strip_html


def repo_root_from_bundle(bundle: dict | None) -> Path:
    raw = ((bundle or {}).get("automation_repo_path") or os.environ.get("AUTOMATION_REPO") or "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def setup_automation_paths(bundle: dict | None) -> Path:
    root = repo_root_from_bundle(bundle)
    for sub in (root, root / "documentary-engine", root / "library"):
        s = str(sub)
        if sub.is_dir() and s not in sys.path:
            sys.path.insert(0, s)
    return root


def use_channel_first_research(bundle: dict | None, master: str) -> bool:
    story = (bundle or {}).get("story") or {}
    if story.get("channel_first_research") is False:
        return False
    settings = (bundle or {}).get("settings") or {}
    mode = (settings.get("research_engine") or "channel_first").strip().lower()
    if mode in ("transcript_only", "legacy", "off", "false", "0"):
        return False
    return True


def run_channel_research(seed_url: str, research_dir: Path) -> tuple[str, dict]:
    from src.research_runner import run_research

    _, combined_text, meta = run_research(seed_url, research_dir)
    return combined_text, meta


def build_generation_prompt(
    master: str,
    source_text: str,
    *,
    duration: int,
    custom_instructions: str,
    title: str,
    story_type: str,
) -> tuple[str, str, bool]:
    from prompt_builder import build_cms_prompt, is_v3_prompt

    built = build_cms_prompt(
        master,
        source_text,
        duration,
        custom_instructions=custom_instructions,
        topic=title,
        story_type=story_type,
    )
    if is_v3_prompt(master):
        system = (
            "You are an expert Hindi documentary scriptwriter. "
            "Follow every instruction in the user message exactly. "
            "Output all required sections in order."
        )
        user = built + "\n\nBegin now. Execute STEP 0 through final output per the instructions above."
        return system, user, True
    system = (
        "You are an expert Hindi documentary scriptwriter. "
        "Follow every instruction in the user message exactly."
    )
    user = built + "\n\nWrite output exactly in the master prompt format."
    return system, user, False


def log(msg: str) -> None:
    print(msg, flush=True)


def now_monotonic() -> float:
    return time.monotonic()


def deadline_exceeded(deadline_ts: float | None) -> bool:
    return deadline_ts is not None and now_monotonic() >= deadline_ts


def assert_not_timed_out(deadline_ts: float | None, stage: str) -> None:
    if deadline_exceeded(deadline_ts):
        raise TimeoutError(f"Generation exceeded wall-clock limit during {stage}.")


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"^([A-Za-z0-9_-]{11})$",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None


def _extract_text_chunks(chunks: object) -> list[str]:
    if hasattr(chunks, "to_raw_data"):
        chunks = chunks.to_raw_data()
    out: list[str] = []
    if isinstance(chunks, list):
        for item in chunks:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
            else:
                text = str(getattr(item, "text", "")).strip()
            if text:
                out.append(text)
    else:
        text = str(getattr(chunks, "text", "")).strip()
        if text:
            out.append(text)
    return out


def _fetch_transcript_via_api(vid: str, languages: list[str]) -> str:
    text_chunks: list[str] = []
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        raw = YouTubeTranscriptApi.get_transcript(vid, languages=languages)
        text_chunks = _extract_text_chunks(raw)
    else:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            raw = api.fetch(vid, languages=languages)
            text_chunks = _extract_text_chunks(raw)
    text = " ".join(text_chunks).strip()
    if not text:
        raise RuntimeError("transcript text empty")
    return text


def _youtube_cookies_path() -> str | None:
    raw = (os.environ.get("YOUTUBE_COOKIES_FILE") or "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    return str(path) if path.is_file() else None


def _youtube_cookies_browser() -> str | None:
    raw = (os.environ.get("YOUTUBE_COOKIES_BROWSER") or "").strip()
    return raw if raw else None


def _youtube_has_auth_cookies() -> bool:
    return bool(_youtube_cookies_path() or _youtube_cookies_browser())


def _ytdlp_cookie_cli_args() -> list[str]:
    browser = _youtube_cookies_browser()
    if browser:
        return ["--cookies-from-browser", browser]
    path = _youtube_cookies_path()
    if path:
        return ["--cookies", path]
    return []


def _fetch_transcript_via_ytdlp(vid: str, languages: list[str]) -> str:
    cookie_args = _ytdlp_cookie_cli_args()
    try:
        from fetch_youtube_transcript import fetch_transcript_ytdlp  # type: ignore

        _raw, plain = fetch_transcript_ytdlp(vid, languages)
        return plain.strip()
    except ImportError:
        import subprocess
        import tempfile

        sub_langs = ",".join([*languages, "en", "hi", "en-orig"])
        url = f"https://www.youtube.com/watch?v={vid}"
        with tempfile.TemporaryDirectory(prefix="yt-subs-") as tmp:
            out_base = str(Path(tmp) / "sub")
            cmd = [sys.executable, "-m", "yt_dlp", *cookie_args]
            cmd.extend(
                [
                    "--skip-download",
                    "--ignore-no-formats-error",
                    "--extractor-args",
                    "youtube:player_client=default,-web",
                    "--write-auto-sub",
                    "--write-sub",
                    "--sub-langs",
                    sub_langs,
                    "--convert-subs",
                    "vtt",
                    "--no-playlist",
                    "-o",
                    out_base,
                    url,
                ]
            )
            env = os.environ.copy()
            env["PATH"] = "/opt/homebrew/bin:/usr/local/bin" + os.pathsep + env.get("PATH", "")
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120, env=env)
            if proc.returncode != 0:
                err = (proc.stderr or proc.stdout or "").strip()
                raise RuntimeError(f"yt-dlp subtitle fetch failed: {err[:500]}")
            vtt_files = sorted(
                Path(tmp).glob("*.vtt"), key=lambda p: p.stat().st_size, reverse=True
            )
            if not vtt_files:
                raise RuntimeError("yt-dlp did not produce any subtitle file")
            lines: list[str] = []
            for line in vtt_files[0].read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("WEBVTT") or "-->" in line:
                    continue
                if re.match(r"^\d+$", line) or line.startswith("Kind:") or line.startswith("Language:"):
                    continue
                lines.append(line)
            deduped: list[str] = []
            for line in lines:
                if not deduped or deduped[-1] != line:
                    deduped.append(line)
            plain = " ".join(deduped).strip()
            if len(plain) < 50:
                raise RuntimeError("yt-dlp subtitle file was too short or empty")
            return plain


def fetch_single_transcript(vid: str) -> tuple[str, str]:
    """Return (text, method) where method describes which fetch path succeeded."""
    languages = ["en", "en-US", "en-GB", "hi"]
    api_exc: Exception | None = None
    try:
        return _fetch_transcript_via_api(vid, languages), "api"
    except Exception as exc:
        api_exc = exc
        log(f"[youtube] {vid}: transcript-api failed ({exc}); trying yt-dlp")
    if _youtube_has_auth_cookies():
        browser = _youtube_cookies_browser()
        method = f"yt-dlp+{browser}" if browser else "yt-dlp+cookies-file"
        try:
            return _fetch_transcript_via_ytdlp(vid, languages), method
        except Exception as cookies_exc:
            log(f"[youtube] {vid}: {method} failed ({cookies_exc}); trying yt-dlp without cookies hint")
    try:
        text = _fetch_transcript_via_ytdlp(vid, languages)
        return text, "yt-dlp"
    except Exception as ytdlp_exc:
        hint = ""
        if not _youtube_has_auth_cookies():
            hint = " Set YOUTUBE_COOKIES_BROWSER=firefox:PROFILE (logged into YouTube)."
        raise RuntimeError(
            f"transcript-api: {api_exc}; yt-dlp: {ytdlp_exc}.{hint}"
        ) from ytdlp_exc


def fetch_transcripts(urls: list[str]) -> tuple[str, int, int]:
    import time

    parts = []
    ok = 0
    failed = 0
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(5)  # reduce YouTube subtitle 429 bursts
        vid = extract_video_id(url)
        if not vid:
            log(f"[youtube] skip (no video id): {url}")
            parts.append(f"=== URL (no id): {url} ===\n")
            failed += 1
            continue
        try:
            text, method = fetch_single_transcript(vid)
            log(f"[youtube] {vid}: ok via {method} ({len(text):,} chars)")
            parts.append(f"=== YouTube {vid} ===\n{text}\n")
            ok += 1
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            log(f"[youtube] {vid}: failed ({err[:240]})")
            parts.append(f"=== YouTube {vid} (fetch failed: {err}) ===\n")
            failed += 1
    return "\n".join(parts), ok, failed


def normalize_urls(raw_urls: list[str]) -> list[str]:
    urls: list[str] = []
    for entry in raw_urls:
        for part in re.split(r"\s*,\s*", (entry or "").strip()):
            if part:
                urls.append(part)
    return list(dict.fromkeys(urls))


def deepseek_request_timeout(duration_minutes: int = 0) -> int:
    """HTTP read timeout for DeepSeek — long stories can take many minutes to stream."""
    env = (os.environ.get("DEEPSEEK_REQUEST_TIMEOUT_SECONDS") or "").strip()
    if env:
        return max(60, int(env))
    if duration_minutes > 0:
        # 30 min story → 6000s (~100 min) cap at 2 hours
        return min(7200, max(600, duration_minutes * 180 + 600))
    return 600


def call_deepseek(
    api_key: str,
    system: str,
    user: str,
    model: str = "deepseek-v4-pro",
    *,
    best_quality: bool = True,
    max_tokens: int = 16384,
    request_timeout_s: int = 180,
    retries: int = 4,
    deadline_ts: float | None = None,
) -> tuple[str, str | None]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    if best_quality:
        # DeepSeek v4 thinking path: prefer max reasoning for quality.
        payload["reasoning_effort"] = "max"
        payload["thinking"] = {"type": "enabled"}

    def _request(data: dict) -> dict:
        req = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=request_timeout_s) as resp:
            return json.loads(resp.read().decode("utf-8"))

    data: dict | None = None
    for attempt in range(1, max(1, retries) + 1):
        assert_not_timed_out(deadline_ts, "deepseek request")
        try:
            data = _request(payload)
            break
        except urllib.error.HTTPError as exc:
            code = getattr(exc, "code", None)
            # Backward-compatible fallback if provider/version rejects thinking fields.
            if best_quality and code in (400, 404, 422):
                fallback = dict(payload)
                fallback.pop("reasoning_effort", None)
                fallback.pop("thinking", None)
                try:
                    data = _request(fallback)
                    break
                except Exception:
                    pass

            retryable = code in (408, 409, 425, 429, 500, 502, 503, 504)
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                pass
            if not retryable or attempt >= retries:
                raise RuntimeError(f"DeepSeek HTTP {code}: {body[:500]}") from exc
            wait_s = min(20, attempt * 3)
            log(f"[llm] transient HTTP {code}, retry {attempt}/{retries}, waiting {wait_s}s")
            time.sleep(wait_s)
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            if attempt >= retries:
                raise RuntimeError(
                    f"DeepSeek transport timeout after {retries} attempts "
                    f"(timeout={request_timeout_s}s): {exc}"
                ) from exc
            wait_s = min(30, attempt * 5)
            log(
                f"[llm] transport timeout ({request_timeout_s}s), "
                f"retry {attempt}/{retries}, waiting {wait_s}s"
            )
            time.sleep(wait_s)

    if data is None:
        raise RuntimeError("DeepSeek response missing after retries.")

    choices = data.get("choices") or []
    if not choices:
        return "", None
    first = choices[0] or {}
    message = first.get("message") or {}

    def _as_text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, list):
            parts: list[str] = []
            for part in value:
                if isinstance(part, dict):
                    t = part.get("text") or part.get("content") or ""
                    if t:
                        parts.append(str(t))
                elif part:
                    parts.append(str(part))
            return "\n".join(parts).strip()
        return str(value).strip()

    content = _as_text(message.get("content"))
    reasoning = ""
    for key in ("reasoning_content", "reasoning", "thinking"):
        reasoning = _as_text(message.get(key))
        if reasoning:
            break

    # Thinking models: final answer may be in content, reasoning, or both.
    # Prefer the block that actually contains the structured extract / script.
    def _score(text: str) -> int:
        upper = text.upper()
        score = 0
        if "BULLETS" in upper:
            score += 3
        if "STORY FLOW" in upper or "STORY_FLOW" in upper:
            score += 2
        if "FULL SCRIPT" in upper:
            score += 3
        if "SOURCE_ID" in upper:
            score += 1
        return score

    if not content and reasoning:
        content = reasoning
    elif content and reasoning and _score(reasoning) > _score(content):
        # Do not prefer reasoning when it reads like planning prose, not output.
        planning_markers = (
            "PRE-WRITE VALIDATOR",
            "STATUS: READY TO WRITE",
            "SELF-CHECK BEFORE WRITING",
            "I WILL OUTPUT",
            "LET'S PRODUCE",
        )
        reasoning_upper = reasoning.upper()
        looks_like_planning = any(m in reasoning_upper for m in planning_markers)
        if not looks_like_planning:
            content = reasoning
    elif content and reasoning and _score(content) == 0 and _score(reasoning) > 0:
        planning_markers = (
            "PRE-WRITE VALIDATOR",
            "STATUS: READY TO WRITE",
            "SELF-CHECK BEFORE WRITING",
        )
        if not any(m in reasoning.upper() for m in planning_markers):
            content = reasoning

    finish_reason = first.get("finish_reason")
    return content, finish_reason


def generate_with_continuation(
    *,
    api_key: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    max_continuations: int = 3,
    request_timeout_s: int = 180,
    retries: int = 4,
    deadline_ts: float | None = None,
    best_quality: bool = True,
) -> tuple[str, str | None]:
    raw, finish_reason = call_deepseek(
        api_key,
        system,
        user,
        model=model,
        best_quality=best_quality,
        max_tokens=max_tokens,
        request_timeout_s=request_timeout_s,
        retries=retries,
        deadline_ts=deadline_ts,
    )
    continuation_attempts = 0
    while (finish_reason or "").lower() == "length" and continuation_attempts < max_continuations:
        continuation_attempts += 1
        log(f"[llm] response truncated (length). requesting continuation {continuation_attempts}/{max_continuations} ...")
        tail = raw[-3000:]
        continue_prompt = (
            "Continue the SAME output from exactly where it stopped.\n"
            "Do not restart, do not repeat previous content, do not add commentary.\n"
            "Maintain the same format and language.\n\n"
            "LAST GENERATED TAIL (for continuity):\n"
            f"{tail}\n"
        )
        cont, finish_reason = call_deepseek(
            api_key,
            "You are continuing an already-started output. Continue seamlessly.",
            continue_prompt,
            model=model,
            best_quality=best_quality,
            max_tokens=max_tokens,
            request_timeout_s=request_timeout_s,
            retries=retries,
            deadline_ts=deadline_ts,
        )
        if not cont.strip():
            break
        raw = raw.rstrip() + "\n" + cont.lstrip()
    return raw, finish_reason


def strip_model_preamble(raw: str) -> str:
    """Drop model thinking / planning that appears before the real output sections.

    DeepSeek thinking often says "then Full Script, then Post-Write…" which used
    to fool substring parsers into treating the preamble as the script body.
    """
    text = (raw or "").strip()
    if not text:
        return text
    candidates: list[int] = []
    for pattern in (
        r"(?im)^\s*={5,}\s*$",
        r"(?im)^\s*TITLE\s+OPTIONS\b",
        r"(?im)^\s*THUMBNAIL\s+TEXT\b",
        r"(?im)^\s*HOOK\s*/\s*OPENING\b",
        r"(?im)^\s*FULL\s+SCRIPT\s*$",
    ):
        match = re.search(pattern, text)
        if match:
            candidates.append(match.start())
    if not candidates:
        return text
    start = min(candidates)
    return text[start:].lstrip() if start > 0 else text


def _section_header(pattern: str, text: str) -> re.Match[str] | None:
    """Match a section title only as its own line (never mid-sentence mentions)."""
    return re.search(pattern, text)


# Markers that start the meta tail after narration.
# IMPORTANT: avoid nested quantifiers like (?:[─\-]+)* — they catastrophic-backtrack
# on long LLM outputs (hung story 124 for 10h at 99% CPU in re.search).
_META_MARKER_RE = re.compile(
    r"(?i)\b("
    r"POST-?WRITE\s+CHARACTER\s+COUNT|"
    r"POST-?WRITE\s+COMPLIANCE\s+VALIDATOR|"
    r"YOUTUBE\s+DESCRIPTION|"
    r"STORY\s+META"
    r")\b"
)
_BOX_TOP_RE = re.compile(r"^[┌┏╔][─━═\-]{3,}[┐┓╗]\s*$")
_BOX_ROW_RE = re.compile(r"^[│┃|]")


def _line_meta_marker(line: str) -> re.Match[str] | None:
    """Return match when a line is (or is a boxed row containing) a meta header.

    Ignores inline mentions in planning prose (e.g. "Then Post-write character count").
    """
    cleaned = re.sub(r"^[\s│┃|═━─\-]+|[\s│┃|═━─\-]+$", "", line)
    if not cleaned:
        return None
    # Allow optional list / step prefix before the header token.
    header_line = re.sub(
        r"^(?:\d+[\.\)]\s*|(?:STEP|SECTION)\s+\d+\s*[:\-]\s*)",
        "",
        cleaned,
        flags=re.I,
    ).strip()
    match = _META_MARKER_RE.search(header_line)
    if not match or match.start() != 0:
        return None
    return match


def _find_meta_cut_index(text: str, *, post_write_only: bool = False) -> int | None:
    """Return absolute index where meta/post-write block begins, or None."""
    if not text:
        return None
    lines = text.splitlines(keepends=True)
    offset = 0
    prev_box_top_at: int | None = None
    for line in lines:
        stripped = line.strip()
        if _BOX_TOP_RE.match(stripped):
            prev_box_top_at = offset
            offset += len(line)
            continue

        marker = _line_meta_marker(line)
        if marker:
            upper = marker.group(1).upper().replace(" ", "")
            is_post = "POSTWRITE" in upper.replace("-", "")
            if post_write_only and not is_post:
                offset += len(line)
                continue
            # Cut at box top if the marker is on the next boxed row.
            if prev_box_top_at is not None and _BOX_ROW_RE.match(stripped):
                return prev_box_top_at
            return offset

        if stripped and not _BOX_ROW_RE.match(stripped) and not re.match(r"^[└┗╚][─━═\-]+[┘┛╝]$", stripped):
            prev_box_top_at = None
        offset += len(line)
    return None


def find_post_write_header(text: str) -> re.Match[str] | None:
    """Locate post-write header; returns a match whose .start() is the cut index."""
    idx = _find_meta_cut_index(text or "", post_write_only=True)
    if idx is None:
        return None

    class _IdxMatch:
        def __init__(self, start: int, end: int):
            self._start = start
            self._end = end

        def start(self, group: int = 0) -> int:
            return self._start

        def end(self, group: int = 0) -> int:
            return self._end

    # end at end of the header line
    end = text.find("\n", idx)
    if end < 0:
        end = len(text)
    else:
        end += 1
    return _IdxMatch(idx, end)  # type: ignore[return-value]


def strip_trailing_meta(script_body: str) -> tuple[str, str]:
    """Split narration from any trailing post-write / description / meta block."""
    body = (script_body or "").strip()
    if not body:
        return "", ""
    cut = _find_meta_cut_index(body, post_write_only=False)
    if cut is not None and cut >= 80:
        return body[:cut].rstrip(), body[cut:].strip()
    return body, ""


def parse_generated_sections(raw: str) -> tuple[str, str, str, bool, str]:
    """
    Extract script and meta from generated output.

    Returns:
      full_script_only, story_meta, story_plan_raw, parsed_ok, parse_note
    """
    cleaned = strip_model_preamble(raw)
    text = cleaned.strip()
    plan_raw = text  # store without thinking preamble

    full_script_header = _section_header(r"(?im)^\s*FULL\s+SCRIPT\s*$", text)
    post_write_header = find_post_write_header(text)

    if full_script_header and post_write_header and post_write_header.start() > full_script_header.end():
        script_body = text[full_script_header.end() : post_write_header.start()]
        script_body = re.sub(r"^\s*={3,}\s*", "", script_body).strip("\n\r =-\t")
        script_body = re.sub(r"\n\s*={3,}\s*$", "", script_body).strip()
        script_body, trailing_meta = strip_trailing_meta(script_body)
        meta = text[post_write_header.start() :].strip()
        if trailing_meta and trailing_meta not in meta:
            meta = (trailing_meta + "\n\n" + meta).strip()
        return script_body, meta, plan_raw, True, "full_script_and_post_write_found"

    if full_script_header and not post_write_header:
        script_body = text[full_script_header.end() :].strip("\n\r =-\t")
        script_body = re.sub(r"^\s*={3,}\s*", "", script_body).strip()
        script_body, meta = strip_trailing_meta(script_body)
        if meta:
            return script_body, meta, plan_raw, True, "post_write_recovered_from_script_tail"
        cut = _section_header(
            r"(?im)^\s*(DESCRIPTION|YOUTUBE\s+DESCRIPTION|SHORTS|META|STORY\s+META)\b",
            script_body,
        )
        if cut and cut.start() > 200:
            script_body = script_body[: cut.start()].strip()
        return script_body, "", plan_raw, True, "post_write_missing_used_full_script_tail"

    # No FULL SCRIPT header — still split narration from post-write meta if present.
    if post_write_header and post_write_header.start() > 80:
        script_body = text[: post_write_header.start()].strip()
        script_body, _extra = strip_trailing_meta(script_body)
        meta = text[post_write_header.start() :].strip()
        # Planning-only outputs mention post-write inline — reject tiny pseudo-scripts.
        if len(script_body) < 400:
            return text, "", plan_raw, False, "post_write_false_positive_planning_only"
        return script_body, meta, plan_raw, True, "post_write_split_without_full_script_header"

    upper = text.upper()
    markers = ["STORY META", "META:", "---META---", "TITLE SUGGESTIONS"]
    for marker in markers:
        if marker in upper:
            idx = upper.index(marker)
            return text[:idx].strip(), text[idx:].strip(), plan_raw, False, "fallback_marker_split_only"
    return text, "", plan_raw, False, "no_known_sections"


def inject_full_script(original_raw: str, new_script: str) -> str:
    """
    Replace only the FULL SCRIPT body while preserving other sections.
    """
    text = strip_model_preamble(original_raw).strip()
    full_script_header = _section_header(r"(?im)^\s*FULL\s+SCRIPT\s*$", text)
    post_write_header = find_post_write_header(text)
    if not full_script_header or not post_write_header or post_write_header.start() <= full_script_header.end():
        return text

    prefix = text[: full_script_header.end()]
    suffix = text[post_write_header.start() :]
    return f"{prefix}\n\n{new_script.strip()}\n\n{suffix.lstrip()}"


def maybe_expand_script_length(
    api_keys: dict[str, str],
    model: str,
    full_script: str,
    duration_minutes: int,
    deadline_ts: float | None = None,
) -> str:
    target_chars = max(0, int(duration_minutes) * 1000)
    if target_chars <= 0:
        return full_script

    current_script = full_script.strip()
    current_chars = len(current_script)
    min_chars = int(target_chars * 0.95)
    max_chars = int(target_chars * 1.07)
    if current_chars >= min_chars:
        return current_script

    # Never invent a novel from a near-empty stub — that produces off-topic filler.
    if current_chars < int(target_chars * 0.25):
        log(
            f"[llm] skip length expansion — script too short to expand safely "
            f"({current_chars} < 25% of target {target_chars})"
        )
        return current_script

    if api_keys.get("deepseek_api_key", "") or (os.environ.get("DEEPSEEK_API_KEYS") or "").strip() or (
        os.environ.get("DEEPSEEK_API_KEY") or ""
    ).strip():
        with leased_deepseek_key(api_keys) as deepseek_key:
            for attempt in range(1, 4):
                current_chars = len(current_script)
                if current_chars >= min_chars:
                    break
                assert_not_timed_out(deadline_ts, "length expansion")
                expand_prompt = (
                    "Expand the following Hindi documentary narration while preserving plot, tone, "
                    "and character consistency.\n"
                    f"Current length: {current_chars} characters.\n"
                    f"Target length: {target_chars} characters.\n"
                    f"Allowed range: {min_chars} to {max_chars} characters.\n"
                    "Add meaningful narrative detail from the same topic only.\n"
                    "Do NOT invent new romance plots, unrelated characters, or filler.\n"
                    "Do NOT copy any source video's opening hook wording.\n"
                    "Do not add headings, bullets, titles, characters, or metadata.\n"
                    "Return ONLY the final expanded narration text.\n\n"
                    "SCRIPT TO EXPAND:\n"
                    f"{current_script}\n"
                )
                log(f"[llm] expanding script length pass {attempt}/3 (current={current_chars}, target={target_chars})")
                expanded, _ = generate_with_continuation(
                    api_key=deepseek_key,
                    model=model,
                    system="You are an expert Hindi storyteller. Obey requested character range strictly.",
                    user=expand_prompt,
                    max_tokens=min(65536, max(16384, int(target_chars * 2.2))),
                    max_continuations=2,
                    request_timeout_s=deepseek_request_timeout(duration_minutes),
                    retries=3,
                    deadline_ts=deadline_ts,
                )
                expanded = expanded.strip()
                if expanded:
                    current_script = expanded

    return current_script


def _looks_like_hindi_script(text: str) -> bool:
    """True when text is mostly narration, not English planning/meta."""
    body = (text or "").strip()
    if len(body) < 400:
        return False
    devanagari = len(re.findall(r"[\u0900-\u097F]", body))
    latin = len(re.findall(r"[A-Za-z]", body))
    if devanagari < 200:
        return False
    # Reject English planning dumps that polluted #126.
    lower = body[:2000].lower()
    planning_markers = (
        "we need to process",
        "pre-write validator",
        "continue this same hindi",
        "last script tail",
        "i'll count the characters",
        "now generating the output",
        "full script (30,000",
    )
    if any(m in lower for m in planning_markers):
        return False
    # Prefer Devanagari-heavy text; allow some Latin (names/acronyms).
    return devanagari >= max(200, int(latin * 0.35))


def extend_story_to_min_chars(
    api_keys: dict[str, str],
    model: str,
    full_script: str,
    duration_minutes: int,
    *,
    deadline_ts: float | None = None,
) -> str:
    """
    Force minimum length by requesting continuation-only additions.
    """
    target_chars = max(0, int(duration_minutes) * 1000)
    if target_chars <= 0:
        return full_script.strip()

    min_chars = int(target_chars * 0.95)
    current_script = full_script.strip()
    if len(current_script) >= min_chars:
        return current_script

    # Same safety as maybe_expand: never continue a near-empty / non-script stub.
    if len(current_script) < int(target_chars * 0.25):
        log(
            f"[llm] skip length-guard continuation — script too short to continue safely "
            f"({len(current_script)} < 25% of target {target_chars})"
        )
        return current_script
    if not _looks_like_hindi_script(current_script):
        log(
            "[llm] skip length-guard continuation — parsed body is not a usable Hindi script "
            "(looks like planning/meta). Refusing to append to junk."
        )
        return current_script

    if not (
        api_keys.get("deepseek_api_key", "")
        or (os.environ.get("DEEPSEEK_API_KEYS") or "").strip()
        or (os.environ.get("DEEPSEEK_API_KEY") or "").strip()
    ):
        return current_script

    with leased_deepseek_key(api_keys) as deepseek_key:
        for attempt in range(1, 5):
            current_len = len(current_script)
            if current_len >= min_chars:
                break
            assert_not_timed_out(deadline_ts, "continuation length guard")
            need = max(500, min_chars - current_len)
            tail = current_script[-2500:]
            continue_prompt = (
                "Continue this SAME Hindi FULL SCRIPT from the exact ending.\n"
                "IMPORTANT:\n"
                "- Output ONLY continuation text to append.\n"
                "- Do NOT restart or summarize previous content.\n"
                "- No headings, bullets, or metadata.\n"
                f"- Add about {need} more characters while preserving continuity.\n\n"
                "LAST SCRIPT TAIL:\n"
                f"{tail}\n"
            )
            log(
                f"[llm] length-guard continuation {attempt}/4 "
                f"(current={current_len}, min={min_chars}, need≈{need})"
            )
            cont, _ = generate_with_continuation(
                api_key=deepseek_key,
                model=model,
                system="You are an expert Hindi storyteller. Continue seamlessly.",
                user=continue_prompt,
                max_tokens=min(65536, max(12000, int(need * 2.0))),
                max_continuations=2,
                request_timeout_s=deepseek_request_timeout(duration_minutes),
                retries=3,
                deadline_ts=deadline_ts,
            )
            cont = cont.strip()
            if not cont:
                break
            if current_script[:200] in cont and len(cont) > int(len(current_script) * 0.6):
                # Model sometimes returns full rewrite instead of append.
                current_script = cont
            else:
                current_script = current_script.rstrip() + "\n\n" + cont.lstrip()

    return current_script


def recover_missing_full_script(
    *,
    api_keys: dict[str, str],
    model: str,
    transcripts: str,
    duration: int,
    prior_raw: str,
    deadline_ts: float | None = None,
    research_label: str = "TRANSCRIPTS (sole factual source)",
) -> tuple[str, str, str, bool, str]:
    """
    Second LLM pass when the model wrote planning/character sheets but never
    reached FULL SCRIPT (common on short YouTube jobs with the full master prompt).
    """
    target_chars = max(0, int(duration) * 1000)
    min_chars = int(target_chars * 0.95) if target_chars > 0 else 0
    max_chars = int(target_chars * 1.07) if target_chars > 0 else 0
    gen_max_tokens = min(65536, max(16384, int(target_chars * 2.2))) if target_chars > 0 else 16384

    planning_tail = (prior_raw or "").strip()
    if len(planning_tail) > 12000:
        planning_tail = planning_tail[:6000] + "\n\n[... truncated ...]\n\n" + planning_tail[-4000:]

    recovery_user = (
        "The previous attempt stopped before FULL SCRIPT.\n"
        "Write ONLY the missing output sections below.\n"
        "Do NOT repeat PRE-WRITE VALIDATOR, TOP 10 CHARACTERS, or character image prompts.\n\n"
        f"TARGET DURATION (MINUTES): {duration}\n"
        f"TARGET CHARACTERS: {target_chars}\n"
        f"ACCEPTABLE RANGE: {min_chars} – {max_chars}\n\n"
        f"{research_label}:\n{transcripts.strip()}\n\n"
        f"PRIOR PLANNING (tone/structure reference only — do not copy verbatim):\n{planning_tail}\n\n"
        "Required output format:\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "FULL SCRIPT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "[Hindi narration script only]\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "POST-WRITE CHARACTER COUNT\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "[actual count and range check]\n"
    )

    log("[llm] FULL SCRIPT missing — running recovery pass...")
    with leased_deepseek_key(api_keys) as deepseek_key:
        recovery_raw, _ = generate_with_continuation(
            api_key=deepseek_key,
            model=model,
            system="You are an expert Hindi documentary scriptwriter. Output only the requested sections.",
            user=recovery_user,
            max_tokens=gen_max_tokens,
            max_continuations=4,
            request_timeout_s=deepseek_request_timeout(duration),
            retries=int(os.environ.get("DEEPSEEK_REQUEST_RETRIES", "4")),
            deadline_ts=deadline_ts,
            best_quality=False,
        )

    merged_raw = prior_raw.rstrip() + "\n\n" + recovery_raw.lstrip()
    return parse_generated_sections(merged_raw)


def _guess_video_id_from_label(label: str) -> str | None:
    m = re.search(r"([a-zA-Z0-9_-]{11})", label)
    return m.group(1) if m else None


def _combine_transcript_parts(parts: list[tuple[str, str]], youtube_urls: list[str]) -> str:
    sections: list[str] = []
    for index, (label, text) in enumerate(parts):
        text = text.strip()
        if not text:
            continue
        vid = _guess_video_id_from_label(label)
        if not vid and index < len(youtube_urls):
            vid = extract_video_id(youtube_urls[index])
        if not vid:
            vid = f"upload-{index + 1}"
        sections.append(f"=== YouTube {vid} ===\n{text}")
    return "\n\n".join(sections) + ("\n" if sections else "")


def _collect_transcript_files(base_script_dir: Path) -> list[Path]:
    transcript_dir = base_script_dir / "transcripts"
    if transcript_dir.is_dir():
        files = sorted(transcript_dir.glob("*.txt"), key=lambda p: p.name)
        if files:
            return files
    for name in ("uploaded_transcript.txt", "combined_transcript.txt"):
        path = base_script_dir / name
        if path.is_file():
            return [path]
    return []


def load_uploaded_transcript(bundle: dict, slug_folder: Path | None) -> str | None:
    """Read uploaded transcript(s) from the Drupal story node."""
    story = (bundle or {}).get("story") or {}
    if not story.get("has_uploaded_transcript"):
        return None

    youtube_urls = story.get("youtube_urls") or []
    script_dirs: list[Path] = []
    if slug_folder is not None:
        script_dirs.append(slug_folder / "script")

    asset_root = (os.environ.get("STORY_ASSET_ROOT") or "").strip()
    if asset_root and story.get("id"):
        stype = story.get("story_type") or "general"
        title = story.get("title") or f"story-{story['id']}"
        sid = story["id"]
        slug = slugify(title, fallback=f"story-{sid}")
        script_dirs.append(Path(asset_root).expanduser() / stype / f"{sid}-{slug}" / "script")

    for script_dir in script_dirs:
        files = _collect_transcript_files(script_dir)
        if not files:
            continue
        if len(files) == 1 and files[0].name in ("uploaded_transcript.txt", "combined_transcript.txt"):
            text = files[0].read_text(encoding="utf-8", errors="replace").strip()
            if len(text) >= 100:
                return text
            continue
        parts: list[tuple[str, str]] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
            if text:
                parts.append((path.stem, text))
        combined = _combine_transcript_parts(parts, youtube_urls).strip()
        if len(combined) >= 100:
            return combined
    return None


def run_generate(story_id: int, *, pointers_only: bool = False) -> None:
    client = DrupalStoryClient()

    log("[progress] stage=boot")
    log(f"[drupal] GET bundle (generate)")
    bundle = client.get_bundle(story_id, pipeline="generate")
    repo_root = setup_automation_paths(bundle)
    load_all_env(repo_root)
    apply_asset_root_from_bundle(bundle)
    if not (os.environ.get("AUTOMATION_REPO") or "").strip():
        os.environ["AUTOMATION_REPO"] = str(repo_root)
    story = bundle["story"]
    urls = normalize_urls(story.get("youtube_urls") or [])

    api_keys = resolve_keys(bundle)
    anthropic_key = api_keys.get("anthropic_api_key", "")

    if not api_keys.get("deepseek_api_key", "") and not anthropic_key and not (
        os.environ.get("DEEPSEEK_API_KEYS") or ""
    ).strip() and not (os.environ.get("DEEPSEEK_API_KEY") or "").strip():
        sys.exit(
            "error: set DeepSeek or Anthropic key in Drupal config, worker .env, "
            "or AUTOMATION_REPO/.env"
        )

    master = bundle["prompts"].get("master_prompt") or ""
    if not master:
        sys.exit("error: master_prompt empty on Story Type taxonomy term in Drupal")

    duration = int(story.get("duration_minutes") or 0)
    custom_instructions = (story.get("custom_instructions") or "").strip()
    pointers_only = pointers_only or bool(story.get("research_only"))

    slug_folder = story_folder(
        slug=slugify(story.get("title") or "", fallback=f"story-{story_id}"),
        story_id=story_id,
        title=story.get("title") or "",
        story_type=story.get("story_type") or "general",
    )
    research_dir = (slug_folder / "research") if slug_folder is not None else None

    uploaded_transcript = load_uploaded_transcript(bundle, slug_folder)
    channel_research = False if uploaded_transcript else use_channel_first_research(bundle, master)
    seed_url = urls[0] if urls else ""
    research_meta: dict = {}

    if uploaded_transcript:
        transcripts = uploaded_transcript
        transcript_ok, transcript_failed = 1, 0
        log(
            f"[progress] stage=transcripts mode=uploaded chars={len(transcripts):,} "
            "skip_youtube=1"
        )
    elif channel_research:
        log(f"[progress] stage=research mode=channel_first seed={seed_url}")
        if research_dir is None:
            sys.exit("error: STORY_ASSET_ROOT not configured — cannot save research artifacts")
        try:
            transcripts, research_meta = run_channel_research(seed_url, research_dir)
            transcript_ok, transcript_failed = 1, 0
            log(
                f"[research] done videos={research_meta.get('selected_count', '?')} "
                f"priority={research_meta.get('priority_channel_count', '?')} "
                f"chars={len(transcripts):,}"
            )
        except Exception as exc:
            log(f"[research] channel-first failed ({exc}); falling back to direct transcript fetch")
            transcripts, transcript_ok, transcript_failed = fetch_transcripts(urls)
    else:
        if not urls:
            sys.exit("error: story has no YouTube URLs and no uploaded transcript file")
        log(f"[progress] stage=transcripts count={len(urls)} mode=transcript_only")
        log(f"[youtube] fetching {len(urls)} transcript(s)")
        transcripts, transcript_ok, transcript_failed = fetch_transcripts(urls)

    # Timeout budget scales with requested duration by default so longer stories
    # (e.g., 40 minutes) get enough time for generation + expansion passes.
    # Operators can still hard-override via STORY_GENERATE_MAX_SECONDS.
    env_wall_clock = (os.environ.get("STORY_GENERATE_MAX_SECONDS") or "").strip()
    if env_wall_clock:
        wall_clock_limit_s = int(env_wall_clock)
    else:
        base_seconds = 1200
        per_minute_seconds = 120
        computed = base_seconds + max(0, duration) * per_minute_seconds
        wall_clock_limit_s = min(14400, max(1800, computed))
    deadline_ts = now_monotonic() + max(300, wall_clock_limit_s)
    api_timeout_s = deepseek_request_timeout(duration)
    api_retries = int(os.environ.get("DEEPSEEK_REQUEST_RETRIES", "4"))
    log(f"[timing] wall_clock_limit_s={wall_clock_limit_s} (duration={duration}m)")
    log(f"[timing] deepseek_request_timeout_s={api_timeout_s} retries={api_retries}")

    if transcript_ok <= 0:
        failure_note = (
            "Transcript fetch failed for all provided YouTube URLs. "
            "Story generation skipped to avoid invalid output."
        )
        detail = transcripts.strip()
        story_meta = failure_note
        if detail:
            story_meta = f"{failure_note}\n\n{detail[:8000]}"
        client.update_story(
            story_id,
            {
                "story_plan_raw": f"{failure_note}\n\n{transcripts}",
                "story_meta": story_meta,
                "status": "failed",
            },
        )
        sys.exit("error: all transcript fetches failed")

    if slug_folder is not None:
        if uploaded_transcript:
            combined_name = "uploaded_transcript.txt"
        else:
            combined_name = "COMBINED_RESEARCH.txt" if channel_research else "combined_transcript.txt"
        (slug_folder / "script" / combined_name).write_text(transcripts.strip() + "\n", encoding="utf-8")
        mirror_story_folder(slug_folder)

    settings = bundle.get("settings") or {}
    model = settings.get("model", "deepseek-v4-pro")
    mode = source_mode()
    research_for_prompt = transcripts
    research_label = "TRANSCRIPTS (sole factual source)"

    # Research-only: always extract bullet ledger, then stop before story LLM.
    extract_bullets = mode == "bullets" or pointers_only
    if pointers_only:
        log("[progress] stage=research_only (transcript + bullets; skip story LLM)")

    # Bullet mode: per-source 20–25 POINTER extracts → generate from ledger only.
    if extract_bullets:
        log(f"[progress] stage=pointer_extract mode={'bullets' if mode == 'bullets' else 'research_only'}")
        assert_not_timed_out(deadline_ts, "pointer extraction")
        with leased_deepseek_key(api_keys) as deepseek_key:
            research_for_prompt, bullet_entries = extract_bullet_ledger(
                combined_transcripts=transcripts,
                api_key=deepseek_key,
                model=model,
                call_llm=call_deepseek,
                log=log,
                topic=story.get("title") or "",
                deadline_ts=deadline_ts,
                request_timeout_s=api_timeout_s,
            )
        save_bullet_artifacts(slug_folder, research_for_prompt, bullet_entries)
        try:
            assert_ledger_usable(bullet_entries)
        except RuntimeError as exc:
            failure_note = str(exc)
            log(f"[pointers] FAIL {failure_note}")
            client.update_story(
                story_id,
                {
                    "story_plan_raw": research_for_prompt,
                    "story_meta": failure_note,
                    "status": "failed",
                },
            )
            sys.exit(f"error: {failure_note}")
        research_label = "STORY POINTER LEDGER (sole factual source — no raw transcripts)"
        log(
            f"[pointers] ledger ready sources={len(bullet_entries)} "
            f"chars={len(research_for_prompt):,}"
        )
        if slug_folder is not None:
            log(f"[assets] pointer ledger → {slug_folder / 'script' / 'BULLET_LEDGER.txt'}")

        if pointers_only:
            combined_name = "COMBINED_RESEARCH.txt" if channel_research else "combined_transcript.txt"
            research_note_parts = [
                "Research-only run: combined transcript + bullet pointer ledger saved.",
                f"Transcript file: script/{combined_name}",
                "Bullet ledger: script/BULLET_LEDGER.txt",
                "Paste your script into Full story on the story node, then run Build storyboard.",
            ]
            if research_meta:
                research_note_parts.insert(
                    1,
                    f"Videos: {research_meta.get('selected_count', '?')} "
                    f"({research_meta.get('priority_channel_count', '?')} priority channels).",
                )
            payload = {
                "story_plan_raw": research_for_prompt,
                "story_meta": "\n".join(research_note_parts),
                "status": "research_done",
            }
            mirror_story_folder(slug_folder)
            log("[progress] stage=research_done")
            log(f"[drupal] POST update story {story_id} (research only)")
            result = client.update_story(story_id, payload)
            log(f"  status: {result.get('status')}")
            log("done (research only — no story generated).")
            return
    else:
        log(f"[progress] stage=source mode=transcript (raw combined)")

    system_prompt, user_block, v3_mode = build_generation_prompt(
        master,
        research_for_prompt,
        duration=duration,
        custom_instructions=custom_instructions,
        title=story.get("title") or "",
        story_type=story.get("story_type") or "general",
    )

    if slug_folder is not None:
        prompt_doc = (
            user_block.strip() + "\n"
            if v3_mode
            else (master.strip() + "\n\n=== USER INPUT ===\n\n" + user_block.strip() + "\n")
        )
        (slug_folder / "prompts" / "story-builder-input.txt").write_text(prompt_doc, encoding="utf-8")

    log(
        f"[progress] stage=prompt ready v3={v3_mode} source_mode={mode} "
        f"transcript_ok={transcript_ok} transcript_failed={transcript_failed}"
    )

    target_chars = max(0, int(duration) * 1000)
    gen_max_tokens = min(65536, max(16384, int(target_chars * 2.2))) if target_chars > 0 else 16384

    log(f"[progress] stage=llm model={model}")
    log(f"[llm] generating script from {'bullet ledger' if mode == 'bullets' else 'transcripts'}...")
    if api_keys.get("deepseek_api_key", "") or (os.environ.get("DEEPSEEK_API_KEYS") or "").strip() or (
        os.environ.get("DEEPSEEK_API_KEY") or ""
    ).strip():
        with leased_deepseek_key(api_keys) as deepseek_key:
            log(f"[llm] using max_tokens={gen_max_tokens} for requested duration={duration}m")
            raw, finish_reason = generate_with_continuation(
                api_key=deepseek_key,
                model=model,
                system=system_prompt,
                user=user_block,
                max_tokens=gen_max_tokens,
                max_continuations=4,
                request_timeout_s=api_timeout_s,
                retries=api_retries,
                deadline_ts=deadline_ts,
                best_quality=False,
            )
    else:
        sys.exit("error: Anthropic path not implemented yet — set deepseek_api_key in Drupal config")

    assert_not_timed_out(deadline_ts, "response parsing")
    full_story, meta, story_plan_raw, has_expected_sections, parse_note = parse_generated_sections(raw)
    if not has_expected_sections or len((full_story or "").strip()) < 400:
        if has_expected_sections:
            log(f"[llm] parsed script too short ({len((full_story or '').strip())} chars) — running recovery pass")
            has_expected_sections = False
        full_story, meta, story_plan_raw, has_expected_sections, parse_note = recover_missing_full_script(
            api_keys=api_keys,
            model=model,
            transcripts=research_for_prompt,
            duration=duration,
            prior_raw=raw,
            deadline_ts=deadline_ts,
            research_label=research_label,
        )
        if has_expected_sections and parse_note:
            parse_note = f"recovery_pass:{parse_note}"
    target_chars = max(0, int(duration) * 1000)
    min_chars = int(target_chars * 0.95) if target_chars > 0 else 0
    if has_expected_sections:
        log(f"[progress] stage=parse_ok note={parse_note} script_chars={len(full_story)}")
        # Safety: never keep post-write boxes inside the narration body.
        full_story, trailing_meta = strip_trailing_meta(full_story)
        if trailing_meta and not (meta or "").strip():
            meta = trailing_meta
        elif trailing_meta and trailing_meta not in (meta or ""):
            meta = ((meta or "").rstrip() + "\n\n" + trailing_meta).strip()
        full_story = maybe_expand_script_length(api_keys, model, full_story, duration, deadline_ts=deadline_ts)
        full_story = extend_story_to_min_chars(api_keys, model, full_story, duration, deadline_ts=deadline_ts)
        full_story, _again = strip_trailing_meta(full_story)
        story_plan_raw = inject_full_script(story_plan_raw, full_story)
        parse_meta_note = ""
        if parse_note == "post_write_missing_used_full_script_tail":
            parse_meta_note = "Parser note: POST-WRITE marker missing; used FULL SCRIPT tail recovery."
        final_len = len(full_story.strip())
        meets_length = (min_chars <= 0) or (final_len >= min_chars)
        merged_meta = "\n".join([x for x in [meta.strip(), parse_meta_note] if x]).strip()
        if meets_length:
            research_note = ""
            if research_meta:
                research_note = (
                    f"Research: {research_meta.get('selected_count', '?')} videos "
                    f"({research_meta.get('priority_channel_count', '?')} priority channels)."
                )
            if mode == "bullets":
                bullet_note = (
                    "Source mode: story pointer ledger "
                    "(20–25 POINTER Explains/How per source; no raw transcripts in prompt)."
                )
                research_note = "\n".join([x for x in [research_note, bullet_note] if x])
            merged_meta_final = "\n".join([x for x in [merged_meta, research_note] if x]).strip()
            payload = {
                "full_story": full_story,
                "story_plan_raw": story_plan_raw,
                "story_meta": merged_meta_final,
                "status": "story_generated",
            }
        else:
            failure_note = (
                f"Length guard failed: full_story {final_len} chars, required minimum {min_chars} "
                f"(target {target_chars})."
            )
            log(f"[llm] {failure_note}")
            payload = {
                "story_plan_raw": story_plan_raw,
                "story_meta": "\n".join([x for x in [merged_meta, failure_note] if x]).strip(),
                "status": "failed",
            }
    else:
        # Guardrail: do not overwrite main story when output structure is invalid/refusal-like.
        payload = {
            "story_plan_raw": story_plan_raw,
            "story_meta": "Model output missing expected FULL SCRIPT / POST-WRITE markers.",
            "status": "failed",
        }

    should_write_full_story = bool(payload.get("full_story"))
    sync_script(
        story_id,
        story.get("title") or "",
        full_story if should_write_full_story else "",
        meta if has_expected_sections else "",
        story.get("story_type") or "general",
    )

    log(f"[progress] stage=save")
    log(f"[drupal] POST update story {story_id}")
    result = client.update_story(story_id, payload)
    log(f"  status: {result.get('status')}")
    log(f"  full_story length: {len(strip_html(result.get('full_story') or ''))} chars")
    log("done.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate script from YouTube URLs for a Drupal story")
    parser.add_argument("story_id", type=int)
    parser.add_argument(
        "--source-mode",
        choices=("bullets", "transcript"),
        default=None,
        help="bullets=extract 20–25 story pointers per source then generate (default via STORY_SOURCE_MODE); "
        "transcript=pass raw combined transcripts to master prompt",
    )
    parser.add_argument(
        "--pointers-only",
        action="store_true",
        help="Download combined transcript + bullet pointer ledger only; skip story LLM "
        "(also set when Drupal field_research_only is checked)",
    )
    args = parser.parse_args()
    if args.source_mode:
        os.environ["STORY_SOURCE_MODE"] = args.source_mode
    try:
        run_generate(args.story_id, pointers_only=bool(args.pointers_only))
    except TimeoutError as exc:
        client = DrupalStoryClient()
        client.update_story(
            args.story_id,
            {
                "story_meta": f"Generation timeout: {exc}",
                "status": "failed",
            },
        )
        log(f"error: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
