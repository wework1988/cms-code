#!/usr/bin/env python3
"""Call DeepSeek directly to break a story into scenes using updated-scene-breakdown.md."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

FULL_STORY_MARKER = "FULL STORY:"


def build_user_message(prompt_template: str, full_story: str) -> str:
    """Inject the story at the FULL STORY section of the prompt template."""
    story = full_story.strip()
    if not story:
        raise ValueError("Story text is empty")

    template = prompt_template.strip()
    marker_idx = template.find(FULL_STORY_MARKER)
    if marker_idx >= 0:
        before = template[: marker_idx + len(FULL_STORY_MARKER)]
        return f"{before}\n{story}\n"
    return f"{template}\n\n{FULL_STORY_MARKER}\n{story}\n"


def call_deepseek_scene_breakdown(
    api_key: str,
    prompt_template: str,
    full_story: str,
    *,
    model: str = "deepseek-v4-pro",
    max_tokens: int = 131072,
    temperature: float = 0.3,
    timeout: int = 900,
) -> str:
    user_message = build_user_message(prompt_template, full_story)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Break the supplied story into scene blocks exactly as instructed. "
                    "Return only the scene blocks — no commentary before or after."
                ),
            },
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {body}") from exc

    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    content = (message.get("content") or "").strip()
    finish_reason = choice.get("finish_reason") or ""

    if not content:
        raise RuntimeError("DeepSeek returned empty content")

    if finish_reason == "length":
        raise RuntimeError(
            "DeepSeek output was truncated (finish_reason=length). "
            "Try raising DEEPSEEK_MAX_TOKENS_BREAKDOWN or shorten the story for a test run."
        )

    return content


def write_breakdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")
