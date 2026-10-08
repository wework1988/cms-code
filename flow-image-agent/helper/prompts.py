"""Parse CMS image-prompts-only.txt (|| delimited Scene N. blocks)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

SCENE_HEADING_RE = re.compile(
    r"^\s*Scene\s+(\d+)\s*[.:：]\s*",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class ScenePrompt:
    scene: int
    text: str
    prompt_hash: str

    @property
    def filename_stem(self) -> str:
        return scene_filename_stem(self.scene)


def scene_filename_stem(scene: int) -> str:
    """Pad to at least 3 digits; never truncate larger numbers."""
    if scene < 0:
        raise ValueError(f"Invalid scene number: {scene}")
    return f"{scene:03d}" if scene < 1000 else str(scene)


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def parse_image_prompts(text: str) -> list[ScenePrompt]:
    """
    Parse ||-delimited scene prompts.

    Preserves full prompt text (including internal blank lines).
    Rejects missing/duplicate scene numbers with actionable errors.
    """
    raw = _strip_bom(text).replace("\r\n", "\n").replace("\r", "\n")
    blocks = raw.split("||")
    scenes: list[ScenePrompt] = []
    errors: list[str] = []
    seen: dict[int, int] = {}

    for index, block in enumerate(blocks):
        body = block.strip()
        if not body:
            continue
        match = SCENE_HEADING_RE.search(body)
        if not match:
            preview = body[:80].replace("\n", " ")
            errors.append(
                f"Block {index + 1}: missing Scene N. / Scene N: heading "
                f"(starts with: {preview!r})"
            )
            continue
        scene_num = int(match.group(1))
        if scene_num in seen:
            errors.append(
                f"Duplicate scene number {scene_num} "
                f"(blocks {seen[scene_num]} and {index + 1})"
            )
            continue
        seen[scene_num] = index + 1
        # Keep the complete block text (heading + body), trimmed outer whitespace only.
        prompt_text = body
        scenes.append(
            ScenePrompt(
                scene=scene_num,
                text=prompt_text,
                prompt_hash=prompt_hash(prompt_text),
            )
        )

    if errors:
        raise ValueError("Prompt parse failed:\n- " + "\n- ".join(errors))
    if not scenes:
        raise ValueError("Prompt parse failed: no scene prompts found (empty file or only ||).")

    scenes.sort(key=lambda s: s.scene)
    return scenes


def parse_image_prompts_file(path: Path) -> list[ScenePrompt]:
    text = path.read_text(encoding="utf-8")
    return parse_image_prompts(text)


def filter_scene_range(
    scenes: list[ScenePrompt],
    scene_from: int | None = None,
    scene_to: int | None = None,
    scene_list: list[int] | None = None,
) -> list[ScenePrompt]:
    if scene_list is not None:
        wanted = set(scene_list)
        selected = [s for s in scenes if s.scene in wanted]
        missing = sorted(wanted - {s.scene for s in selected})
        if missing:
            raise ValueError(f"Requested scenes not in prompt file: {missing}")
        return selected

    lo = scene_from if scene_from is not None else (scenes[0].scene if scenes else 1)
    hi = scene_to if scene_to is not None else (scenes[-1].scene if scenes else lo)
    if lo > hi:
        raise ValueError(f"Invalid scene range: from {lo} to {hi}")
    selected = [s for s in scenes if lo <= s.scene <= hi]
    if not selected:
        raise ValueError(f"No scenes found in range {lo}-{hi}")
    return selected


def detect_format(text: str) -> str:
    """Explicit format detection for UI preview."""
    raw = _strip_bom(text)
    if "||" in raw and SCENE_HEADING_RE.search(raw):
        return "pipe_delimited_scene_blocks"
    if SCENE_HEADING_RE.search(raw):
        return "scene_headings_without_pipes"
    return "unknown"
