"""Reference-clip inspection and extraction.

Original uploads are never modified. Selected segments are written as a new
16-bit PCM WAV. No denoising or other identity-changing enhancement is applied.
"""

from __future__ import annotations

import array
import math
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

from .config import DECODER_REFERENCE_SECONDS, ENCODER_REFERENCE_SECONDS

MIN_SEGMENT_SECONDS = 0.3
MAX_SEGMENT_SECONDS = 30.0
_PCM16_MAX = 32767
_CLIP_THRESHOLD = int(_PCM16_MAX * 0.99)
_SILENCE_RMS = 0.008

ALLOWED_SUFFIXES = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".aiff", ".aif"}


class AudioError(ValueError):
    """The recording cannot be used as a reference."""


@dataclass
class AudioInfo:
    path: Path
    duration_sec: float
    sample_rate: int
    channels: int
    sample_width: int
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"Duration: {self.duration_sec:.2f} s",
            f"Sample rate: {self.sample_rate} Hz",
            f"Channels: {self.channels}",
        ]
        if self.warnings:
            lines.append("Warnings:")
            lines.extend(f"- {item}" for item in self.warnings)
        return "\n".join(lines)


def ffmpeg_exe() -> str | None:
    """Prefer a system FFmpeg, then the binary bundled in this lab's virtualenv."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
    except Exception:
        return None
    try:
        path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None
    if path and Path(path).is_file():
        return path
    return None


def ffprobe_exe() -> str | None:
    return shutil.which("ffprobe")


def ffmpeg_available() -> bool:
    return ffmpeg_exe() is not None


def ffprobe_available() -> bool:
    return ffprobe_exe() is not None


def decoder_status() -> str:
    ffmpeg = ffmpeg_exe()
    soundfile = _soundfile_available()
    parts = [
        "WAV 16-bit PCM can be read without extra tools.",
    ]
    if soundfile:
        parts.append("soundfile is available for WAV, FLAC, and OGG when libsndfile supports them.")
    else:
        parts.append("soundfile is not installed, so only 16-bit PCM WAV is readable without FFmpeg.")
    if ffmpeg and shutil.which("ffmpeg"):
        parts.append("FFmpeg is on PATH, so MP3 and M4A can be decoded and MP3 export is enabled.")
    elif ffmpeg:
        parts.append(
            "This lab includes its own FFmpeg, so MP3 and M4A can be decoded and MP3 can be exported. "
            "No system FFmpeg install is required."
        )
    else:
        parts.append(
            "FFmpeg is not available. MP3 and M4A uploads will be rejected, and MP3 export is disabled. "
            "Run scripts/setup.sh inside hindi-voice-lab, then restart the app, or upload WAV."
        )
    return " ".join(parts)


def validate_segment_bounds(start: float, end: float, duration: float) -> float:
    """Return the usable end time, or raise AudioError."""
    if duration <= 0 or not math.isfinite(duration):
        raise AudioError("The recording has no audio.")
    if not math.isfinite(start) or not math.isfinite(end):
        raise AudioError("Start and end must be finite numbers of seconds.")
    if start < 0:
        raise AudioError("Start time cannot be negative.")
    if end <= start:
        raise AudioError("End time must be later than the start time.")
    if start >= duration:
        raise AudioError(
            f"Start time {start:.2f}s is past the end of the {duration:.2f}s recording."
        )
    if end > duration + 0.05:
        raise AudioError(
            f"End time {end:.2f}s is past the recording duration of {duration:.2f}s."
        )
    usable_end = min(end, duration)
    length = usable_end - start
    if length < MIN_SEGMENT_SECONDS:
        raise AudioError("The selected segment is empty or shorter than 0.3 seconds.")
    if length > MAX_SEGMENT_SECONDS:
        raise AudioError(
            "Select at most 30 seconds. This app will not send a long recording to the model. "
            f"The installed model uses the first {ENCODER_REFERENCE_SECONDS:.0f}s for speaker "
            f"conditioning and the first {DECODER_REFERENCE_SECONDS:.0f}s for the decoder."
        )
    return usable_end


def reference_warnings(duration_sec: float, peak: int, rms: float, channels: int) -> list[str]:
    warnings: list[str] = []
    if channels > 1:
        warnings.append("The clip was mixed to mono by averaging channels. The original file was not changed.")
    if duration_sec < 3:
        warnings.append("The clip is shorter than about 3 seconds. A clean 6–10 second phrase is more reliable.")
    if duration_sec > DECODER_REFERENCE_SECONDS:
        warnings.append(
            f"The model only uses the first {DECODER_REFERENCE_SECONDS:.0f} seconds of the reference "
            f"({ENCODER_REFERENCE_SECONDS:.0f}s for speaker tokens). Audio after that is ignored, not learned."
        )
    if peak >= _CLIP_THRESHOLD:
        warnings.append("The clip looks clipped or very close to full scale. Choose a section that is not distorted.")
    if rms < _SILENCE_RMS:
        warnings.append("The clip is near silence. Choose a section with clear speech.")
    return warnings


def recommend_window(duration_sec: float) -> tuple[float, float]:
    """Suggest a window inside the model's 10 second decoder limit."""
    if duration_sec <= 0:
        return 0.0, 0.0
    end = min(duration_sec, float(DECODER_REFERENCE_SECONDS))
    return 0.0, round(end, 3)


