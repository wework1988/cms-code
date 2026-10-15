"""Read-only history over job folders. The index is the metadata on disk.

Missing fields are derived when that can be done from a profile or an audio
header. Nothing is invented, and listing a job does not rewrite it.
"""

from __future__ import annotations

import json
import wave
from datetime import datetime
from pathlib import Path

from .config import JOBS, OUTPUTS, ROOT, confine
from .generation import JOB_ID_RE
from .voice_profiles import ProfileError, load_profile

PUBLIC_STATUSES = {
    "complete": "completed",
    "completed": "completed",
    "failed": "failed",
    "interrupted": "interrupted",
    "generating": "generating",
    "partial": "generating",
    "queued": "queued",
}


class HistoryError(ValueError):
    """A history request was not safe to serve."""


def query_history(
    *,
    text: str = "",
    voice_id: str = "",
    status: str = "",
    created_from: str = "",
    created_to: str = "",
    sort: str = "newest",
    page: int = 1,
    page_size: int = 20,
    jobs_root: Path | None = None,
    profiles_root: Path | None = None,
) -> dict:
    records = list_records(jobs_root, profiles_root)
    needle = (text or "").casefold().strip()
    wanted_status = (status or "").strip().lower()
    if wanted_status == "complete":
        wanted_status = "completed"
    start = _parse_bound(created_from)
    end = _parse_bound(created_to)
    matched = []
    for record in records:
        if voice_id and record.get("voice_id") != voice_id:
            continue
        if wanted_status and record.get("status") != wanted_status:
            continue
        if needle and needle not in record.get("search_text", ""):
            continue
        created = _parse_bound(record.get("created_at") or "")
        if start and (created is None or created < start):
            continue
        if end and (created is None or created > end):
            continue
        matched.append(record)
    reverse = sort != "oldest"
    matched.sort(key=lambda item: item.get("created_at") or "", reverse=reverse)
    size = min(max(int(page_size or 20), 1), 100)
    current = max(int(page or 1), 1)
    total = len(matched)
    offset = (current - 1) * size
    page_items = matched[offset : offset + size]
    return {
        "total": total,
        "page": current,
        "page_size": size,
        "pages": max(1, (total + size - 1) // size) if total else 1,
        "items": [_public(item) for item in page_items],
    }


def list_records(jobs_root: Path | None = None, profiles_root: Path | None = None) -> list[dict]:
    base = Path(jobs_root) if jobs_root is not None else JOBS
    if not base.exists():
        return []
    names = {item.get("id"): item.get("display_name") for item in _profiles(profiles_root)}
    records = []
    for folder in base.iterdir():
        if not folder.is_dir() or not JOB_ID_RE.fullmatch(folder.name):
            continue
        records.append(_read_record(folder, names))
    return records


def get_record(job_id: str, jobs_root: Path | None = None, profiles_root: Path | None = None) -> dict:
    if not JOB_ID_RE.fullmatch(job_id or ""):
        raise HistoryError("Job id is not valid.")
    base = Path(jobs_root) if jobs_root is not None else JOBS
    folder = confine(base / job_id, base)
    if not folder.is_dir():
        raise HistoryError("That generation was not found.")
    names = {item.get("id"): item.get("display_name") for item in _profiles(profiles_root)}
    return _public(_read_record(folder, names))


def audio_path(job_id: str, kind: str, jobs_root: Path | None = None) -> Path:
    """Return a persisted wav or mp3 that belongs to this job, or raise."""
    if kind not in {"wav", "mp3"}:
        raise HistoryError("Choose wav or mp3.")
    if not JOB_ID_RE.fullmatch(job_id or ""):
        raise HistoryError("Job id is not valid.")
    base = Path(jobs_root) if jobs_root is not None else JOBS
    folder = confine(base / job_id, base)
    if not folder.is_dir():
        raise HistoryError("That generation was not found.")
    record = _read_record(folder, {})
    key = "_resolved_wav" if kind == "wav" else "_resolved_mp3"
    if not record.get(key):
        raise HistoryError("Audio unavailable" if kind == "wav" else "MP3 is not available for this generation.")
    candidate = _safe_audio(record.get(key), folder)
    if candidate is None or not candidate.is_file():
        raise HistoryError("Audio unavailable")
    return candidate


def _read_record(folder: Path, names: dict) -> dict:
    meta_path = folder / "metadata.json"
    job_id = folder.name
    try:
        document = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "id": job_id,
            "readable": False,
            "status": "failed",
            "title": None,
            "text": "",
            "excerpt": "Unreadable record",
            "voice_id": None,
            "voice_name": "Unknown voice",
            "voice_name_source": "unknown",
            "created_at": None,
            "completed_at": None,
            "duration_sec": None,
            "duration_source": None,
            "sample_rate": None,
            "audio_available": False,
            "mp3_available": False,
            "error": "This job's metadata could not be read.",
            "search_text": job_id.casefold(),
            "legacy": True,
            "_resolved_wav": None,
            "_resolved_mp3": None,
            "wav_name": None,
            "mp3_name": None,
        }
    if not isinstance(document, dict):
        document = {}
    text = document.get("text") if isinstance(document.get("text"), str) else ""
    title = document.get("title") if isinstance(document.get("title"), str) and document.get("title") else None
    voice_id = document.get("profile_id") if isinstance(document.get("profile_id"), str) else None
    snapshot = document.get("voice_name") if isinstance(document.get("voice_name"), str) and document.get("voice_name") else None
    if snapshot:
        voice_name = snapshot
        voice_source = "snapshot"
    elif voice_id and names.get(voice_id):
        voice_name = names[voice_id]
        voice_source = "profile"
    elif voice_id:
        voice_name = voice_id
        voice_source = "id"
    else:
        voice_name = "Unknown voice"
        voice_source = "unknown"
    raw_status = str(document.get("status") or "failed")
    status = PUBLIC_STATUSES.get(raw_status, "failed")
    wav = _resolve_output(document.get("output_wav"), job_id, "wav", folder)
    mp3 = _resolve_output(document.get("output_mp3"), job_id, "mp3", folder)
    duration = document.get("duration_sec")
    duration_source = "stored" if isinstance(duration, (int, float)) else None
    sample_rate = document.get("sample_rate") if isinstance(document.get("sample_rate"), int) else None
    if duration_source is None and wav is not None:
        probed = _probe_wav(wav)
        if probed:
            duration, sample_rate = probed
            duration_source = "header"
    excerpt = title or _excerpt(text) or job_id
    search = " ".join(
        part for part in (title or "", text, voice_name, voice_id or "", job_id) if part
    ).casefold()
    return {
        "id": job_id,
        "readable": True,
        "status": status,
        "raw_status": raw_status,
        "title": title,
        "text": text,
        "excerpt": excerpt,
        "voice_id": voice_id,
        "voice_name": voice_name,
        "voice_name_source": voice_source,
        "created_at": document.get("created_at") if isinstance(document.get("created_at"), str) else None,
        "completed_at": document.get("completed_at") if isinstance(document.get("completed_at"), str) else None,
        "updated_at": document.get("updated_at") if isinstance(document.get("updated_at"), str) else None,
        "duration_sec": duration,
        "duration_source": duration_source,
        "sample_rate": sample_rate,
        "audio_available": wav is not None,
        "mp3_available": mp3 is not None,
        "error": document.get("error") if isinstance(document.get("error"), str) else None,
        "settings": document.get("settings") if isinstance(document.get("settings"), dict) else None,
        "settings_present": isinstance(document.get("settings"), dict),
        "seed": document.get("seed", None),
        "checkpoint": document.get("checkpoint") if isinstance(document.get("checkpoint"), str) else None,
        "package_version": document.get("package_version") if isinstance(document.get("package_version"), str) else None,
        "device_requested": document.get("device_requested"),
        "device_used": document.get("device_used"),
        "language_id": document.get("language_id"),
        "pipeline_version": document.get("pipeline_version"),
        "schema_version": document.get("schema_version"),
        "elapsed_sec": document.get("elapsed_sec"),
        "plan": document.get("plan") if isinstance(document.get("plan"), list) else None,
        "legacy": document.get("schema_version") is None or document.get("voice_name") in (None, ""),
        "search_text": search,
        "_resolved_wav": str(wav) if wav else None,
        "_resolved_mp3": str(mp3) if mp3 else None,
        "wav_name": wav.name if wav else None,
        "mp3_name": mp3.name if mp3 else None,
    }


