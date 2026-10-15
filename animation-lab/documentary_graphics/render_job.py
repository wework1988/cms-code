"""Shared browser capture and FFmpeg composite. Both graphics modules call this."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PIL import Image

from .compose import composite, contact_sheet, source_fingerprint, verify_output

LAB = Path(__file__).resolve().parents[1]
RENDER = Path(__file__).resolve().parent / "browser" / "render.mjs"
FONT_DIR = LAB / "documentary-browser" / "assets" / "fonts"
REQUIRED_FONTS = ("NotoSans-Regular.woff2", "NotoSansDevanagari-Regular.woff2")


def require_fonts() -> Path:
    missing = [name for name in REQUIRED_FONTS if not (FONT_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Bundled fonts are missing: {', '.join(missing)}")
    return FONT_DIR


def reject_annotated_source(source: Path) -> None:
    if source.name == "scene-1-overlay.mp4":
        raise RuntimeError("Refusing to composite onto an already annotated video. Use the original source.")
    if source.parent.name != "fixtures" and (source.parent / "verification.json").is_file():
        raise RuntimeError("Refusing to composite onto a previous graphics export. Use the original source or a fixture plate.")


def render_job(*, source: Path, compiled: dict, destination: Path, raw_plan: dict) -> dict:
    require_fonts()
    reject_annotated_source(source)
    before = source_fingerprint(source)
    folder = destination.parent
    folder.mkdir(parents=True, exist_ok=True)
    compiled_path = folder / "compiled-plan.json"
    compiled_path.write_text(json.dumps(compiled, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "sample-plan.json").write_text(json.dumps(raw_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    frame_dir = folder / "overlay-frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.pop("PLAYWRIGHT_CHROME_CDP", None)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "Library/Caches/ms-playwright")
    subprocess.run(
        ["node", str(RENDER), "--plan", str(compiled_path), "--output-dir", str(frame_dir)],
        cwd=str(LAB),
        env=env,
        check=True,
    )
    with Image.open(frame_dir / "overlay_0001.png") as image:
        if image.mode != "RGBA" or image.getpixel((0, 0))[3] != 0:
            raise RuntimeError("Overlay capture did not produce a transparent frame")
    graphic = compiled["graphics"][0]
    hold_frame = int((graphic["start"] + graphic["reveal"] + float(graphic.get("label_fade") or 0) + 0.15) * compiled["fps"])
    with Image.open(frame_dir / f"overlay_{hold_frame + 1:04d}.png") as image:
        if image.mode != "RGBA" or not any(pixel[3] > 12 for pixel in image.getdata()):
            raise RuntimeError("The hold frame has no visible overlay")
    media = {
        "width": compiled["width"],
        "height": compiled["height"],
        "fps": compiled["fps"],
        "frames": compiled["frames"],
        "has_audio": compiled["has_audio"],
    }
    if destination.exists():
        destination.unlink()
    composite(source, frame_dir, destination, media)
    if source_fingerprint(source) != before:
        destination.unlink(missing_ok=True)
        raise RuntimeError("The source video changed during export")
    verification = verify_output(destination, media)
    contact_sheet(destination, graphic, folder / "contact-sheet.jpg", media)
    placement = graphic.get("placement") or {}
    report = {
        "output": str(destination),
        "width": verification["width"],
        "height": verification["height"],
        "fps": verification["fps"],
        "frames": verification["frames"],
        "duration": verification["duration"],
        "has_audio": verification["has_audio"],
        "pix_fmt": verification["pix_fmt"],
        "source_unchanged": True,
        "transparent_overlay": True,
        "preset": compiled.get("preset"),
        "treatment": graphic.get("treatment"),
        "factual_claim": compiled.get("factual_claim", False),
        "timing_source": compiled.get("timing_source"),
        "sample_note": compiled.get("sample_note") or "",
        "placement": placement.get("candidate") or graphic.get("placement_mode"),
        "heuristic_placement": bool(placement.get("heuristic")),
    }
    (folder / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
