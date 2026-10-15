"""MP4 verification with the local FFmpeg binary. No remote calls."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg


def decoded_frame_count(log: str) -> int | None:
    """Use the final decoded frame count, not the first progress line."""
    matches = list(re.finditer(r"frame=\s*(\d+)", log))
    return int(matches[-1].group(1)) if matches else None


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def replace_verified(partial: Path, destination: Path, verify) -> dict:
    """Keep destination untouched when the new file fails verification."""
    try:
        metadata = verify(partial)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    partial.replace(destination)
    return metadata


def verify_mp4(path: Path, *, width: int, height: int, fps: int, duration: float) -> dict:
    """Decode the whole file and check container basics. Raises RuntimeError on failure."""
    if not path.is_file() or path.stat().st_size < 1000:
        raise RuntimeError(f"Video is missing or empty: {path.name}")
    expected = int(round(duration * fps))
    probe = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    info = (probe.stderr or "") + (probe.stdout or "")
    if f"{width}x{height}" not in info:
        raise RuntimeError(f"Expected {width}x{height}. Probe: {info[-500:]}")
    if "yuv420p" not in info:
        raise RuntimeError(f"Expected yuv420p. Probe: {info[-500:]}")
    if "h264" not in info and "H.264" not in info:
        raise RuntimeError(f"Expected H.264. Probe: {info[-500:]}")
    if not re.search(rf"\b{fps}\s*fps\b", info):
        raise RuntimeError(f"Expected {fps} fps")
    decode = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    log = (decode.stderr or "") + (decode.stdout or "")
    if decode.returncode != 0:
        raise RuntimeError(f"Full decode failed: {log[-400:]}")
    frames = decoded_frame_count(log)
    if frames != expected:
        raise RuntimeError(f"Expected {expected} frames, decoded {frames}")
    head = path.read_bytes()[:65536]
    if head[4:8] != b"ftyp" or b"moov" not in head:
        raise RuntimeError("Expected faststart (moov before mdat)")
    return {
        "width": width,
        "height": height,
        "fps": fps,
        "duration_seconds": duration,
        "frames": frames,
        "pix_fmt": "yuv420p",
        "codec": "h264",
        "faststart": True,
        "decoded": True,
    }
