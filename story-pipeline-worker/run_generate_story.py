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

from asset_store import story_folder, sync_script
from drupal_client import DrupalStoryClient
from secrets import apply_asset_root_from_bundle, leased_deepseek_key, load_all_env, resolve_keys
from workspace import slugify, strip_html


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


def fetch_transcripts(urls: list[str]) -> tuple[str, int, int]:
    parts = []
    ok = 0
    failed = 0
    for url in urls:
        vid = extract_video_id(url)
        if not vid:
            parts.append(f"=== URL (no id): {url} ===\n")
            failed += 1
            continue
        try:
            text_chunks: list[str] = []
            if hasattr(YouTubeTranscriptApi, "get_transcript"):
                raw = YouTubeTranscriptApi.get_transcript(vid, languages=["hi", "en", "en-US", "en-GB"])
                text_chunks = _extract_text_chunks(raw)
            else:
                api = YouTubeTranscriptApi()
                if hasattr(api, "fetch"):
                    raw = api.fetch(vid, languages=["hi", "en", "en-US", "en-GB"])
                    text_chunks = _extract_text_chunks(raw)
            text = " ".join(text_chunks).strip()
            if not text:
                raise RuntimeError("transcript text empty")
            parts.append(f"=== YouTube {vid} ===\n{text}\n")
            ok += 1
        except Exception as exc:
            parts.append(f"=== YouTube {vid} (fetch failed: {exc}) ===\n")
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
    content = message.get("content") or ""
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
) -> tuple[str, str | None]:
    raw, finish_reason = call_deepseek(
        api_key,
        system,
        user,
        model=model,
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
            max_tokens=max_tokens,
            request_timeout_s=request_timeout_s,
            retries=retries,
            deadline_ts=deadline_ts,
        )
        if not cont.strip():
            break
        raw = raw.rstrip() + "\n" + cont.lstrip()
    return raw, finish_reason


def parse_generated_sections(raw: str) -> tuple[str, str, str, bool, str]:
    """
    Extract script and meta from generated output.

    Returns:
      full_script_only, story_meta, story_plan_raw, parsed_ok, parse_note
    """
    text = (raw or "").strip()
    upper = text.upper()

    full_script_header = re.search(r"FULL\s+SCRIPT", upper)
    post_write_header = re.search(r"POST-?WRITE\s+CHARACTER\s+COUNT", upper)

    if full_script_header and post_write_header and post_write_header.start() > full_script_header.end():
        script_start = full_script_header.end()
        script_body = text[script_start:post_write_header.start()]
        script_body = script_body.strip("\n\r =-\t")
        meta = text[post_write_header.start() :].strip()
        return script_body.strip(), meta, text, True, "full_script_and_post_write_found"

    if full_script_header and not post_write_header:
        # Recoverable: accept everything after FULL SCRIPT as script body.
        script_start = full_script_header.end()
        script_body = text[script_start:].strip("\n\r =-\t")
        return script_body.strip(), "", text, True, "post_write_missing_used_full_script_tail"

    # Fallback: old behavior for unexpected formats.
    markers = ["STORY META", "META:", "---META---", "TITLE SUGGESTIONS"]
    for marker in markers:
        if marker in upper:
            idx = upper.index(marker)
            return text[:idx].strip(), text[idx:].strip(), text, False, "fallback_marker_split_only"
    return text, "", text, False, "no_known_sections"


def inject_full_script(original_raw: str, new_script: str) -> str:
    """
    Replace only the FULL SCRIPT body while preserving other sections.
    """
    text = (original_raw or "").strip()
    upper = text.upper()
    full_script_header = re.search(r"FULL\s+SCRIPT", upper)
    post_write_header = re.search(r"POST-?WRITE\s+CHARACTER\s+COUNT", upper)
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
                    "Expand the following Hindi story script while preserving plot, tone, and character consistency.\n"
                    f"Current length: {current_chars} characters.\n"
                    f"Target length: {target_chars} characters.\n"
                    f"Allowed range: {min_chars} to {max_chars} characters.\n"
                    "Add meaningful narrative detail. Do not add headings, bullets, or metadata.\n"
                    "Return ONLY the final expanded script text.\n\n"
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
        f"TRANSCRIPTS (sole factual source):\n{transcripts.strip()}\n\n"
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
        )

    merged_raw = prior_raw.rstrip() + "\n\n" + recovery_raw.lstrip()
    return parse_generated_sections(merged_raw)


