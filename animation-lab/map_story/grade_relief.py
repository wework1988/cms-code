"""Grade Natural Earth relief so oceans are dark teal and land stays natural.

The source rasters are not modified. Documentary renders read the graded copies.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

LAB = Path(__file__).resolve().parent.parent


def grade_image(source: Path, dest: Path) -> None:
    image = Image.open(source).convert("RGB")
    pixels = np.asarray(image).astype(np.float32)
    red = pixels[:, :, 0]
    green = pixels[:, :, 1]
    blue = pixels[:, :, 2]
    luma = 0.30 * red + 0.52 * green + 0.18 * blue
    water = (blue > red + 6) & (blue + 8 > green) & (luma < 170)
    depth = np.clip((luma - 8.0) / 150.0, 0.0, 1.0)
    # #082831 at the dark end, #103E4A through the mids. Highlights stay restrained.
    target_r = 8.0 + depth * 14.0
    target_g = 36.0 + depth * 28.0
    target_b = 46.0 + depth * 32.0
    pixels[:, :, 0] = np.where(water, red * 0.18 + target_r * 0.82, red)
    pixels[:, :, 1] = np.where(water, green * 0.18 + target_g * 0.82, green)
    pixels[:, :, 2] = np.where(water, blue * 0.18 + target_b * 0.82, blue)
    land = ~water
    # A small warm pull on land, without raising contrast.
    pixels[:, :, 0] = np.where(land, np.clip(red * 1.03 + 2.0, 0, 255), pixels[:, :, 0])
    pixels[:, :, 2] = np.where(land, np.clip(blue * 0.94, 0, 255), pixels[:, :, 2])
    dest.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(pixels.astype(np.uint8)).save(dest, quality=88, optimize=True)


def grade_default_rasters() -> list[Path]:
    pairs = [
        (LAB / "assets/maps/south-asia-relief.jpg", LAB / "assets/maps/south-asia-relief-doc.jpg"),
        (LAB / "assets/maps/world/world-relief.jpg", LAB / "assets/maps/world/world-relief-doc.jpg"),
    ]
    written = []
    for source, dest in pairs:
        if not source.is_file():
            continue
        grade_image(source, dest)
        written.append(dest)
    return written


if __name__ == "__main__":
    for path in grade_default_rasters():
        print(path)
