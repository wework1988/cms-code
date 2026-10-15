#!/usr/bin/env python3
"""
Run playright-automation CMS-mode Digen after Flow images are ready.

Writes scene_N.mp4 into <story>/videos/. Soft-failure friendly for callers.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parent
DEFAULT_PLAYRIGHT = WORKER_ROOT.parent / "playright-automation"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
SCENE_HEADER_RE = re.compile(r"(?m)^Scene\s+(\d+)\.")
DIGEN_SCENE_RE = re.compile(r"(?m)^---\s*Scene\s+(\d+)\s*/")
MIN_IMAGES_FOR_VIDEOS = 10


def digen_videos_enabled() -> bool:
    raw = (os.environ.get("DIGEN_VIDEOS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def playright_root() -> Path:
    override = (os.environ.get("PLAYRIGHT_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_PLAYRIGHT.resolve()


def _count_images(images_dir: Path) -> int:
    if not images_dir.is_dir():
        return 0
    return sum(
        1
        for p in images_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTS
        and p.stem.isdigit()
        and not p.name.startswith(".")
    )


def _count_prompt_scenes(story_asset_dir: Path) -> int:
    prompt_txt = story_asset_dir / "prompts" / "prompt.txt"
    if prompt_txt.is_file():
        text = prompt_txt.read_text(encoding="utf-8", errors="replace")
        nums = [int(n) for n in DIGEN_SCENE_RE.findall(text)]
        if nums:
            return max(nums)
        nums = [int(n) for n in SCENE_HEADER_RE.findall(text)]
        if nums:
            return max(nums)
    ip = story_asset_dir / "image-prompts" / "image-prompts-only.txt"
    if ip.is_file():
        text = ip.read_text(encoding="utf-8", errors="replace")
        nums = [int(n) for n in SCENE_HEADER_RE.findall(text)]
        if nums:
            return max(nums)
        parts = [p for p in text.split("||") if p.strip()]
        return len(parts)
    return 0


def _count_videos(videos_dir: Path) -> int:
    if not videos_dir.is_dir():
        return 0
    return sum(
        1
        for p in videos_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".mp4" and p.stat().st_size > 0
    )


def _cms_ref(story_asset_dir: Path) -> str:
    """e.g. general/170-test-flow-images-story-2"""
    return f"{story_asset_dir.parent.name}/{story_asset_dir.name}"


def _enrich_node_path(env: dict[str, str]) -> dict[str, str]:
    homebrew = "/opt/homebrew/bin:/usr/local/bin"
    env["PATH"] = f"{homebrew}:{env.get('PATH') or '/usr/bin:/bin'}"
    for candidate in ("/opt/homebrew/bin/node", "/usr/local/bin/node"):
        if Path(candidate).is_file():
            env["NODE_BIN"] = candidate
            break
    return env


def run_digen_videos_for_story(
    story_asset_dir: Path,
    *,
    story_id: int | str | None = None,
    update_status=None,
) -> bool:
    """
    Generate missing Digen videos for story_asset_dir into videos/.

    Returns True on success, False if skipped. Raises on hard runner failure
    (caller may catch for soft-fail).
    """
    if not digen_videos_enabled():
        print("[digen-videos] skipped (DIGEN_VIDEOS=0)")
        return False

    story_asset_dir = Path(story_asset_dir).resolve()
    images_dir = story_asset_dir / "images"
    prompt_file = story_asset_dir / "prompts" / "prompt.txt"
    videos_dir = story_asset_dir / "videos"

    if not prompt_file.is_file():
        print(f"[digen-videos] skipped — no prompts/prompt.txt at {prompt_file}")
        return False

    scene_count = _count_prompt_scenes(story_asset_dir)
    image_count = _count_images(images_dir)
    if scene_count <= 0:
        print("[digen-videos] skipped — could not detect scene count")
        return False
    from pipeline_validation import media_report
    image_report = media_report(story_asset_dir, "images")
    images_complete = bool(image_report["complete"])
    if image_count < MIN_IMAGES_FOR_VIDEOS and not images_complete:
        print(
            f"[digen-videos] skipped — need at least {MIN_IMAGES_FOR_VIDEOS} images "
            f"({image_count}/{scene_count})"
        )
        print(
            f"PROGRESS [####################------]  85% · Digen videos skipped · "
            f"images {image_count}/{scene_count}"
        )
        return False
    if not images_complete:
        print(
            f"[digen-videos] images still generating "
            f"({image_count}/{scene_count}); starting videos for scenes that already have images"
        )

    root = playright_root()
    runner = root / "run-cms-story.js"
    if not runner.is_file():
        print(f"[digen-videos] skipped — playright not found at {root}")
        return False

    cms_ref = _cms_ref(story_asset_dir)
    cms_root = story_asset_dir.parent.parent
    print(f"[digen-videos] story={cms_ref} path={story_asset_dir}")
    print(
        f"[digen-videos] generating missing videos via Digen "
        f"({image_count} images → videos/)…"
    )
    print(
        f"PROGRESS [######################----]  88% · Digen videos · "
        f"starting {cms_ref} ({scene_count} scenes)"
    )

    if update_status:
        try:
            update_status(
                {
                    "status": "storyboard_running",
                    "story_meta": f"Digen videos: starting {cms_ref} ({scene_count} scenes)",
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[digen-videos] status update failed: {exc}")

    env = _enrich_node_path(os.environ.copy())
    env["WAIT_READY"] = env.get("WAIT_READY") or "1"
    env["CMS_STORIES_ROOT"] = str(cms_root)
    # Cursor sandbox may redirect Playwright browsers to an empty cache.
    pb = (env.get("PLAYWRIGHT_BROWSERS_PATH") or "")
    if "cursor-sandbox-cache" in pb:
        env.pop("PLAYWRIGHT_BROWSERS_PATH", None)
    # Always prefer playright's local profile when present. Ignore stale env paths
    # that point at another machine/user (e.g. /Users/averma/...).
    local_profile = root / "profiles" / "firefox-automation"
    env_profile = (env.get("FIREFOX_PROFILE_PATH") or "").strip()
    if local_profile.is_dir():
        if not env_profile or not Path(env_profile).is_dir() or "averma" in env_profile:
            env["FIREFOX_PROFILE_PATH"] = str(local_profile)
    elif env_profile and not Path(env_profile).is_dir():
        raise RuntimeError(
            f"FIREFOX_PROFILE_PATH does not exist: {env_profile}. "
            f"Create/login a profile at {local_profile} (see playright-automation/MIGRATION.md)."
        )
    # Prefer missing-only so re-runs resume safely.
    cmd = [
        env.get("NODE_BIN") or "node",
        str(runner),
        "--missing",
        cms_ref,
    ]
    print(
        f"[digen-videos] $ WAIT_READY=1 FIREFOX_PROFILE_PATH={env.get('FIREFOX_PROFILE_PATH', '(default)')} "
        f"CMS_STORIES_ROOT={cms_root} {' '.join(cmd)}"
    )
    proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
    video_count = _count_videos(videos_dir)
    if proc.returncode != 0:
        raise RuntimeError(
            f"playright Digen exited {proc.returncode} for story {cms_ref} "
            f"({video_count}/{scene_count} videos on disk). "
            "Images are saved; re-run with: "
            f"WAIT_READY=1 npm run run:cms:missing -- {cms_ref}"
        )
    video_report = media_report(story_asset_dir, "videos")
    if not video_report["complete"]:
        if not images_complete:
            print(
                f"[digen-videos] partial — {video_count} video(s) so far; "
                "Flow is still generating images, will catch up later"
            )
            print(
                f"PROGRESS [######################----]  90% · Digen videos · "
                f"{video_count}/{scene_count} mp4(s) (partial)"
            )
            return True
        raise RuntimeError(f"Digen outputs incomplete: {video_report}")
    if video_count <= 0:
        raise RuntimeError(
            f"playright Digen finished but wrote 0 videos for {cms_ref}. "
            "Check Firefox profile login (profiles/firefox-automation) and Digen UI."
        )

    print(f"[digen-videos] done — {video_count} video file(s) in {videos_dir}")
    print(
        f"PROGRESS [##########################]  96% · Digen videos · "
        f"{video_count}/{scene_count} mp4(s) in videos/"
    )
    if update_status:
        try:
            update_status(
                {
                    "status": "storyboard_running",
                    "story_meta": (
                        f"Digen videos: completed ({video_count}/{scene_count}) for {cms_ref}"
                    ),
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[digen-videos] status update failed: {exc}")
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate missing Digen videos for a CMS story folder"
    )
    parser.add_argument("story_dir", type=Path, help="Path to story asset folder")
    args = parser.parse_args()
    try:
        run_digen_videos_for_story(args.story_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