def run_generate(story_id: int) -> None:
    load_all_env(Path(os.environ.get("AUTOMATION_REPO", ".")).expanduser())
    client = DrupalStoryClient()

    log("[progress] stage=boot")
    log(f"[drupal] GET bundle (generate)")
    bundle = client.get_bundle(story_id, pipeline="generate")
    apply_asset_root_from_bundle(bundle)
    story = bundle["story"]
    urls = normalize_urls(story.get("youtube_urls") or [])
    if not urls:
        sys.exit("error: story has no YouTube URLs")

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

    log(f"[progress] stage=transcripts count={len(urls)}")
    log(f"[youtube] fetching {len(urls)} transcript(s)")
    transcripts, transcript_ok, transcript_failed = fetch_transcripts(urls)
    duration = int(story.get("duration_minutes") or 0)
    custom_instructions = (story.get("custom_instructions") or "").strip()

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
        client.update_story(
            story_id,
            {
                "story_plan_raw": f"{failure_note}\n\n{transcripts}",
                "story_meta": failure_note,
                "status": "failed",
            },
        )
        sys.exit("error: all transcript fetches failed")

    characters = (story.get("characters_info") or "").strip()
    youtube_generate_mode = not characters
    characters_block = (
        characters
        if characters
        else "(none — derive all characters and facts only from TRANSCRIPTS below)"
    )
    youtube_mode_rules = ""
    if youtube_generate_mode:
        youtube_mode_rules = (
            "YOUTUBE GENERATE MODE:\n"
            "- TRANSCRIPTS are the sole factual source.\n"
            "- Output PRE-WRITE VALIDATOR only, then SKIP the entire "
            "\"TOP 10 CHARACTERS IN THE STORY\" section (no PART A / PART B character sheets).\n"
            "- Proceed immediately to FULL SCRIPT, then POST-WRITE CHARACTER COUNT and remaining meta.\n"
            "- Do NOT spend tokens on character image prompts before the script.\n\n"
        )
    user_block = (
        f"{youtube_mode_rules}"
        f"CHARACTERS INFO:\n{characters_block}\n\n"
        f"TARGET DURATION (MINUTES):\n{duration}\n\n"
        f"TARGET CHARACTER COUNT:\n{duration * 1000 if duration > 0 else 0}\n\n"
        f"CUSTOM INSTRUCTIONS:\n{custom_instructions or '(none)'}\n\n"
        f"TRANSCRIPTS:\n{transcripts}\n\n"
        "Write output exactly in the master prompt format. FULL SCRIPT must match target character count range."
    )

    slug_folder = story_folder(
        slug=slugify(story.get("title") or "", fallback=f"story-{story_id}"),
        story_id=story_id,
        title=story.get("title") or "",
        story_type=story.get("story_type") or "general",
    )
    if slug_folder is not None:
        (slug_folder / "script" / "combined_transcript.txt").write_text(transcripts.strip() + "\n", encoding="utf-8")
        # Keep story-builder input separate from storyboard Stage C prompt.txt
        # to avoid filename conflicts in cms-generate-stories mirrors.
        (slug_folder / "prompts" / "story-builder-input.txt").write_text(
            (master.strip() + "\n\n=== USER INPUT ===\n\n" + user_block.strip() + "\n"),
            encoding="utf-8",
        )

    log(f"[progress] stage=prompt ready transcript_ok={transcript_ok} transcript_failed={transcript_failed}")

    settings = bundle.get("settings") or {}
    model = settings.get("model", "deepseek-v4-pro")
    target_chars = max(0, int(duration) * 1000)
    gen_max_tokens = min(65536, max(16384, int(target_chars * 2.2))) if target_chars > 0 else 16384

    log(f"[progress] stage=llm model={model}")
    log(f"[llm] generating script...")
    if api_keys.get("deepseek_api_key", "") or (os.environ.get("DEEPSEEK_API_KEYS") or "").strip() or (
        os.environ.get("DEEPSEEK_API_KEY") or ""
    ).strip():
        with leased_deepseek_key(api_keys) as deepseek_key:
            log(f"[llm] using max_tokens={gen_max_tokens} for requested duration={duration}m")
            raw, finish_reason = generate_with_continuation(
                api_key=deepseek_key,
                model=model,
                system=master,
                user=user_block,
                max_tokens=gen_max_tokens,
                max_continuations=4,
                request_timeout_s=api_timeout_s,
                retries=api_retries,
                deadline_ts=deadline_ts,
            )
    else:
        sys.exit("error: Anthropic path not implemented yet — set deepseek_api_key in Drupal config")

    assert_not_timed_out(deadline_ts, "response parsing")
    full_story, meta, story_plan_raw, has_expected_sections, parse_note = parse_generated_sections(raw)
    if not has_expected_sections and not re.search(r"FULL\s+SCRIPT", (raw or ""), re.I):
        full_story, meta, story_plan_raw, has_expected_sections, parse_note = recover_missing_full_script(
            api_keys=api_keys,
            model=model,
            transcripts=transcripts,
            duration=duration,
            prior_raw=raw,
            deadline_ts=deadline_ts,
        )
        if has_expected_sections and parse_note:
            parse_note = f"recovery_pass:{parse_note}"
    target_chars = max(0, int(duration) * 1000)
    min_chars = int(target_chars * 0.95) if target_chars > 0 else 0
    if has_expected_sections:
        log("[progress] stage=parse_ok")
        full_story = maybe_expand_script_length(api_keys, model, full_story, duration, deadline_ts=deadline_ts)
        full_story = extend_story_to_min_chars(api_keys, model, full_story, duration, deadline_ts=deadline_ts)
        story_plan_raw = inject_full_script(story_plan_raw, full_story)
        parse_meta_note = ""
        if parse_note == "post_write_missing_used_full_script_tail":
            parse_meta_note = "Parser note: POST-WRITE marker missing; used FULL SCRIPT tail recovery."
        final_len = len(full_story.strip())
        meets_length = (min_chars <= 0) or (final_len >= min_chars)
        merged_meta = "\n".join([x for x in [meta.strip(), parse_meta_note] if x]).strip()
        if meets_length:
            payload = {
                "full_story": full_story,
                "story_plan_raw": story_plan_raw,
                "story_meta": merged_meta,
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
    args = parser.parse_args()
    try:
        run_generate(args.story_id)
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
