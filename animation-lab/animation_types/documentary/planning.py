"""DeepSeek planning shared by documentary types. The model returns JSON only."""
from __future__ import annotations

import json
from typing import Callable

from animation_core.planning import call_json

POLICY = """
Read the full script for context, then choose one coherent contiguous passage.
Prefer 3 or 4 beats. Do not invent facts, dates, numbers, relationships, or assets
to fill a quota. Return fewer clips, or none, when that is all the script supports.
Every evidence quote must be an exact substring of the selected passage.
You may choose an approved template id and a style preset:
cinematic_dark, archival_paper, or clean_editorial.
Do not return JavaScript, HTML, CSS, shell commands, or arbitrary URLs.
Outcomes are suitable clips, an empty selection, or an explanation that assets
or review are required. Do not describe a generic substitute visual.
""".strip()


def _content(response: dict) -> str:
    choice = (response.get("choices") or [{}])[0]
    content = ((choice.get("message") or {}).get("content") or "").strip()
    if not content:
        raise ValueError(f"Planner response was empty (finish_reason={choice.get('finish_reason')})")
    return content


def _chat(key: str, messages: list[dict], *, model: str, timeout: int, client: Callable | None) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "max_tokens": 2500,
        "temperature": 0.2,
    }
    if client is not None:
        return client(payload)
    return call_json(key, payload, timeout)


def ask_json(
    *,
    key: str,
    model: str,
    timeout: int,
    system: str,
    user: dict,
    validate: Callable[[dict], dict],
    client: Callable | None = None,
) -> dict:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]
    last = "Planning failed"
    for attempt in range(2):
        content = _content(_chat(key, messages, model=model, timeout=timeout, client=client))
        try:
            return validate(json.loads(content))
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            last = str(error)
            if attempt:
                break
            messages += [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"Return corrected JSON only. Validation error: {error}"},
            ]
    raise ValueError(f"Planning failed validation after repair: {last}")
