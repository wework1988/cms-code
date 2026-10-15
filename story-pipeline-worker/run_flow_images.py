#!/usr/bin/env python3
"""
Run flow-image-agent for all scenes of a CMS story folder (sequential).

Called from run_storyboard after image-prompts are synced. Soft-failure friendly:
callers should catch exceptions and still mark storyboard_done.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WORKER_ROOT = Path(__file__).resolve().parent
DEFAULT_AGENT_ROOT = WORKER_ROOT.parent / "flow-image-agent"
HELPER_PORT = int(os.environ.get("FLOW_IMAGE_HELPER_PORT") or "8765")
HELPER_URL = f"http://127.0.0.1:{HELPER_PORT}"


def flow_images_enabled() -> bool:
    raw = (os.environ.get("FLOW_IMAGES") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def agent_root() -> Path:
    override = (os.environ.get("FLOW_IMAGE_AGENT_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return DEFAULT_AGENT_ROOT.resolve()


def _helper_healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{HELPER_URL}/health", timeout=1.5) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _stop_helper_on_port() -> None:
    """Stop a previous helper so the next run picks up STORY_ASSET_ROOT in config."""
    if not _helper_healthy():
        return
    print(f"[flow-images] restarting helper on port {HELPER_PORT} for current story roots…")
    try:
        out = subprocess.check_output(
            ["lsof", f"-tiTCP:{HELPER_PORT}", "-sTCP:LISTEN"],
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    for pid in out.split():
        try:
            os.kill(int(pid), signal.SIGTERM)
        except (ProcessLookupError, ValueError, PermissionError):
            pass
    time.sleep(1.0)


def run_flow_images_for_story(
    story_asset_dir: Path,
    *,
    story_id: int | str | None = None,
    update_status=None,
) -> bool:
    """
    Generate all Flow images for story_asset_dir (expects image-prompts/…).

    Returns True on success, False if skipped. Raises on hard runner failure
    (caller may catch for soft-fail).
    """
    if not flow_images_enabled():
        print("[flow-images] skipped (FLOW_IMAGES=0)")
        return False

    story_asset_dir = Path(story_asset_dir).resolve()
    prompts = story_asset_dir / "image-prompts" / "image-prompts-only.txt"
    if not prompts.is_file():
        print(f"[flow-images] skipped — no prompts at {prompts}")
        return False

    root = agent_root()
    runner = root / "scripts" / "run_images.sh"
    if not runner.is_file():
        print(f"[flow-images] skipped — agent not found at {root}")
        return False

    story_key = story_asset_dir.name
    print(f"[flow-images] story={story_key} path={story_asset_dir}")
    print("[flow-images] generating ALL scenes one-by-one via Flow (Nano Banana 2.1 · 16:9 · 2K)…")
    print(
        f"PROGRESS [##################--------]  72% · Flow images · "
        f"starting all scenes for {story_key}"
    )

    if update_status:
        try:
            update_status(
                {
                    "status": "storyboard_running",
                    "story_meta": f"Flow images: starting all scenes for {story_key}",
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[flow-images] status update failed: {exc}")

    env = os.environ.copy()
    # PHP/exec PATH often omits Homebrew — required for node/playwright.
    homebrew = "/opt/homebrew/bin:/usr/local/bin"
    env["PATH"] = f"{homebrew}:{env.get('PATH') or '/usr/bin:/bin'}"
    for candidate in ("/opt/homebrew/bin/node", "/usr/local/bin/node"):
        if Path(candidate).is_file():
            env["NODE_BIN"] = candidate
            break
    asset_root = (env.get("STORY_ASSET_ROOT") or "").strip()
    if not asset_root:
        # Parent of category folder (…/general/165-foo → …)
        env["STORY_ASSET_ROOT"] = str(story_asset_dir.parent.parent)

    cmd = ["bash", str(runner), story_key, "--all"]
    print(f"[flow-images] $ PATH=… NODE_BIN={env.get('NODE_BIN', 'auto')} {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
    if proc.returncode != 0 and os.environ.get("PIPELINE_MANAGED") != "1":
        # Helper may have been started earlier without STORY_ASSET_ROOT — restart once.
        print("[flow-images] first attempt failed; restarting helper with current story roots…")
        _stop_helper_on_port()
        proc = subprocess.run(cmd, cwd=str(root), env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            f"flow-image-agent exited {proc.returncode} for story {story_key}. "
            "Storyboard text assets are saved; re-run images later to resume."
        )

    from pipeline_validation import media_report
    report = media_report(story_asset_dir, "images")
    if not report["complete"]:
        raise RuntimeError(f"Flow outputs incomplete: {report}")

    images_dir = story_asset_dir / "images"
    count = 0
    if images_dir.is_dir():
        count = sum(
            1
            for p in images_dir.iterdir()
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
            and p.stem.isdigit()
        )
    print(f"[flow-images] done — {count} image file(s) in {images_dir}")
    print(
        f"PROGRESS [####################------]  86% · Flow images · "
        f"completed ({count} files) for {story_key}"
    )
    if update_status:
        try:
            update_status(
                {
                    "status": "storyboard_running",
                    "story_meta": f"Flow images: completed ({count} files) for {story_key}",
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[flow-images] status update failed: {exc}")
    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate all Flow images for a CMS story folder")
    parser.add_argument("story_dir", type=Path, help="Path to story asset folder")
    args = parser.parse_args()
    try:
        run_flow_images_for_story(args.story_dir)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