def probe_audio(path: Path) -> AudioInfo:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise AudioError(
            f"Unsupported file type {suffix or '(none)'}. Use WAV, or MP3/M4A when FFmpeg is installed."
        )
    if not path.is_file():
        raise AudioError("The audio file does not exist.")
    if suffix == ".wav":
        try:
            return _probe_wav(path)
        except AudioError:
            if ffprobe_available():
                return _probe_with_ffprobe(path)
            if ffmpeg_available():
                return _probe_with_ffmpeg(path)
            raise
    if suffix in {".mp3", ".m4a"} and not ffmpeg_available():
        raise AudioError(
            f"Cannot decode {suffix} because FFmpeg is not available in this lab. "
            "Run scripts/setup.sh, restart the app, or upload a WAV file."
        )
    if ffmpeg_available() and ffprobe_available():
        return _probe_with_ffprobe(path)
    if ffmpeg_available():
        return _probe_with_ffmpeg(path)
    if _soundfile_available():
        return _probe_soundfile(path)
    raise AudioError(
        f"Cannot decode {suffix}. FFmpeg is not installed, and soundfile could not read this file. "
        "Upload 16-bit PCM WAV, or install FFmpeg."
    )


def extract_segment(source: Path, dest: Path, start: float, end: float) -> AudioInfo:
    """Write a new mono PCM WAV for [start, end] without modifying source."""
    info = probe_audio(source)
    usable_end = validate_segment_bounds(start, end, info.duration_sec)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if source.suffix.lower() == ".wav" and info.sample_width == 2 and not ffmpeg_available():
        _extract_wav(source, dest, start, usable_end, info)
    elif source.suffix.lower() == ".wav" and info.sample_width == 2:
        _extract_wav(source, dest, start, usable_end, info)
    elif ffmpeg_available():
        _extract_ffmpeg(source, dest, start, usable_end)
    elif _soundfile_available():
        _extract_soundfile(source, dest, start, usable_end)
    else:
        raise AudioError(decoder_status())
    extracted = _probe_wav(dest)
    samples = _read_pcm16(dest)
    extracted.warnings = reference_warnings(
        extracted.duration_sec,
        _peak(samples),
        _rms(samples),
        info.channels,
    )
    return extracted


def _probe_wav(path: Path) -> AudioInfo:
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            rate = handle.getframerate()
            channels = handle.getnchannels()
            width = handle.getsampwidth()
    except wave.Error as exc:
        raise AudioError(f"Could not read WAV file: {exc}") from exc
    if rate <= 0 or channels <= 0:
        raise AudioError("The WAV file has an invalid sample rate or channel count.")
    if width != 2:
        raise AudioError(
            f"This WAV is {width * 8}-bit. 16-bit PCM is required unless FFmpeg or soundfile can convert it."
        )
    return AudioInfo(
        path=path,
        duration_sec=frames / float(rate),
        sample_rate=rate,
        channels=channels,
        sample_width=width,
    )


