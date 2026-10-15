"""Clearly labeled synthetic images for standalone samples. Not historical evidence."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2] / "examples" / "documentary" / "assets"


def _card(path: Path, title: str, body: str, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (1600, 900), color)
    draw = ImageDraw.Draw(image)
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    title_font = ImageFont.truetype(font_path, 72)
    body_font = ImageFont.truetype(font_path, 40)
    draw.rectangle((70, 70, 1530, 830), outline=(244, 240, 232), width=6)
    draw.text((140, 240), "SYNTHETIC DEMONSTRATION", fill=(226, 196, 138), font=body_font)
    draw.text((140, 400), title, fill=(244, 240, 232), font=title_font)
    draw.text((140, 510), body, fill=(226, 196, 138), font=body_font)
    image.save(path)


def ensure_assets() -> dict[str, Path]:
    files = {
        "photo_a": ROOT / "photo-a.png",
        "photo_b": ROOT / "photo-b.png",
        "photo_c": ROOT / "photo-c.png",
        "before": ROOT / "before.png",
        "after": ROOT / "after.png",
        "scene_a": ROOT / "scene-a.png",
        "scene_b": ROOT / "scene-b.png",
        "scene_c": ROOT / "scene-c.png",
        "scan": ROOT / "document-scan.png",
    }
    _card(files["photo_a"], "River gate", "Fixture photograph A", (28, 48, 62))
    _card(files["photo_b"], "Market lane", "Fixture photograph B", (48, 36, 28))
    _card(files["photo_c"], "Bridge detail", "Fixture photograph C", (24, 42, 36))
    _card(files["before"], "BEFORE — low bank", "Different viewpoint from the after fixture", (36, 42, 58))
    _card(files["after"], "AFTER — raised bank", "Not a registered overlay of the before fixture", (58, 44, 32))
    _card(files["scene_a"], "Scene 1", "Illustrative reconstruction", (32, 28, 40))
    _card(files["scene_b"], "Scene 2", "Illustrative reconstruction", (40, 32, 28))
    _card(files["scene_c"], "Scene 3", "Illustrative reconstruction", (28, 36, 40))
    scan = Image.new("RGB", (1400, 1800), (236, 228, 214))
    draw = ImageDraw.Draw(scan)
    draw.text((80, 60), "SYNTHETIC DOCUMENT", fill=(40, 32, 24))
    draw.rectangle((120, 520, 1280, 860), outline=(140, 90, 40), width=6)
    draw.text((160, 600), "The river changed course after the flood.", fill=(40, 32, 24))
    scan.save(files["scan"])
    pdf = ROOT / "document-demo.pdf"
    _write_pdf(pdf)
    files["pdf"] = pdf
    return files


def _write_pdf(path: Path) -> None:
    stream = b"BT /F1 22 Tf 72 700 Td (SYNTHETIC DEMONSTRATION) Tj ET BT /F1 20 Tf 72 640 Td (The river changed course after the flood.) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    chunks = [b"%PDF-1.4\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(part) for part in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref = sum(len(part) for part in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    chunks.append(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    path.write_bytes(b"".join(chunks))
