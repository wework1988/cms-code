"""Render the standalone documentary-graphics samples. No CMS and no model calls."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
REPO = LAB.parent
if str(LAB) not in sys.path:
    sys.path.insert(0, str(LAB))

from cinematic_overlays.compile import compile_overlay  # noqa: E402
from cinematic_overlays.schema import validate_plan as validate_overlay  # noqa: E402
from documentary_graphics.compose import probe_video  # noqa: E402
from documentary_graphics.render_job import render_job  # noqa: E402
from documentary_typography.compile import compile_typography  # noqa: E402
from documentary_typography.schema import validate_plan as validate_type  # noqa: E402
from animation_core.outputs import ffmpeg_exe  # noqa: E402

OUTPUT = LAB / "output" / "documentary-graphics"
SOURCE = REPO / "general" / "152-priso-story-updated" / "video" / "scene_1.mp4"
JOBS = (
    ("prison-callout", LAB / "cinematic_overlays/samples/prison-callout.json"),
    ("prison-impact-phrase", LAB / "documentary_typography/samples/prison-impact-phrase.json"),
    ("prison-title", LAB / "documentary_typography/samples/prison-title.json"),
    ("demo-location-title", LAB / "documentary_typography/samples/demo-location-title.json"),
    ("demo-date-year", LAB / "documentary_typography/samples/demo-date-year.json"),
    ("demo-key-number", LAB / "documentary_typography/samples/demo-key-number.json"),
    ("demo-portrait", LAB / "documentary_typography/samples/demo-portrait.json"),
    ("demo-impact-word", LAB / "documentary_typography/samples/demo-impact-word.json"),
    ("demo-quote", LAB / "documentary_typography/samples/demo-quote.json"),
    ("demo-spotlight", LAB / "cinematic_overlays/samples/demo-spotlight.json"),
    ("demo-key-fact", LAB / "cinematic_overlays/samples/demo-key-fact.json"),
    ("demo-evidence", LAB / "cinematic_overlays/samples/demo-evidence.json"),
    ("demo-route", LAB / "cinematic_overlays/samples/demo-route.json"),
    ("demo-measurement", LAB / "cinematic_overlays/samples/demo-measurement.json"),
)


def make_crop() -> None:
    from PIL import Image, ImageDraw, ImageFont
    path = LAB / "documentary_graphics" / "samples" / "assets" / "demo-crop.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (960, 540), (54, 44, 32))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 36, 924, 504), outline=(196, 165, 116), width=6)
    font_path = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
    font = ImageFont.truetype(str(font_path), 72) if font_path.is_file() else ImageFont.load_default()
    draw.text((180, 220), "FICTIONAL CROP", fill=(243, 234, 215), font=font)
    image.save(path)


def make_plate(path: Path, width: int, height: int, fps: int, frames: int) -> None:
    if path.is_file():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=0x14181e:s={width}x{height}:r={fps}:d={frames / fps:.3f}",
            "-frames:v", str(frames),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an",
            str(path),
        ],
        check=True,
    )


def resolve_input(value: str, fixtures: dict[str, Path]) -> Path:
    if value == "fixture:landscape":
        return fixtures["landscape"]
    if value == "fixture:portrait":
        return fixtures["portrait"]
    path = Path(value)
    if path.is_file():
        return path.resolve()
    candidate = (REPO / value).resolve()
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"Source video is missing: {value}")


def render_one(plan_path: Path, folder: Path, fixtures: dict[str, Path]) -> dict:
    raw = json.loads(plan_path.read_text(encoding="utf-8"))
    source = resolve_input(raw["input"], fixtures)
    media = probe_video(source)
    if raw.get("module") == "documentary_typography":
        compiled = compile_typography(validate_type(raw, duration=media["duration"]), media)
    else:
        compiled = compile_overlay(validate_overlay(raw, duration=media["duration"]), media)
    folder.mkdir(parents=True, exist_ok=True)
    return render_job(source=source, compiled=compiled, destination=folder / f"{folder.name}.mp4", raw_plan=raw)


def original_reference(folder: Path) -> None:
    media = probe_video(SOURCE)
    payload = {
        "role": "clean_original",
        "path": str(SOURCE),
        "note": "Unmodified source. Every prison sample composites onto this file and writes a new MP4.",
        "width": media["width"],
        "height": media["height"],
        "fps": media["fps"],
        "frames": media["frames"],
        "duration": media["duration"],
        "has_audio": media["has_audio"],
    }
    (folder / "original-reference.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    stills = folder / "original-stills"
    stills.mkdir(parents=True, exist_ok=True)
    for name, seconds in (("open", 0.2), ("middle", 2.5), ("close", 4.6)):
        subprocess.run(
            [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-ss", str(seconds), "-i", str(SOURCE), "-frames:v", "1", str(stills / f"{name}.jpg")],
            check=True,
        )


def render_samples(only: str | None = None) -> list[dict]:
    make_crop()
    fixtures = {
        "landscape": OUTPUT / "fixtures" / "landscape.mp4",
        "portrait": OUTPUT / "fixtures" / "portrait.mp4",
    }
    make_plate(fixtures["landscape"], 1920, 1080, 24, 108)
    make_plate(fixtures["portrait"], 1080, 1920, 24, 108)
    original_reference(OUTPUT)
    reports = []
    for slug, plan in JOBS:
        if only and slug != only:
            continue
        print(slug, flush=True)
        reports.append(render_one(plan, OUTPUT / slug, fixtures))
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render documentary graphics samples")
    parser.add_argument("command", choices=["render-samples"])
    parser.add_argument("--only", default="")
    args = parser.parse_args(argv)
    reports = render_samples(args.only or None)
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
