"""Sequential Hindi generation, assembly, and resumable jobs."""

from __future__ import annotations

import array
import hashlib
import json
import os
import re
import threading
import time
import uuid
import wave
from pathlib import Path

from .audio_processing import AudioError, export_mp3, ffmpeg_available
from .config import (
    JOBS,
    LANGUAGE_ID,
    MODEL_SAMPLE_RATE,
    OUTPUTS,
    PACKAGE_VERSION,
    T3_FILENAME,
    confine,
)
from .model_adapter import GeneratedChunk, ModelError, ModelService
from .narration import PIPELINE_VERSION, NarrationError, PauseMark, SpeechPiece, assert_model_text, plan_narration
from .text_processing import MAX_TEXT_CHARS
from .voice_profiles import ProfileError, load_profile

_JOB_LOCK = threading.Lock()
_LIVE = {"active": False, "job_id": None, "message": "", "index": 0, "total": 0}
JOB_ID_RE = re.compile(r"^job-[a-f0-9]{12}$")
SCHEMA_VERSION = 2
_RESUMABLE = {"partial", "generating", "failed", "interrupted"}


class GenerationError(RuntimeError):
    """A narration job could not be created or resumed."""


def build_fingerprint(
    text: str,
    plan: list,
    profile_id: str,
    reference_sha256: str,
    settings: dict,
) -> str:
    payload = {
        "pipeline_version": PIPELINE_VERSION,
        "text": text,
        "plan": plan,
        "profile_id": profile_id,
        "reference_sha256": reference_sha256,
        "language_id": LANGUAGE_ID,
        "package_version": PACKAGE_VERSION,
        "checkpoint": T3_FILENAME,
        "settings": settings,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def reusable_chunks(job_dir: Path, fingerprint: str, chunks: list[str], sample_rate: int) -> list[Path | None]:
    """Return completed chunk files only when the job still matches."""
    meta_path = job_dir / "metadata.json"
    if not meta_path.is_file():
        return [None] * len(chunks)
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [None] * len(chunks)
    if metadata.get("fingerprint") != fingerprint:
        return [None] * len(chunks)
    if int(metadata.get("sample_rate") or 0) not in {0, sample_rate}:
        return [None] * len(chunks)
    records = {int(item["index"]): item for item in metadata.get("chunks", []) if "index" in item}
    found: list[Path | None] = []
    for index, text in enumerate(chunks):
        record = records.get(index)
        if not record or record.get("status") != "complete" or record.get("text") != text:
            found.append(None)
            continue
        relative = str(record.get("relative_path") or "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            found.append(None)
            continue
        try:
            path = confine(job_dir / relative, job_dir)
        except ValueError:
            found.append(None)
            continue
        if not _wav_ok(path, sample_rate):
            found.append(None)
            continue
        found.append(path)
    return found


def list_history(limit: int = 20, root: Path | None = None) -> list[dict]:
    base = Path(root) if root is not None else JOBS
    if not base.exists():
        return []
    rows = []
    for folder in base.iterdir():
        meta = folder / "metadata.json"
        if not meta.is_file():
            continue
        try:
            document = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        text = str(document.get("text") or "")
        preview = text[:48] + ("…" if len(text) > 48 else "")
        rows.append(
            {
                "id": document.get("id"),
                "status": document.get("status"),
                "updated_at": document.get("updated_at"),
                "profile_id": document.get("profile_id"),
                "device_used": document.get("device_used"),
                "preview": preview,
                "output_wav": document.get("output_wav"),
            }
        )
    rows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return rows[:limit]


def generation_busy() -> bool:
    return _JOB_LOCK.locked()


def live_progress() -> dict:
    return dict(_LIVE)


def generate_speech(
    profile_id: str,
    text: str,
    settings: dict,
    service: ModelService,
    progress=None,
    jobs_root: Path | None = None,
    profiles_root: Path | None = None,
    title: str | None = None,
    force_new: bool = False,
    reuse_complete: bool = False,
) -> dict:
    if not _JOB_LOCK.acquire(blocking=False):
        raise GenerationError("Another generation is already running. Wait for it to finish.")
    started = time.perf_counter()
    try:
        return _generate_locked(
            profile_id,
            text,
            settings,
            service,
            progress,
            jobs_root,
            profiles_root,
            started,
            title=title,
            force_new=force_new,
            reuse_complete=reuse_complete,
        )
    finally:
        _LIVE["active"] = False
        _JOB_LOCK.release()


def _generate_locked(
    profile_id: str,
    text: str,
    settings: dict,
    service: ModelService,
    progress,
    jobs_root: Path | None,
    profiles_root: Path | None,
    started: float,
    title: str | None = None,
    force_new: bool = False,
    reuse_complete: bool = False,
) -> dict:
    original = text or ""
    if not original.strip():
        raise GenerationError("Enter some Hindi text.")
    if len(original) > MAX_TEXT_CHARS:
        raise GenerationError(
            f"Text is longer than {MAX_TEXT_CHARS} characters. Split it into smaller narrations."
        )
    try:
        profile = load_profile(profile_id, profiles_root)
    except ProfileError as exc:
        raise GenerationError(str(exc)) from exc
    reference = Path(profile["reference_path"])
    normalized = _normalize_settings(settings)
    try:
        narration = plan_narration(
            original,
            int(normalized["sentence_pause_ms"]),
            int(normalized["paragraph_pause_ms"]),
        )
    except NarrationError as exc:
        raise GenerationError(str(exc)) from exc
    segments = narration.model_segments()
    chunks = [piece.model_text for piece in segments]
    if not chunks:
        raise GenerationError("Enter some Hindi text.")
    try:
        for part in chunks:
            assert_model_text(part)
    except NarrationError as exc:
        raise GenerationError(str(exc)) from exc
    plan_document = narration.to_dict()
    reference_sha = _sha256(reference)
    fingerprint = build_fingerprint(
        original,
        plan_document,
        profile["id"],
        reference_sha,
        normalized,
    )
    base = Path(jobs_root) if jobs_root is not None else JOBS
    if reuse_complete and not force_new:
        cached = _completed_match(base, fingerprint)
        if cached is not None:
            folder, metadata = cached
            note = "Reused an existing generation with the same voice, text, pauses, and settings."
            result = _result_from_metadata(metadata, folder, notes=[note])
            result["cache_hit"] = True
            result["resumed"] = False
            return result
    job_dir, metadata, resumed = _open_job(
        base,
        fingerprint,
        original,
        plan_document,
        chunks,
        profile,
        normalized,
        title=title,
        reference_sha256=reference_sha,
        force_new=force_new,
    )
    _LIVE.update(active=True, job_id=metadata["id"], message="Preparing segments", index=0, total=len(chunks))
    sample_rate = int(metadata.get("sample_rate") or MODEL_SAMPLE_RATE)
    existing = reusable_chunks(job_dir, fingerprint, chunks, sample_rate)
    notes: list[str] = []
    if resumed:
        notes.append("Resuming a local job with the same text, reference, model, and settings.")
    device_used = metadata.get("device_used")
    for index, part in enumerate(chunks):
        message = f"Generating segment {index + 1} of {len(chunks)}"
        if existing[index] is not None:
            message = f"Reusing segment {index + 1} of {len(chunks)}"
            _report(progress, message, index, len(chunks))
            continue
        _report(progress, message, index, len(chunks))
        if not part.strip():
            raise GenerationError("A text segment was empty after chunking.")
        try:
            generated = service.generate(
                text=part,
                reference_wav=reference,
                device=str(normalized["device"]),
                exaggeration=float(normalized["exaggeration"]),
                cfg_weight=float(normalized["cfg_weight"]),
                temperature=float(normalized["temperature"]),
                repetition_penalty=float(normalized["repetition_penalty"]),
                min_p=float(normalized["min_p"]),
                top_p=float(normalized["top_p"]),
                seed=normalized["seed"],
                offline=bool(normalized["offline"]),
            )
        except ModelError as exc:
            metadata["status"] = "failed"
            metadata["error"] = str(exc)
            metadata["updated_at"] = _now()
            _write_json(job_dir / "metadata.json", metadata)
            raise GenerationError(str(exc)) from exc
        if generated.note:
            notes.append(generated.note)
        if device_used and device_used != generated.device_used:
            metadata["status"] = "failed"
            metadata["error"] = (
                f"Segment {index + 1} ran on {generated.device_used}, but earlier audio used "
                f"{device_used}. The partial files were kept. Start again with Device set to CPU "
                "so the whole narration uses one device."
            )
            metadata["updated_at"] = _now()
            _write_json(job_dir / "metadata.json", metadata)
            raise GenerationError(metadata["error"])
        device_used = generated.device_used
        sample_rate = generated.sample_rate
        relative = f"chunks/{index:04d}.wav"
        _write_float_wav(job_dir / relative, generated, job_dir)
        _upsert_chunk(metadata, index, part, relative, generated)
        metadata["sample_rate"] = sample_rate
        metadata["device_used"] = device_used
        metadata["status"] = "partial"
        metadata["updated_at"] = _now()
        metadata["error"] = None
        _write_json(job_dir / "metadata.json", metadata)
        existing[index] = confine(job_dir / relative, job_dir)

    if jobs_root is not None:
        output_path = confine(job_dir / "output.wav", job_dir)
    else:
        OUTPUTS.mkdir(parents=True, exist_ok=True)
        output_path = confine(OUTPUTS / f"{metadata['id']}.wav", OUTPUTS)
    paths = [path for path in existing if path is not None]
    if len(paths) != len(chunks):
        raise GenerationError("Not every segment was generated, so the narration was not assembled.")
    assemble_timeline(paths, narration.events, output_path, sample_rate)
    mp3_path = None
    mp3_error = None
    if ffmpeg_available():
        candidate = output_path.with_suffix(".mp3")
        try:
            export_mp3(output_path, candidate)
            mp3_path = candidate
        except AudioError as exc:
            mp3_error = str(exc)
    else:
        mp3_error = "MP3 export is unavailable because FFmpeg is not installed. Download the WAV."
    elapsed = round(time.perf_counter() - started, 3)
    metadata["status"] = "complete"
    metadata["duration_sec"] = _wav_duration(output_path)
    metadata["output_wav"] = str(output_path)
    metadata["output_mp3"] = str(mp3_path) if mp3_path else None
    metadata["device_used"] = device_used
    metadata["sample_rate"] = sample_rate
    metadata["elapsed_sec"] = elapsed
    metadata["updated_at"] = _now()
    metadata["completed_at"] = metadata["updated_at"]
    metadata["error"] = None
    metadata["notes"] = notes
    _write_json(job_dir / "metadata.json", metadata)
    return {
        "job_id": metadata["id"],
        "wav_path": str(output_path),
        "mp3_path": str(mp3_path) if mp3_path else None,
        "mp3_error": mp3_error,
        "device_used": device_used,
        "sample_rate": sample_rate,
        "segments": len(chunks),
        "elapsed_sec": elapsed,
        "notes": notes,
        "resumed": resumed,
        "cache_hit": False,
        "title": metadata.get("title"),
        "voice_name": metadata.get("voice_name"),
    }


def mark_abandoned_jobs(root: Path | None = None) -> list[str]:
    """Mark in-progress jobs interrupted when this process is not generating them."""
    base = Path(root) if root is not None else JOBS
    if not base.exists():
        return []
    active = _LIVE.get("job_id") if _LIVE.get("active") else None
    changed: list[str] = []
    for folder in base.iterdir():
        if not folder.is_dir() or not JOB_ID_RE.fullmatch(folder.name):
            continue
        if folder.name == active:
            continue
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        try:
            document = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("status") not in {"partial", "generating"}:
            continue
        document["status"] = "interrupted"
        document["error"] = document.get("error") or (
            "The app stopped before this generation finished. Completed pieces were kept."
        )
        document["updated_at"] = _now()
        _write_json(meta_path, document)
        changed.append(folder.name)
    return changed


def _open_job(
    base: Path,
    fingerprint: str,
    text: str,
    plan: list,
    chunks: list[str],
    profile: dict,
    settings: dict,
    title: str | None = None,
    reference_sha256: str | None = None,
    force_new: bool = False,
):
    candidate = None if force_new else _latest_partial(base, fingerprint)
    if candidate is not None:
        metadata = json.loads((candidate / "metadata.json").read_text(encoding="utf-8"))
        metadata["status"] = "generating"
        metadata["title"] = _clean_title(title) or metadata.get("title")
        metadata.setdefault("voice_name", profile.get("display_name"))
        metadata.setdefault("schema_version", SCHEMA_VERSION)
        if reference_sha256:
            metadata.setdefault("reference_sha256", reference_sha256)
        metadata["updated_at"] = _now()
        _write_json(candidate / "metadata.json", metadata)
        return candidate, metadata, True
    job_id = f"job-{uuid.uuid4().hex[:12]}"
    if not JOB_ID_RE.fullmatch(job_id):
        raise GenerationError("Could not allocate a job id.")
    job_dir = confine(base / job_id, base)
    (job_dir / "chunks").mkdir(parents=True, exist_ok=True)
    metadata = {
        "id": job_id,
        "schema_version": SCHEMA_VERSION,
        "status": "generating",
        "fingerprint": fingerprint,
        "pipeline_version": PIPELINE_VERSION,
        "title": _clean_title(title),
        "text": text,
        "plan": plan,
        "spoken_segments": chunks,
        "profile_id": profile["id"],
        "voice_name": profile.get("display_name"),
        "reference_sha256": reference_sha256,
        "reference_wav": profile["reference_path"],
        "language_id": LANGUAGE_ID,
        "checkpoint": T3_FILENAME,
        "package_version": PACKAGE_VERSION,
        "settings": settings,
        "seed": settings.get("seed"),
        "device_requested": settings.get("device"),
        "device_used": None,
        "sample_rate": MODEL_SAMPLE_RATE,
        "chunks": [],
        "output_wav": None,
        "output_mp3": None,
        "created_at": _now(),
        "updated_at": _now(),
        "completed_at": None,
        "elapsed_sec": None,
        "error": None,
        "notes": [],
        "timings": [],
    }
    _write_json(job_dir / "metadata.json", metadata)
    return job_dir, metadata, False


def _latest_partial(base: Path, fingerprint: str) -> Path | None:
    if not base.exists():
        return None
    matches: list[tuple[str, Path]] = []
    for folder in base.iterdir():
        if not folder.is_dir() or not JOB_ID_RE.fullmatch(folder.name):
            continue
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        try:
            document = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("fingerprint") != fingerprint:
            continue
        if document.get("status") not in _RESUMABLE:
            continue
        matches.append((str(document.get("updated_at") or ""), folder))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[-1][1]


def _normalize_settings(settings: dict) -> dict:
    def number(name: str, default: float, low: float, high: float) -> float:
        raw = settings.get(name, default)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise GenerationError(f"{name} must be a number.") from exc
        if not low <= value <= high:
            raise GenerationError(f"{name} must be between {low} and {high}.")
        return value

    device = str(settings.get("device") or "auto").lower()
    if device not in {"auto", "cpu", "mps", "cuda"}:
        raise GenerationError("Device must be auto, cpu, mps, or cuda.")
    seed = settings.get("seed")
    parsed_seed: int | None
    if seed is None or seed == "":
        parsed_seed = None
    else:
        try:
            parsed_seed = int(seed)
        except (TypeError, ValueError) as exc:
            raise GenerationError("Seed must be an integer, or left empty.") from exc
        if not 0 <= parsed_seed <= 2_147_483_647:
            raise GenerationError("Seed must be between 0 and 2147483647.")
    preset = str(settings.get("preset") or "neutral")
    if preset not in {"neutral", "warm", "serious", "dramatic", "custom"}:
        raise GenerationError("Delivery preset must be neutral, warm, serious, dramatic, or custom.")
    return {
        "device": device,
        "offline": bool(settings.get("offline")),
        "preset": preset,
        "exaggeration": number("exaggeration", 0.5, 0.0, 1.5),
        "cfg_weight": number("cfg_weight", 0.5, 0.0, 1.0),
        "temperature": number("temperature", 0.8, 0.05, 1.5),
        "repetition_penalty": number("repetition_penalty", 2.0, 1.0, 3.0),
        "min_p": number("min_p", 0.05, 0.0, 0.5),
        "top_p": number("top_p", 1.0, 0.5, 1.0),
        "sentence_pause_ms": int(number("sentence_pause_ms", 450, 0, 5000)),
        "paragraph_pause_ms": int(number("paragraph_pause_ms", 800, 0, 5000)),
        "seed": parsed_seed,
    }


def _upsert_chunk(metadata: dict, index: int, text: str, relative: str, generated: GeneratedChunk) -> None:
    record = {
        "index": index,
        "text": text,
        "relative_path": relative,
        "status": "complete",
        "sample_rate": generated.sample_rate,
        "device_used": generated.device_used,
        "samples": len(generated.samples),
    }
    chunks = [item for item in metadata.get("chunks", []) if int(item.get("index", -1)) != index]
    chunks.append(record)
    chunks.sort(key=lambda item: int(item["index"]))
    metadata["chunks"] = chunks
    metadata.setdefault("timings", []).append(
        {
            "index": index,
            "device_used": generated.device_used,
            "samples": len(generated.samples),
            "sample_rate": generated.sample_rate,
        }
    )


def edge_silence_ms(samples: array.array, sample_rate: int, edge: str) -> int:
    """Count only near-digital-silence at one edge. The samples are not changed."""
    if sample_rate <= 0 or not samples:
        return 0
    threshold = 200
    sequence = reversed(samples) if edge == "trail" else samples
    count = 0
    for sample in sequence:
        if abs(int(sample)) <= threshold:
            count += 1
        else:
            break
    return (count * 1000) // sample_rate


def inserted_silence_ms(planned_ms: int, previous_tail_ms: int, next_head_ms: int) -> int:
    """Shorten an inserted gap by silence already in the clips, without trimming them."""
    planned = max(0, int(planned_ms))
    already = max(0, int(previous_tail_ms)) + max(0, int(next_head_ms))
    return max(0, planned - already)


def assemble_timeline(
    paths: list[Path],
    events: tuple,
    destination: Path,
    sample_rate: int,
) -> None:
    """Join spoken clips and insert planned silence at the real sample rate."""
    wavs = iter(paths)
    clips: list[array.array | None] = []
    for kind, item in events:
        if kind == "speech" and isinstance(item, SpeechPiece) and item.model_text:
            try:
                path = next(wavs)
            except StopIteration as exc:
                raise GenerationError("A spoken segment had no audio file.") from exc
            rate, samples = _read_wav(path)
            if rate != sample_rate:
                raise GenerationError(
                    f"A segment is {rate} Hz, but the narration is {sample_rate} Hz."
                )
            clips.append(samples)
        else:
            clips.append(None)
    try:
        next(wavs)
    except StopIteration:
        pass
    else:
        raise GenerationError("There was extra segment audio that the plan did not ask for.")

    combined = array.array("h")
    pending_ms = 0
    previous: array.array | None = None
    for index, (kind, item) in enumerate(events):
        if kind == "pause" and isinstance(item, PauseMark):
            pending_ms += int(item.ms)
            continue
        if kind != "speech" or not isinstance(item, SpeechPiece) or not item.model_text:
            continue
        samples = clips[index]
        if samples is None:
            raise GenerationError("A spoken segment had no audio file.")
        if pending_ms:
            _append_pause(combined, pending_ms, previous, samples, sample_rate)
            pending_ms = 0
        combined.extend(samples)
        previous = samples
    if pending_ms:
        _append_pause(combined, pending_ms, previous, None, sample_rate)
    _write_pcm(destination, combined, sample_rate)


def _append_pause(
    combined: array.array,
    planned_ms: int,
    previous: array.array | None,
    nxt: array.array | None,
    sample_rate: int,
) -> None:
    tail = edge_silence_ms(previous, sample_rate, "trail") if previous is not None else 0
    head = edge_silence_ms(nxt, sample_rate, "lead") if nxt is not None else 0
    frames = int(round(sample_rate * (inserted_silence_ms(planned_ms, tail, head) / 1000.0)))
    if frames:
        combined.extend(array.array("h", [0]) * frames)


def _write_pcm(destination: Path, samples: array.array, sample_rate: int) -> None:
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(samples.tobytes())
    os.replace(temporary, destination)


def _assemble(paths: list[Path], destination: Path, sample_rate: int, pause_ms: int) -> None:
    pause_frames = int(round(sample_rate * (pause_ms / 1000.0)))
    silence = array.array("h", [0]) * pause_frames
    combined = array.array("h")
    for index, path in enumerate(paths):
        rate, samples = _read_wav(path)
        if rate != sample_rate:
            raise GenerationError(
                f"Segment {index + 1} is {rate} Hz, but the narration is {sample_rate} Hz."
            )
        if index and pause_frames:
            combined.extend(silence)
        combined.extend(samples)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(combined.tobytes())
    os.replace(temporary, destination)


def _write_float_wav(path: Path, generated: GeneratedChunk, job_dir: Path) -> None:
    path = confine(path, job_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    samples = array.array("h")
    for value in generated.samples:
        clamped = max(-1.0, min(1.0, float(value)))
        samples.append(int(round(clamped * 32767.0)))
    temporary = path.with_suffix(path.suffix + ".partial")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(generated.sample_rate)
        handle.writeframes(samples.tobytes())
    os.replace(temporary, path)


def _read_wav(path: Path) -> tuple[int, array.array]:
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise GenerationError(f"{path.name} is not mono 16-bit PCM.")
        rate = handle.getframerate()
        samples = array.array("h")
        samples.frombytes(handle.readframes(handle.getnframes()))
    return rate, samples


def _wav_ok(path: Path, sample_rate: int) -> bool:
    if not path.is_file():
        return False
    try:
        rate, samples = _read_wav(path)
    except (wave.Error, EOFError, GenerationError, OSError):
        return False
    return rate == sample_rate and len(samples) > 0


def _write_json(path: Path, document: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_title(title: str | None) -> str | None:
    cleaned = " ".join((title or "").split())
    if not cleaned:
        return None
    if len(cleaned) > 120:
        raise GenerationError("Title must be 120 characters or fewer.")
    return cleaned


def _wav_duration(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return round(handle.getnframes() / rate, 3)
    except (wave.Error, EOFError, OSError):
        return None


def _completed_match(base: Path, fingerprint: str) -> tuple[Path, dict] | None:
    if not base.exists():
        return None
    matches: list[tuple[str, Path, dict]] = []
    for folder in base.iterdir():
        if not folder.is_dir() or not JOB_ID_RE.fullmatch(folder.name):
            continue
        meta_path = folder / "metadata.json"
        if not meta_path.is_file():
            continue
        try:
            document = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if document.get("fingerprint") != fingerprint or document.get("status") != "complete":
            continue
        wav = document.get("output_wav")
        if not wav or not Path(wav).is_file():
            continue
        matches.append((str(document.get("completed_at") or document.get("updated_at") or ""), folder, document))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    _stamp, folder, document = matches[-1]
    return folder, document


def _result_from_metadata(metadata: dict, folder: Path, notes: list[str]) -> dict:
    wav = metadata.get("output_wav")
    mp3 = metadata.get("output_mp3")
    return {
        "job_id": metadata["id"],
        "wav_path": wav,
        "mp3_path": mp3 if mp3 and Path(mp3).is_file() else None,
        "mp3_error": None,
        "device_used": metadata.get("device_used"),
        "sample_rate": metadata.get("sample_rate"),
        "segments": len(metadata.get("spoken_segments") or metadata.get("chunks") or []),
        "elapsed_sec": metadata.get("elapsed_sec"),
        "notes": notes,
        "resumed": False,
        "cache_hit": False,
        "title": metadata.get("title"),
        "voice_name": metadata.get("voice_name"),
        "job_dir": str(folder),
    }


def _report(progress, message: str, index: int, total: int) -> None:
    _LIVE.update(message=message, index=index, total=total)
    if progress is None:
        return
    fraction = index / total if total else 0
    try:
        progress(fraction, desc=message)
    except TypeError:
        progress(fraction)
