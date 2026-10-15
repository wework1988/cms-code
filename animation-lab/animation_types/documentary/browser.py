"""Launch the isolated documentary browser renderer."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from animation_core.outputs import replace_verified, verify_mp4

LAB = Path(__file__).resolve().parents[2]
RENDER = LAB / "documentary-browser" / "render.mjs"


def _contact_sheet(still_dir: Path, destination: Path) -> None:
    frames = sorted(still_dir.glob("beat-*.jpg")) + sorted(still_dir.glob("hold.jpg"))
    if not frames:
        return
    thumbs = []
    for frame in frames:
        with Image.open(frame) as source:
            card = source.convert("RGB").resize((640, 360), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (640, 420), (16, 22, 30))
        canvas.paste(card, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((16, 372), frame.stem, fill=(244, 240, 232))
        thumbs.append(canvas)
    columns = 2
    rows = (len(thumbs) + 1) // 2
    sheet = Image.new("RGB", (columns * 640, rows * 420), (11, 16, 22))
    for index, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((index % columns) * 640, (index // columns) * 420))
    sheet.save(destination)


def render_compiled(plan: dict, output_dir: Path) -> dict:
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    plan_path = output_dir / "compiled-plan.json"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    env = os.environ.copy()
    env.pop("PLAYWRIGHT_CHROME_CDP", None)
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(Path.home() / "Library/Caches/ms-playwright")
    subprocess.run(
        ["node", str(RENDER), "--plan", str(plan_path), "--output-dir", str(output_dir)],
        cwd=str(LAB / "documentary-browser"),
        env=env,
        check=True,
    )
    partial = output_dir / "documentary.partial.mp4"
    destination = output_dir / "sample.mp4"
    verification = replace_verified(
        partial,
        destination,
        lambda path: verify_mp4(
            path,
            width=1920,
            height=1080,
            fps=int(plan["fps"]),
            duration=float(plan["duration_seconds"]),
        ),
    )
    _contact_sheet(output_dir / "frames", output_dir / "contact-sheet.jpg")
    (output_dir / "verification.json").write_text(json.dumps(verification, indent=2) + "\n", encoding="utf-8")
    return verification
