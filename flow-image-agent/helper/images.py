"""Verify downloads and atomically place scene images under story/images/."""

from __future__ import annotations

import os
import shutil
import struct
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .prompts import scene_filename_stem
from .security import SecurityError, resolve_under_roots

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None  # type: ignore


class ImageValidationError(Exception):
    pass


@dataclass
class SavedImage:
    path: Path
    format: str
    width: int
    height: int
    size_bytes: int


SIGNATURES = {
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "webp": (b"RIFF",),  # also check WEBP at offset 8
}

EXT_FOR_FORMAT = {"jpeg": ".jpg", "png": ".png", "webp": ".webp"}


def sniff_format(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise ImageValidationError("Unrecognized or unsupported image format")


def _jpeg_size(data: bytes) -> tuple[int, int]:
    i = 2
    while i < len(data) - 8:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        if marker == 0xD9:
            break
        if marker in (0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0x01) or marker == 0xD8:
            i += 2
            continue
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + length
    raise ImageValidationError("Could not read JPEG dimensions")


def _png_size(data: bytes) -> tuple[int, int]:
    if len(data) < 24:
        raise ImageValidationError("PNG too small")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _webp_size(data: bytes) -> tuple[int, int]:
    if Image is not None:
        from io import BytesIO

        with Image.open(BytesIO(data)) as im:
            return im.size
    # VP8X
    if len(data) >= 30 and data[12:16] == b"VP8X":
        w = 1 + int.from_bytes(data[24:27], "little")
        h = 1 + int.from_bytes(data[27:30], "little")
        return w, h
    raise ImageValidationError("Could not read WebP dimensions without Pillow")


def decode_dimensions(data: bytes, fmt: str) -> tuple[int, int]:
    if Image is not None:
        from io import BytesIO

        with Image.open(BytesIO(data)) as im:
            return im.size
    if fmt == "jpeg":
        return _jpeg_size(data)
    if fmt == "png":
        return _png_size(data)
    if fmt == "webp":
        return _webp_size(data)
    raise ImageValidationError(f"Unsupported format: {fmt}")


def validate_download_bytes(
    data: bytes,
    *,
    min_width: int = 2048,
    aspect: float = 16 / 9,
    aspect_tolerance: float = 0.08,
) -> tuple[str, int, int]:
    if not data:
        raise ImageValidationError("Downloaded file is empty")
    if data.endswith(b".crdownload") or len(data) < 32:
        raise ImageValidationError("Download appears incomplete")
    fmt = sniff_format(data)
    width, height = decode_dimensions(data, fmt)
    if width < min_width:
        raise ImageValidationError(
            f"Image width {width}px is below expected 2K landscape minimum ({min_width}px)"
        )
    if height <= 0:
        raise ImageValidationError("Invalid image height")
    ratio = width / height
    if abs(ratio - aspect) > aspect_tolerance:
        raise ImageValidationError(
            f"Aspect ratio {ratio:.4f} is not within tolerance of {aspect:.4f} (16:9)"
        )
    return fmt, width, height


def validate_download_file(
    path: Path,
    *,
    min_width: int = 2048,
    aspect: float = 16 / 9,
    aspect_tolerance: float = 0.08,
) -> tuple[str, int, int]:
    if path.suffix.lower() == ".crdownload":
        raise ImageValidationError("Download still incomplete (.crdownload)")
    if not path.is_file():
        raise ImageValidationError(f"Download path not found: {path}")
    data = path.read_bytes()
    return validate_download_bytes(
        data, min_width=min_width, aspect=aspect, aspect_tolerance=aspect_tolerance
    )


def atomic_place(
    source: Path,
    dest_dir: Path,
    scene: int,
    *,
    roots: list[Path],
    overwrite: bool = False,
    min_width: int = 2048,
    aspect_tolerance: float = 0.08,
    delete_source: bool = False,
) -> SavedImage:
    """
    Validate source image and place as NNN.ext under dest_dir.
    Never silently overwrite an existing scene image.
    """
    dest_dir = resolve_under_roots(dest_dir, roots)
    source = Path(source).expanduser().resolve(strict=False)
    if not source.is_file():
        raise ImageValidationError(f"Source file missing: {source}")

    # Source may be in Downloads (outside story roots) — that is intentional.
    data = source.read_bytes()
    fmt, width, height = validate_download_bytes(
        data, min_width=min_width, aspect_tolerance=aspect_tolerance
    )
    ext = EXT_FOR_FORMAT[fmt]
    stem = scene_filename_stem(scene)
    final_path = dest_dir / f"{stem}{ext}"

    # Conflict with any existing scene image (any extension).
    for other_ext in EXT_FOR_FORMAT.values():
        existing = dest_dir / f"{stem}{other_ext}"
        if existing.is_file():
            if not overwrite:
                raise ImageValidationError(
                    f"Refusing to overwrite existing image: {existing}. "
                    "Use regenerate=true to replace."
                )
            if existing.resolve() != final_path.resolve():
                existing.unlink()

    dest_dir.mkdir(parents=True, exist_ok=True)
    # Ensure dest_dir still under roots after mkdir
    resolve_under_roots(dest_dir, roots)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{stem}.", suffix=ext, dir=str(dest_dir))
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, final_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    if delete_source and source.exists() and source.resolve() != final_path.resolve():
        try:
            source.unlink()
        except OSError:
            pass

    return SavedImage(
        path=final_path,
        format=fmt,
        width=width,
        height=height,
        size_bytes=final_path.stat().st_size,
    )


def copy_validated_download(
    source: Path,
    dest_dir: Path,
    scene: int,
    roots: list[Path],
    **kwargs,
) -> SavedImage:
    return atomic_place(source, dest_dir, scene, roots=roots, delete_source=False, **kwargs)
