#!/usr/bin/env python3
"""Run ElevenLabs TTS via automation repo (read-only subprocess)."""

from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path


def resolve_elevenlabs_repo(automation_repo: Path) -> Path:
    """
    Find the repo that contains elevenlabs-audio/generate_audio.py.

    AUTOMATION_REPO may point at myresearch2 while elevenlabs-audio lives in the
    research-story automation repo (STORY_ASSET_MIRROR parent).
    """
    candidates: list[Path] = [automation_repo]
    mirror = (os.environ.get("STORY_ASSET_MIRROR") or "").strip()
    if mirror:
        candidates.append(Path(mirror).expanduser().parent)
    for repo in candidates:
        script = repo / "elevenlabs-audio" / "generate_audio.py"
        if script.is_file():
            return repo.resolve()
    return automation_repo.resolve()


def elevenlabs_python(automation_repo: Path) -> Path | None:
    repo = resolve_elevenlabs_repo(automation_repo)
    venv_py = repo / "elevenlabs-audio" / ".venv" / "bin" / "python"
    if venv_py.is_file():
        return venv_py
    return None


def generate_eleven_labs(
    automation_repo: Path,
    full_story: Path,
    output_dir: Path,
    api_key: str,
    voice_id: str | None = None,
    language_code: str | None = None,
) -> Path:
    """
    Generate narration MP3s into output_dir (stories/<slug>/eleven-labs/).

    Returns output_dir on success.
    """
    repo = resolve_elevenlabs_repo(automation_repo)
    script = repo / "elevenlabs-audio" / "generate_audio.py"
    if not script.is_file():
        raise FileNotFoundError(f"generate_audio.py not found: {script}")
    python = elevenlabs_python(automation_repo)
    if python is None:
        raise RuntimeError(
            f"ElevenLabs venv not found under {repo / 'elevenlabs-audio'} — "
            "run ./elevenlabs-audio/setup.sh in the automation repo"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["ELEVENLABS_API_KEY"] = api_key

    cmd = [
        str(python),
        str(script),
        str(full_story),
        "--output-dir",
        str(output_dir),
        "--mode",
        "full",
    ]
    if voice_id:
        cmd.extend(["--voice-id", voice_id])
    if language_code:
        cmd.extend(["--language-code", language_code])
    subprocess.run(cmd, env=env, check=True, cwd=str(repo))
    return output_dir


def collect_mp3_payload(output_dir: Path) -> list[dict[str, str]]:
    """Build Drupal update payload: list of {filename, content_base64}."""
    files: list[dict[str, str]] = []
    for mp3 in sorted(output_dir.glob("*.mp3")):
        files.append(
            {
                "filename": mp3.name,
                "content_base64": base64.b64encode(mp3.read_bytes()).decode("ascii"),
            }
        )
    return files
