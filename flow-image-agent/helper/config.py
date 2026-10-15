"""Load helper configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config.json"
EXAMPLE_CONFIG_PATH = PACKAGE_ROOT / "config.example.json"


def _default_roots() -> list[str]:
    cms = PACKAGE_ROOT.parent
    return [
        str(cms / "general"),
        str(cms / "crime"),
        str(cms / "cms-generate-stories" / "general"),
        str(cms / "cms-generate-stories" / "crime"),
        str(cms / "cms-generate-stories" / "english"),
        str(cms / "cms-generate-stories" / "god_story"),
    ]


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = path or Path(os.environ.get("FLOW_IMAGE_AGENT_CONFIG") or DEFAULT_CONFIG_PATH)
    data: dict[str, Any] = {
        "host": "127.0.0.1",
        "port": 8765,
        "story_roots": _default_roots(),
        "allowed_origins": ["chrome-extension://*"],
        "model": "Nano Banana 2.1",
        "aspect_ratio": "16:9",
        "outputs_per_prompt": 1,
        "download_variant": "2K Upscaled",
        "min_landscape_width": 2048,
        "aspect_tolerance": 0.08,
        "token_file": str(PACKAGE_ROOT / ".local" / "pairing-token"),
        "state_dir": str(PACKAGE_ROOT / ".local" / "state"),
    }
    if EXAMPLE_CONFIG_PATH.is_file() and not cfg_path.is_file():
        # Prefer example as template values for relative roots when no config yet.
        example = json.loads(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
        for key in ("model", "aspect_ratio", "outputs_per_prompt", "download_variant",
                    "min_landscape_width", "aspect_tolerance", "host", "port"):
            if key in example:
                data[key] = example[key]

    if cfg_path.is_file():
        loaded = json.loads(cfg_path.read_text(encoding="utf-8"))
        data.update(loaded)

    roots: list[Path] = []
    for raw in data.get("story_roots") or _default_roots():
        p = Path(raw)
        if not p.is_absolute():
            p = (PACKAGE_ROOT / p).resolve()
        else:
            p = p.expanduser().resolve()
        roots.append(p)

    # Worker/CMS jobs set STORY_ASSET_ROOT — include it so discovery finds sync'd stories.
    asset_root = (os.environ.get("STORY_ASSET_ROOT") or "").strip()
    if asset_root:
        root = Path(asset_root).expanduser().resolve()
        if root not in roots:
            roots.append(root)
        for cat in ("general", "crime", "english", "god_story"):
            cat_root = root / cat
            if cat_root not in roots:
                roots.append(cat_root)

    data["story_roots_resolved"] = roots
    data["token_file"] = str(Path(data["token_file"]).expanduser())
    if not Path(data["token_file"]).is_absolute():
        data["token_file"] = str((PACKAGE_ROOT / data["token_file"]).resolve())
    data["state_dir"] = str(Path(data["state_dir"]).expanduser())
    if not Path(data["state_dir"]).is_absolute():
        data["state_dir"] = str((PACKAGE_ROOT / data["state_dir"]).resolve())
    return data
