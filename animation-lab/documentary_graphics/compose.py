"""Probe a source and composite transparent frames onto a copy of it."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import uuid
from pathlib import Path

from animation_core.outputs import decoded_frame_count, ffmpeg_exe

from .timing import clock_phase


def source_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def partial_output(destination: Path) -> Path:
    """Job-isolated temporary file. Two renders do not share this name."""
    return destination.with_name(f".{destination.name}.{os.getpid()}.{uuid.uuid4().hex}.partial.mp4")


def probe_video(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Source video is missing: {path}")
    probe = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    info = (probe.stderr or "") + (probe.stdout or "")
    size = re.search(r"(\d{2,5})x(\d{2,5})", info)
    rate = re.search(r"(\d+(?:\.\d+)?)\s*fps", info)
    if not size or not rate:
        raise RuntimeError("Could not read the source frame size or frame rate")
    rotation = re.search(r"rotation of (-?\d+(?:\.\d+)?)", info)
    if rotation and abs(float(rotation.group(1))) > 0.1:
        raise RuntimeError("This source has display rotation. The compositor will not reframe it.")
    decode = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    log = (decode.stderr or "") + (decode.stdout or "")
    frames = decoded_frame_count(log)
    if decode.returncode != 0 or not frames:
        raise RuntimeError("Could not decode the source video")
    fps = float(rate.group(1))
    pix = "yuv420p" if "yuv420p" in info else ""
    return {
        "width": int(size.group(1)),
        "height": int(size.group(2)),
        "fps": fps,
        "frames": frames,
        "duration": frames / fps,
        "has_audio": "Audio:" in info,
        "pix_fmt": pix,
        "sha256": source_fingerprint(path),
    }


def composite(source: Path, frames_dir: Path, destination: Path, media: dict) -> None:
    """Flatten transparent PNG frames over the source. Audio is copied only when the source has it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_output(destination)
    command = [
        ffmpeg_exe(), "-y", "-hide_banner",
        "-i", str(source),
        "-framerate", str(media["fps"]),
        "-start_number", "1",
        "-i", str(frames_dir / "overlay_%04d.png"),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
        "-map", "[v]",
        "-frames:v", str(media["frames"]),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        "-r", str(media["fps"]),
        "-movflags", "+faststart",
    ]
    if media["has_audio"]:
        command.extend(["-map", "0:a:0", "-c:a", "copy"])
    else:
        command.append("-an")
    command.append(str(temporary))
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise RuntimeError((result.stderr or result.stdout or "FFmpeg overlay failed")[-800:])
    os.replace(temporary, destination)


def verify_output(path: Path, media: dict) -> dict:
    probed = probe_video(path)
    if probed["width"] != media["width"] or probed["height"] != media["height"]:
        raise RuntimeError(f"Expected {media['width']}x{media['height']}, got {probed['width']}x{probed['height']}")
    if abs(probed["fps"] - media["fps"]) > 0.01:
        raise RuntimeError(f"Expected {media['fps']} fps, got {probed['fps']}")
    if probed["frames"] != media["frames"]:
        raise RuntimeError(f"Expected {media['frames']} frames, decoded {probed['frames']}")
    if probed["has_audio"] != media["has_audio"]:
        raise RuntimeError("Audio preservation does not match the source")
    if probed["pix_fmt"] != "yuv420p":
        raise RuntimeError(f"Expected yuv420p, got {probed['pix_fmt'] or 'unknown'}")
    head = path.read_bytes()[:65536]
    if head[4:8] != b"ftyp" or b"moov" not in head:
        raise RuntimeError("Expected faststart")
    return probed


def graphic_times(graphic: dict) -> list[tuple[str, float]]:
    start = float(graphic["start"])
    reveal = float(graphic["reveal"])
    fade = float(graphic.get("label_fade") or 0)
    hold = float(graphic["hold"])
    exit_time = float(graphic["exit"])
    return [
        ("reveal", start + reveal * 0.55),
        ("hold", start + reveal + fade + hold * 0.5),
        ("exit", start + reveal + fade + hold + exit_time * 0.45),
    ]


def contact_sheet(video: Path, graphic: dict, destination: Path, media: dict) -> None:
    from PIL import Image, ImageDraw

    cards = []
    folder = destination.parent / "frames"
    folder.mkdir(parents=True, exist_ok=True)
    thumb_w = 480
    thumb_h = max(1, round(thumb_w * media["height"] / media["width"]))
    for name, seconds in graphic_times(graphic):
        frame = folder / f"{name}.jpg"
        subprocess.run(
            [
                ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{seconds:.4f}",
                "-i", str(video),
                "-frames:v", "1",
                str(frame),
            ],
            check=True,
        )
        state = clock_phase(graphic["start"], graphic["reveal"], graphic.get("label_fade") or 0, graphic["hold"], graphic["exit"], seconds)
        with Image.open(frame) as source:
            thumb = source.convert("RGB").resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        card = Image.new("RGB", (thumb_w, thumb_h + 36), (12, 16, 22))
        card.paste(thumb, (0, 0))
        draw = ImageDraw.Draw(card)
        draw.text((12, thumb_h + 10), f"{name}  {seconds:.2f}s", fill=(244, 240, 232))
        cards.append(card)
        if name == "hold":
            phone_w = 390
            phone_h = max(1, round(phone_w * media["height"] / media["width"]))
            phone = source.convert("RGB").resize((phone_w, phone_h), Image.Resampling.LANCZOS)
            phone.save(destination.parent / "phone-hold.jpg", quality=90)
    sheet = Image.new("RGB", (thumb_w * len(cards), thumb_h + 36), (12, 16, 22))
    for index, card in enumerate(cards):
        sheet.paste(card, (index * thumb_w, 0))
    sheet.save(destination, quality=90)