def _public(record: dict) -> dict:
    hidden = {"search_text", "_resolved_wav", "_resolved_mp3", "raw_status"}
    return {key: value for key, value in record.items() if key not in hidden}


def _resolve_output(stored: object, job_id: str, kind: str, folder: Path) -> Path | None:
    suffix = f".{kind}"
    candidates: list[Path] = []
    if isinstance(stored, str) and stored:
        candidates.append(Path(stored))
    candidates.append(OUTPUTS / f"{job_id}{suffix}")
    candidates.append(folder / f"output{suffix}")
    for candidate in candidates:
        safe = _safe_audio(candidate, folder)
        if safe is not None and safe.is_file() and safe.suffix.lower() == suffix:
            return safe
    return None


def _safe_audio(candidate: object, folder: Path) -> Path | None:
    if not candidate:
        return None
    try:
        path = confine(Path(str(candidate)), ROOT)
    except (ValueError, OSError):
        return None
    outputs = OUTPUTS.resolve()
    job_root = folder.resolve()
    if path != job_root and job_root not in path.parents and outputs != path and outputs not in path.parents:
        return None
    if path.suffix.lower() not in {".wav", ".mp3"}:
        return None
    return path


def _probe_wav(path: Path) -> tuple[float, int] | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return round(handle.getnframes() / rate, 3), rate
    except (wave.Error, EOFError, OSError):
        return None


def _excerpt(text: str, limit: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _parse_bound(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _profiles(root: Path | None) -> list[dict]:
    from .voice_profiles import list_profiles

    try:
        return list_profiles(root)
    except (OSError, ProfileError):
        return []
