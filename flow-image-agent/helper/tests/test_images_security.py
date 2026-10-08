from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from helper.images import ImageValidationError, atomic_place, validate_download_bytes
from helper.security import SecurityError, resolve_under_roots


def _make_jpeg(path: Path, width: int = 2752, height: int = 1536) -> Path:
    img = Image.new("RGB", (width, height), color=(40, 80, 120))
    img.save(path, format="JPEG", quality=92)
    return path


def test_validate_2k_landscape(tmp_path: Path):
    path = _make_jpeg(tmp_path / "in.jpg")
    fmt, w, h = validate_download_bytes(path.read_bytes())
    assert fmt == "jpeg"
    assert w == 2752
    assert h == 1536


def test_reject_incomplete_and_small(tmp_path: Path):
    with pytest.raises(ImageValidationError):
        validate_download_bytes(b"")
    small = _make_jpeg(tmp_path / "small.jpg", width=1280, height=720)
    with pytest.raises(ImageValidationError, match="below expected"):
        validate_download_bytes(small.read_bytes())


def test_reject_wrong_aspect(tmp_path: Path):
    path = _make_jpeg(tmp_path / "square.jpg", width=2048, height=2048)
    with pytest.raises(ImageValidationError, match="Aspect ratio"):
        validate_download_bytes(path.read_bytes())


def test_atomic_place_and_no_silent_overwrite(tmp_path: Path):
    roots = [tmp_path]
    dest = tmp_path / "story" / "images"
    dest.mkdir(parents=True)
    src = _make_jpeg(tmp_path / "dl.jpg")
    saved = atomic_place(src, dest, 1, roots=roots)
    assert saved.path.name == "001.jpg"
    assert saved.path.is_file()
    with pytest.raises(ImageValidationError, match="Refusing to overwrite"):
        atomic_place(src, dest, 1, roots=roots, overwrite=False)
    saved2 = atomic_place(src, dest, 1, roots=roots, overwrite=True)
    assert saved2.path.name == "001.jpg"


def test_path_traversal_blocked(tmp_path: Path):
    roots = [tmp_path / "stories"]
    roots[0].mkdir()
    with pytest.raises(SecurityError):
        resolve_under_roots(tmp_path / "stories" / ".." / "outside", roots)


def test_symlink_escape_blocked(tmp_path: Path):
    root = tmp_path / "stories"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = root / "evil"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not available")
    with pytest.raises(SecurityError):
        resolve_under_roots(link / "file.jpg", [root])


def test_download_correlation_identity_fields(tmp_path: Path):
    """Helper save requires an explicit download_path (not newest-file heuristics)."""
    roots = [tmp_path]
    dest = tmp_path / "images"
    dest.mkdir()
    correct = _make_jpeg(tmp_path / "scene1_2K.jpg")
    decoy = _make_jpeg(tmp_path / "newer_decoy.jpg", width=2752, height=1536)
    # Touch decoy as newer
    decoy.write_bytes(decoy.read_bytes())
    saved = atomic_place(correct, dest, 12, roots=roots)
    assert saved.path.name == "012.jpg"
    assert not (dest / "newer_decoy.jpg").exists()