def _extract_wav(source: Path, dest: Path, start: float, end: float, info: AudioInfo) -> None:
    with wave.open(str(source), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        start_frame = int(round(start * rate))
        end_frame = int(round(end * rate))
        end_frame = min(end_frame, handle.getnframes())
        if end_frame <= start_frame:
            raise AudioError("The selected segment is empty.")
        handle.setpos(start_frame)
        raw = handle.readframes(end_frame - start_frame)
    samples = array.array("h")
    samples.frombytes(raw)
    mono = _mix_mono(samples, channels)
    if len(mono) == 0:
        raise AudioError("The selected segment is empty.")
    _write_pcm16(dest, mono, rate)


def _extract_ffmpeg(source: Path, dest: Path, start: float, end: float) -> None:
    exe = ffmpeg_exe()
    if not exe:
        raise AudioError("FFmpeg is not available, so this segment cannot be extracted.")
    command = [
        exe,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-ss",
        f"{start:.3f}",
        "-to",
        f"{end:.3f}",
        "-ac",
        "1",
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise AudioError(f"FFmpeg could not extract the segment. {detail}") from exc


def _probe_with_ffprobe(path: Path) -> AudioInfo:
    exe = ffprobe_exe()
    if not exe:
        raise AudioError("ffprobe is not installed, so this format cannot be inspected.")
    command = [
        exe,
        "-v",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=sample_rate,channels",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=0",
        str(path),
    ]
    try:
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise AudioError(f"ffprobe could not read this file. {detail}") from exc
    values: dict[str, str] = {}
    for line in completed.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    try:
        duration = float(values.get("duration", "0"))
        rate = int(float(values.get("sample_rate", "0")))
        channels = int(values.get("channels", "0"))
    except ValueError as exc:
        raise AudioError("ffprobe returned an unreadable audio description.") from exc
    if duration <= 0 or rate <= 0 or channels <= 0:
        raise AudioError("The file does not contain a usable audio stream.")
    return AudioInfo(path=path, duration_sec=duration, sample_rate=rate, channels=channels, sample_width=2)


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_AUDIO_RE = re.compile(
    r"Audio:.*?(\d+)\s*Hz,\s*(mono|stereo|\d+\s*channels)",
    re.IGNORECASE,
)


def _probe_with_ffmpeg(path: Path) -> AudioInfo:
    exe = ffmpeg_exe()
    if not exe:
        raise AudioError("FFmpeg is not available, so this file cannot be inspected.")
    completed = subprocess.run(
        [exe, "-hide_banner", "-i", str(path)],
        capture_output=True,
        text=True,
    )
    text = f"{completed.stderr}\n{completed.stdout}"
    duration_match = _DURATION_RE.search(text)
    audio_match = _AUDIO_RE.search(text)
    if not duration_match or not audio_match:
        detail = " ".join(text.split())[:300]
        raise AudioError(f"FFmpeg could not read a duration and audio stream from this file. {detail}")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    layout = audio_match.group(2).lower()
    if layout == "mono":
        channels = 1
    elif layout == "stereo":
        channels = 2
    else:
        channels = int(layout.split()[0])
    rate = int(audio_match.group(1))
    if duration <= 0 or rate <= 0 or channels <= 0:
        raise AudioError("The file does not contain a usable audio stream.")
    return AudioInfo(path=path, duration_sec=duration, sample_rate=rate, channels=channels, sample_width=2)


def _soundfile_available() -> bool:
    try:
        import soundfile  # noqa: F401
    except Exception:
        return False
    return True


def _probe_soundfile(path: Path) -> AudioInfo:
    import soundfile as sf

    try:
        data, rate = sf.read(str(path), always_2d=True)
    except Exception as exc:
        raise AudioError(
            f"soundfile could not read this file ({exc}). "
            "For MP3 or M4A, install FFmpeg."
        ) from exc
    return AudioInfo(
        path=path,
        duration_sec=len(data) / float(rate),
        sample_rate=int(rate),
        channels=int(data.shape[1]),
        sample_width=2,
    )


def _extract_soundfile(source: Path, dest: Path, start: float, end: float) -> None:
    import numpy as np
    import soundfile as sf

    try:
        data, rate = sf.read(str(source), always_2d=True)
    except Exception as exc:
        raise AudioError(f"soundfile could not decode the recording: {exc}") from exc
    start_index = int(round(start * rate))
    end_index = int(round(end * rate))
    clip = data[start_index:end_index]
    if clip.size == 0:
        raise AudioError("The selected segment is empty.")
    mono = clip.mean(axis=1)
    ints = np.clip(np.round(mono * 32767.0), -32768, 32767).astype("<i2")
    samples = array.array("h")
    samples.frombytes(ints.tobytes())
    _write_pcm16(dest, samples, int(rate))


def export_mp3(wav_path: Path, mp3_path: Path) -> None:
    exe = ffmpeg_exe()
    if not exe:
        raise AudioError(
            "MP3 export needs FFmpeg with an MP3 encoder. The WAV file is still available."
        )
    command = [
        exe,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(wav_path),
        "-codec:a",
        "libmp3lame",
        "-qscale:a",
        "2",
        str(mp3_path),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()
        raise AudioError(f"FFmpeg could not write MP3. {detail}") from exc


def _read_pcm16(path: Path) -> array.array:
    with wave.open(str(path), "rb") as handle:
        raw = handle.readframes(handle.getnframes())
    samples = array.array("h")
    samples.frombytes(raw)
    return samples


def _write_pcm16(path: Path, samples: array.array, sample_rate: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(samples.tobytes())
    temporary.replace(path)


def _mix_mono(samples: array.array, channels: int) -> array.array:
    if channels == 1:
        return samples
    frame_count = len(samples) // channels
    mixed = array.array("h")
    for frame in range(frame_count):
        total = 0
        base = frame * channels
        for channel in range(channels):
            total += samples[base + channel]
        value = int(round(total / channels))
        mixed.append(max(-32768, min(_PCM16_MAX, value)))
    return mixed


def _peak(samples: array.array) -> int:
    peak = 0
    for sample in samples:
        magnitude = sample if sample >= 0 else -sample
        if magnitude > peak:
            peak = magnitude
    return peak


def _rms(samples: array.array) -> float:
    if not samples:
        return 0.0
    total = 0.0
    for sample in samples:
        value = sample / 32768.0
        total += value * value
    return math.sqrt(total / len(samples))
