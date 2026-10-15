"""Shape Hindi and English with the local Devanagari Sangam MN font via CoreText.

Pillow is used to composite those masks. It is not asked to shape Devanagari.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from pathlib import Path

from PIL import Image

LAB = Path(__file__).resolve().parents[2]
SWIFT = Path(__file__).with_name("shape_text.swift")
CACHE = LAB / "output" / ".text-cache"
BINARY = CACHE / "timeline-shaper"


class TextLayoutError(RuntimeError):
    pass


def _binary() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    if not BINARY.exists() or BINARY.stat().st_mtime < SWIFT.stat().st_mtime:
        subprocess.run(
            ["swiftc", "-module-cache-path", str(CACHE / "modules"), str(SWIFT), "-o", str(BINARY)],
            check=True,
        )
    return BINARY


def shape(text: str, size: int, max_width: int, max_height: int, *, align: str = "center") -> Image.Image:
    digest = hashlib.sha256(f"{text}|{size}|{max_width}|{max_height}|{align}".encode("utf-8")).hexdigest()[:20]
    target = CACHE / "timeline" / f"{digest}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.is_file():
        temporary = target.with_name(f".{target.stem}.{os.getpid()}.{uuid.uuid4().hex}.tmp.png")
        result = subprocess.run(
            [str(_binary()), text, str(size), str(max_width), str(max_height), align, str(temporary)],
            capture_output=True,
            text=True,
        )
        if result.returncode == 3:
            temporary.unlink(missing_ok=True)
            raise TextLayoutError(result.stderr.strip() or "Text does not fit the timeline box")
        if result.returncode != 0 or not temporary.is_file():
            temporary.unlink(missing_ok=True)
            detail = (result.stderr or result.stdout or "text shaper failed").strip()
            raise TextLayoutError(detail)
        os.replace(temporary, target)
    with Image.open(target) as image:
        return image.convert("RGBA")


def colorize(image: Image.Image, color: str) -> Image.Image:
    alpha = image.getchannel("A")
    tinted = Image.new("RGBA", image.size, color)
    tinted.putalpha(alpha)
    return tinted
