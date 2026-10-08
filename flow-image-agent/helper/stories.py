"""Discover CMS story folders with image prompts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .prompts import parse_image_prompts_file, scene_filename_stem
from .security import resolve_under_roots, safe_relpath_key

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
PROMPT_REL = Path("image-prompts") / "image-prompts-only.txt"
CATEGORY_HINTS = frozenset({"general", "crime", "english", "god_story"})


@dataclass
class StoryInfo:
    key: str
    path: Path
    category: str
    story_id: str
    title: str
    prompt_file: Path
    prompt_count: int
    images_dir: Path
    completed_images: int
    scene_numbers: list[int]


def _read_meta(story_dir: Path, name: str) -> str:
    path = story_dir / "meta" / name
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def _infer_category(story_dir: Path, roots: list[Path]) -> str:
    meta = _read_meta(story_dir, "story-type.txt")
    if meta:
        return meta
    parent = story_dir.parent.name
    if parent in CATEGORY_HINTS:
        return parent
    for root in roots:
        try:
            rel = story_dir.resolve().relative_to(root.resolve())
            if rel.parts and rel.parts[0] in CATEGORY_HINTS:
                return rel.parts[0]
        except ValueError:
            continue
    return parent or "unknown"


def _infer_id_title(story_dir: Path) -> tuple[str, str]:
    node_id = _read_meta(story_dir, "drupal-node-id.txt")
    title = _read_meta(story_dir, "story-title.txt")
    name = story_dir.name
    if not node_id and "-" in name:
        head, rest = name.split("-", 1)
        if head.isdigit():
            node_id = head
            if not title:
                title = rest.replace("-", " ")
    if not title:
        title = name
    if not node_id:
        node_id = name
    return node_id, title


def count_completed_images(images_dir: Path, scene_numbers: list[int]) -> int:
    if not images_dir.is_dir():
        return 0
    present = set()
    for path in images_dir.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        stem = path.stem
        if stem.isdigit():
            present.add(int(stem))
    return sum(1 for n in scene_numbers if n in present)


def find_existing_image(images_dir: Path, scene: int) -> Path | None:
    stem = scene_filename_stem(scene)
    if not images_dir.is_dir():
        return None
    for ext in IMAGE_EXTS:
        candidate = images_dir / f"{stem}{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    # Also accept unpadded numeric names used by some older folders.
    for ext in IMAGE_EXTS:
        candidate = images_dir / f"{scene}{ext}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def discover_stories(roots: list[Path]) -> list[StoryInfo]:
    found: dict[str, StoryInfo] = {}
    for root in roots:
        if not root.is_dir():
            continue
        root_resolved = root.resolve()
        # Support both category roots (…/general) and trees (…/cms-generate-stories)
        candidates: list[Path] = []
        prompt_direct = root_resolved / PROMPT_REL
        if prompt_direct.is_file():
            candidates.append(root_resolved)
        else:
            for child in sorted(root_resolved.iterdir()):
                if not child.is_dir() or child.name.startswith("."):
                    continue
                if (child / PROMPT_REL).is_file():
                    candidates.append(child)
                else:
                    # one more level: cms-generate-stories/general/<story>
                    for nested in sorted(child.iterdir()):
                        if nested.is_dir() and (nested / PROMPT_REL).is_file():
                            candidates.append(nested)

        for story_dir in candidates:
            try:
                resolve_under_roots(story_dir, roots)
            except Exception:
                continue
            prompt_file = story_dir / PROMPT_REL
            try:
                scenes = parse_image_prompts_file(prompt_file)
            except ValueError:
                # Still list the story; prompt_count 0 signals parse issues in UI.
                scenes = []
            scene_numbers = [s.scene for s in scenes]
            story_id, title = _infer_id_title(story_dir)
            key = safe_relpath_key(story_dir, roots)
            # Prefer deeper/more specific roots if duplicate keys collide on path.
            info = StoryInfo(
                key=key,
                path=story_dir.resolve(),
                category=_infer_category(story_dir, roots),
                story_id=story_id,
                title=title,
                prompt_file=prompt_file.resolve(),
                prompt_count=len(scenes),
                images_dir=(story_dir / "images").resolve(),
                completed_images=count_completed_images(story_dir / "images", scene_numbers),
                scene_numbers=scene_numbers,
            )
            found[key] = info

    return sorted(found.values(), key=lambda s: (s.category, s.story_id, s.title.lower()))


def resolve_story(key: str, roots: list[Path]) -> StoryInfo:
    for story in discover_stories(roots):
        if story.key == key or str(story.path) == key or story.path.name == key:
            return story
    raise KeyError(f"Story not found: {key}")
