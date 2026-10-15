"""Authoritative scene.txt loader for map jobs.

The heading pattern is the same one map_story.scenes uses. This loader
rejects duplicates and incomplete blocks instead of skipping them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from map_story.scenes import HEADING_RE

PARSER_VERSION = "2026.10-scene-txt-v1"
HEADING_MARK = re.compile(r"--- Scene\s+\d+")


class SceneSourceError(ValueError):
    """The saved scene file cannot be used. The full story is not a substitute."""


@dataclass(frozen=True)
class SceneRecord:
    number: int
    scene_id: str
    text: str
    text_hash: str
    approx_marker: int | None


@dataclass(frozen=True)
class SceneDocument:
    parser_version: str
    source_path: str | None
    source_hash: str
    scenes: list[SceneRecord]

    @property
    def scene_count(self) -> int:
        return len(self.scenes)


def load_scene_breakdown(text: str, *, source_path: str | None = None) -> SceneDocument:
    """Parse a completed scene.txt. Scene numbers stay exactly as written."""
    raw = text or ""
    if not raw.strip():
        raise SceneSourceError(
            "Saved scene file is empty. Finish the scene breakdown before generating maps. "
            "The Full story field was not used instead."
        )
    matches = list(HEADING_RE.finditer(raw))
    marks = HEADING_MARK.findall(raw)
    if not matches or len(marks) != len(matches):
        raise SceneSourceError(
            "Saved scene file is incomplete or malformed. Expected blocks of "
            "'--- Scene N / ~M ---' followed by 'Hindi line:'. "
            "The Full story field was not used instead."
        )
    scenes: list[SceneRecord] = []
    seen: set[int] = set()
    for match in matches:
        number = int(match.group(1))
        if number < 1:
            raise SceneSourceError(f"Scene number {number} is not valid. Scene numbers start at 1.")
        if number in seen:
            raise SceneSourceError(
                f"Duplicate scene number {number}. Fix scenes/scene.txt before generating maps."
            )
        hindi = match.group(3).strip()
        if not hindi:
            raise SceneSourceError(
                f"Scene {number} has no narration line. Finish that scene before generating maps."
            )
        seen.add(number)
        scenes.append(SceneRecord(
            number=number,
            scene_id=f"scene-{number}",
            text=hindi,
            text_hash=hashlib.sha256(hindi.encode("utf-8")).hexdigest(),
            approx_marker=int(match.group(2)),
        ))
    encoded = raw.encode("utf-8")
    return SceneDocument(
        parser_version=PARSER_VERSION,
        source_path=source_path,
        source_hash=hashlib.sha256(encoded).hexdigest(),
        scenes=scenes,
    )


def load_scene_file(path: Path) -> SceneDocument:
    if not path.is_file():
        raise SceneSourceError(
            f"Saved scene file was not found at {path}. "
            "Run the scene breakdown first. The Full story field was not used instead."
        )
    return load_scene_breakdown(path.read_text(encoding="utf-8-sig"), source_path=str(path))


def generation_key(
    *,
    source_hash: str,
    prompt_hash: str,
    theme_hash: str,
    limit: int,
    renderer: str,
    duration: float,
    parser_version: str = PARSER_VERSION,
) -> str:
    """Same inputs must enqueue one job. A new scene file or setting changes the key."""
    payload = {
        "source_hash": source_hash,
        "prompt_hash": prompt_hash,
        "theme_hash": theme_hash or "",
        "limit": int(limit),
        "renderer": renderer,
        "duration": float(duration),
        "parser_version": parser_version,
        "input_mode": "scene_breakdown",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def selection_cache_key(
    *,
    source_hash: str,
    limit: int,
    batch_scenes: int,
    batch_chars: int,
    parser_version: str = PARSER_VERSION,
) -> str:
    payload = {
        "source_hash": source_hash,
        "limit": int(limit),
        "batch_scenes": int(batch_scenes),
        "batch_chars": int(batch_chars),
        "parser_version": parser_version,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def presentation_cache_key(*, selection_key: str, prompt_hash: str, theme_hash: str) -> str:
    payload = {
        "selection_key": selection_key,
        "prompt_hash": prompt_hash,
        "theme_hash": theme_hash or "",
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def association_ok(entry: dict, document: SceneDocument) -> bool:
    """A published map belongs to a scene only when number and text hash still match."""
    number = entry.get("scene_number")
    text_hash = entry.get("scene_text_hash")
    if not isinstance(number, int) or not text_hash:
        return False
    current = next((scene for scene in document.scenes if scene.number == number), None)
    if current is None:
        return False
    return current.text_hash == text_hash and current.scene_id == entry.get("scene_id")


def inspect_payload(path: Path, *, include_text: bool = False) -> dict:
    try:
        document = load_scene_file(path)
    except SceneSourceError as error:
        return {"ok": False, "error": str(error), "path": str(path), "parser_version": PARSER_VERSION}
    stat = path.stat()
    payload = {
        "ok": True,
        "path": str(path),
        "filename": path.name,
        "parser_version": document.parser_version,
        "sha256": document.source_hash,
        "scene_count": document.scene_count,
        "modified": int(stat.st_mtime),
        "scenes": [
            {"number": scene.number, "scene_id": scene.scene_id, "text_hash": scene.text_hash}
            for scene in document.scenes
        ],
    }
    if include_text:
        payload["text"] = path.read_text(encoding="utf-8-sig")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a saved scene.txt for map generation")
    parser.add_argument("--inspect", type=Path)
    parser.add_argument("--include-text", action="store_true")
    parser.add_argument("--enqueue-key", action="store_true")
    parser.add_argument("--source-hash", default="")
    parser.add_argument("--prompt-hash", default="")
    parser.add_argument("--theme-hash", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--renderer", default="maplibre")
    parser.add_argument("--duration", type=float, default=14)
    args = parser.parse_args()
    if args.enqueue_key:
        print(generation_key(
            source_hash=args.source_hash,
            prompt_hash=args.prompt_hash,
            theme_hash=args.theme_hash,
            limit=args.limit,
            renderer=args.renderer,
            duration=args.duration,
        ))
        return
    if not args.inspect:
        parser.error("--inspect or --enqueue-key is required")
    json.dump(inspect_payload(args.inspect, include_text=args.include_text), sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
