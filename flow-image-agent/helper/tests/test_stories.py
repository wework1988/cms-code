from __future__ import annotations

from pathlib import Path

from helper.stories import discover_stories, resolve_story


def test_discover_includes_pakistan_army():
    roots = [
        Path(__file__).resolve().parents[3] / "general",
        Path(__file__).resolve().parents[3] / "cms-generate-stories" / "general",
    ]
    roots = [r for r in roots if r.is_dir()]
    if not roots:
        return
    stories = discover_stories(roots)
    keys = {s.key for s in stories}
    assert any("165-pakistan-army" in k or k.endswith("165-pakistan-army") for k in keys)
    story = resolve_story("165-pakistan-army", roots)
    assert story.prompt_count == 202
    assert story.images_dir.name == "images"
