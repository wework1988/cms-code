"""Artifact-based completion checks shared by runners and the watchdog."""
from __future__ import annotations
import json
import re
import struct
import subprocess
from pathlib import Path


def scene_ids(path: Path, *, digen_headers_only: bool = False) -> set[int]:
    if not path.is_file():
        return set()
    text = path.read_text(encoding='utf-8-sig')
    # prompt.txt contains both "--- Scene N /" section headers and "Scene N. Title…"
    # inside IMAGE PROMPT bodies. For motion completeness, count headers only.
    if digen_headers_only or path.name == 'prompt.txt':
        ids = [int(x) for x in re.findall(r'(?m)^\s*---\s*Scene\s+(\d+)\s*/', text)]
    else:
        ids = [int(x) for x in re.findall(r'(?m)^\s*(?:---\s*)?Scene\s+(\d+)(?:\s*[./:]|\s*$)', text)]
    if len(ids) != len(set(ids)):
        raise ValueError(f'Duplicate scene IDs in {path.name}')
    return set(ids)


def expected_scenes(root: Path) -> set[int]:
    return scene_ids(root / 'image-prompts/image-prompts-only.txt')


def image_valid(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    try:
        result = subprocess.run(['/usr/bin/sips', '-g', 'pixelWidth', '-g', 'pixelHeight', str(path)], capture_output=True, text=True, timeout=15)
        w = re.search(r'pixelWidth:\s*(\d+)', result.stdout)
        h = re.search(r'pixelHeight:\s*(\d+)', result.stdout)
        return result.returncode == 0 and bool(w and h) and int(w[1]) >= 2000 and abs(int(w[1])/int(h[1]) - 16/9) < .04
    except (OSError, subprocess.SubprocessError, ZeroDivisionError):
        return False


def video_valid(path: Path) -> bool:
    """Check complete MP4 boxes, a video track, positive duration and media payload."""
    if not path.is_file():
        return False
    try:
        size = path.stat().st_size
        found = set()
        with path.open('rb') as f:
            while f.tell() < size:
                start = f.tell()
                header = f.read(8)
                if len(header) != 8: return False
                length, kind = struct.unpack('>I4s', header)
                minimum = 8
                if length == 1:
                    extra = f.read(8)
                    if len(extra) != 8: return False
                    length = struct.unpack('>Q', extra)[0]
                    minimum = 16
                if length == 0: length = size-start
                if length < minimum or start+length > size: return False
                if kind == b'moov':
                    if length > 32*1024*1024: return False
                    data = f.read(length-minimum)
                    if b'vide' not in data: return False
                    pos = data.find(b'mvhd')
                    if pos < 0: return False
                    body = data[pos+4:]
                    if len(body) < 32: return False
                    off = 20 if body[0] == 1 else 12
                    scale = struct.unpack('>I', body[off:off+4])[0]
                    fmt = '>Q' if body[0] == 1 else '>I'
                    n = 8 if body[0] == 1 else 4
                    duration = struct.unpack(fmt, body[off+4:off+4+n])[0]
                    if not scale or not duration: return False
                    found.add(kind)
                elif kind == b'mdat' and length > minimum:
                    found.add(kind)
                f.seek(start+length)
        return {b'moov', b'mdat'} <= found
    except (OSError, ValueError, struct.error):
        return False


def media_report(root: Path, kind: str) -> dict:
    expected = expected_scenes(root)
    valid, missing, invalid, duplicates = [], [], [], []
    for scene in sorted(expected):
        candidates = ([p for p in (root/'images').glob('*') if p.stem.isdigit() and int(p.stem) == scene and p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}]
                      if kind == 'images' else list((root/'videos').glob(f'scene_{scene}.mp4')))
        if not candidates: missing.append(scene)
        elif len(candidates) != 1: duplicates.append(scene)
        elif (image_valid if kind == 'images' else video_valid)(candidates[0]): valid.append(scene)
        else: invalid.append(scene)
    motion = scene_ids(root/'prompts/prompt.txt') if kind == 'videos' else expected
    return {'complete': bool(expected) and set(valid) == expected and expected <= motion,
            'expected':len(expected), 'completed':len(valid), 'missing':missing, 'invalid':invalid,
            'duplicates':duplicates, 'missing_motion':sorted(expected-motion)}


def storyboard_report(root: Path) -> dict:
    expected = scene_ids(root/'scenes/scene.txt')
    images = expected_scenes(root)
    motion = scene_ids(root/'prompts/prompt.txt', digen_headers_only=True)
    return {'complete':bool(expected) and expected == images == motion, 'expected':len(expected),
            'completed':len(expected & images & motion), 'missing_images':sorted(expected-images),
            'missing_motion':sorted(expected-motion), 'extra_images':sorted(images-expected)}
