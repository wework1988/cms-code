"""Local HTTP API and studio pages. No public sharing and no hosted inference."""

from __future__ import annotations

import copy
import re
import threading
import uuid
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from .audio_processing import AudioError, extract_segment, ffmpeg_available, probe_audio, recommend_window
from .config import (
    LANGUAGE_ID,
    MODEL_SAMPLE_RATE,
    PACKAGE_VERSION,
    REFERENCES,
    ROOT,
    T3_FILENAME,
    TMP,
    confine,
    offline_enabled,
    requested_device,
)
from .generation import GenerationError, generate_speech, generation_busy, live_progress
from .history import HistoryError, audio_path, get_record, query_history
from .model_adapter import ModelService
from .narration import NARRATION_EXAMPLE, NarrationError, format_preview, plan_narration
from .preferences import (
    PreferenceError,
    ensure_voice_settings,
    load_preferences,
    reset_voice_settings,
    save_draft,
    save_screen,
    save_voice_settings,
    select_voice,
    selected_id,
)
from .presets import PRESETS, matching_preset, preset_values
from .text_processing import MAX_TEXT_CHARS, SAMPLE_HINDI
from .voice_profiles import (
    NOT_A_MODEL,
    PROFILE_KIND,
    ProfileError,
    list_profiles,
    load_profile,
    save_profile,
    update_profile,
    validate_profile_id,
)

WEB = ROOT / "web"
UPLOAD_RE = re.compile(r"^ref-[a-f0-9]{12}$")
SERVICE = ModelService()
_RESULT = {"error": None, "result": None}
_RESULT_LOCK = threading.Lock()


def create_app() -> Starlette:
    routes = [
        Route("/", studio_page),
        Route("/studio.css", studio_css),
        Route("/studio.js", studio_js),
        Route("/api/studio", studio_state, methods=["GET"]),
        Route("/api/screen", set_screen, methods=["POST"]),
        Route("/api/draft", save_editor, methods=["PUT"]),
        Route("/api/voices", voices_collection, methods=["GET", "POST"]),
        Route("/api/voices/{voice_id}", voice_detail, methods=["PATCH"]),
        Route("/api/voices/{voice_id}/use", use_voice, methods=["POST"]),
        Route("/api/voices/{voice_id}/reference", voice_reference, methods=["GET"]),
        Route("/api/voices/{voice_id}/settings", voice_settings, methods=["PUT"]),
        Route("/api/voices/{voice_id}/settings/reset", voice_settings_reset, methods=["POST"]),
        Route("/api/uploads", create_upload, methods=["POST"]),
        Route("/api/uploads/{upload_id}", upload_detail, methods=["GET"]),
        Route("/api/uploads/{upload_id}/preview", upload_preview, methods=["POST"]),
        Route("/api/uploads/{upload_id}/audio", upload_audio, methods=["GET"]),
        Route("/api/preview-audio/{name}", preview_file, methods=["GET"]),
        Route("/api/preview", narration_preview, methods=["POST"]),
        Route("/api/generate", start_generate, methods=["POST"]),
        Route("/api/generation", generation_status, methods=["GET"]),
        Route("/api/history", history_collection, methods=["GET"]),
        Route("/api/history/{job_id}", history_detail, methods=["GET"]),
        Route("/api/history/{job_id}/audio/{kind}", history_audio, methods=["GET"]),
    ]
    return Starlette(debug=False, routes=routes)


async def studio_page(_: Request) -> FileResponse:
    return FileResponse(WEB / "index.html")


async def studio_css(_: Request) -> FileResponse:
    return FileResponse(WEB / "studio.css", media_type="text/css")


async def studio_js(_: Request) -> FileResponse:
    return FileResponse(WEB / "studio.js", media_type="text/javascript")


async def studio_state(_: Request) -> JSONResponse:
    return JSONResponse(_studio_payload())


async def set_screen(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        save_screen(str(body.get("screen") or ""))
    except PreferenceError as exc:
        return _error(str(exc), 400)
    return JSONResponse(_studio_payload())


async def save_editor(request: Request) -> JSONResponse:
    body = await _body(request)
    text = body.get("text") if isinstance(body.get("text"), str) else ""
    title = body.get("title") if isinstance(body.get("title"), str) else ""
    if len(text) > MAX_TEXT_CHARS:
        return _error(f"Text is longer than {MAX_TEXT_CHARS} characters.", 400)
    screen = body.get("screen") if body.get("screen") in {"voices", "speak", "history"} else None
    save_draft(text, title, screen=screen)
    return JSONResponse({"ok": True})


async def voices_collection(request: Request) -> JSONResponse:
    if request.method == "GET":
        query = request.query_params.get("q", "")
        return JSONResponse({"voices": _voice_cards(query)})
    body = await _body(request)
    try:
        upload = _upload_dir(str(body.get("upload_id") or ""))
        source = _original_file(upload)
        start = float(body.get("start"))
        end = float(body.get("end"))
        preview = TMP / "previews" / f"{uuid.uuid4().hex}.wav"
        info = extract_segment(source, preview, start, end)
        probed = probe_audio(source)
        description = body.get("description") if isinstance(body.get("description"), str) else ""
        document = save_profile(
            str(body.get("name") or ""),
            info.path,
            {
                "original_file": source.name,
                "original_path": str(source.relative_to(ROOT)),
                "start_sec": start,
                "end_sec": end,
                "source_duration_sec": probed.duration_sec,
                "source_sample_rate": probed.sample_rate,
                "source_channels": probed.channels,
                "clip_duration_sec": info.duration_sec,
                "clip_sample_rate": info.sample_rate,
                "clip_channels": info.channels,
                "warnings": info.warnings,
            },
            description=description,
        )
        use_now = body.get("use_now", True) is not False
        if use_now:
            select_voice(document["id"], make_default=True)
        else:
            ensure_voice_settings(document["id"])
    except (AudioError, ProfileError, PreferenceError, TypeError, ValueError) as exc:
        return _error(str(exc), 400)
    return JSONResponse({"voice": _card(document), "studio": _studio_payload()})


async def voice_detail(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        voice_id = validate_profile_id(request.path_params["voice_id"])
        name = body.get("name") if isinstance(body.get("name"), str) else None
        description = body.get("description") if "description" in body else None
        if description is not None and not isinstance(description, str):
            return _error("Description must be text.", 400)
        updated = update_profile(voice_id, display_name=name, description=description)
    except (ProfileError, KeyError) as exc:
        return _error(str(exc), 400)
    return JSONResponse({"voice": _card(updated)})


async def use_voice(request: Request) -> JSONResponse:
    try:
        voice_id = validate_profile_id(request.path_params["voice_id"])
        load_profile(voice_id)
        select_voice(voice_id, make_default=True)
    except (ProfileError, PreferenceError) as exc:
        return _error(str(exc), 400)
    return JSONResponse(_studio_payload())


async def voice_reference(request: Request) -> Response:
    try:
        voice_id = validate_profile_id(request.path_params["voice_id"])
        profile = load_profile(voice_id)
        path = confine(Path(profile["reference_path"]), ROOT)
    except (ProfileError, ValueError) as exc:
        return _error(str(exc), 404)
    return FileResponse(path, media_type="audio/wav", filename=f"{voice_id}.wav")


async def voice_settings(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        voice_id = validate_profile_id(request.path_params["voice_id"])
        load_profile(voice_id)
        saved = save_voice_settings(voice_id, _settings_from_body(body))
    except (ProfileError, PreferenceError) as exc:
        return _error(str(exc), 400)
    return JSONResponse({"settings": saved})


async def voice_settings_reset(request: Request) -> JSONResponse:
    try:
        voice_id = validate_profile_id(request.path_params["voice_id"])
        load_profile(voice_id)
        saved = reset_voice_settings(voice_id)
    except (ProfileError, PreferenceError) as exc:
        return _error(str(exc), 400)
    return JSONResponse({"settings": saved, "studio": _studio_payload()})


async def create_upload(request: Request) -> JSONResponse:
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "filename"):
        return _error("Choose an audio file.", 400)
    suffix = Path(upload.filename or "").suffix.lower()
    upload_id = f"ref-{uuid.uuid4().hex[:12]}"
    folder = confine(REFERENCES / upload_id, REFERENCES)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"original{suffix}"
    try:
        contents = await upload.read()
        destination.write_bytes(contents)
        info = probe_audio(destination)
    except (AudioError, OSError, ValueError) as exc:
        return _error(str(exc), 400)
    start, end = recommend_window(info.duration_sec)
    return JSONResponse(_upload_payload(upload_id, info, start, end))


async def upload_detail(request: Request) -> JSONResponse:
    try:
        folder = _upload_dir(request.path_params["upload_id"])
        source = _original_file(folder)
        info = probe_audio(source)
    except (AudioError, ValueError) as exc:
        return _error(str(exc), 404)
    start, end = recommend_window(info.duration_sec)
    return JSONResponse(_upload_payload(folder.name, info, start, end))


async def upload_preview(request: Request) -> JSONResponse:
    body = await _body(request)
    try:
        folder = _upload_dir(request.path_params["upload_id"])
        source = _original_file(folder)
        start = float(body.get("start"))
        end = float(body.get("end"))
        name = f"{folder.name}-{uuid.uuid4().hex[:8]}.wav"
        destination = confine(TMP / "previews" / name, TMP)
        info = extract_segment(source, destination, start, end)
    except (AudioError, TypeError, ValueError) as exc:
        return _error(str(exc), 400)
    return JSONResponse(
        {
            "audio_url": f"/api/preview-audio/{name}",
            "duration_sec": info.duration_sec,
            "warnings": info.warnings,
            "details": {
                "sample_rate": info.sample_rate,
                "channels": info.channels,
                "note": NOT_A_MODEL,
            },
        }
    )


async def upload_audio(request: Request) -> Response:
    try:
        folder = _upload_dir(request.path_params["upload_id"])
        source = _original_file(folder)
    except ValueError as exc:
        return _error(str(exc), 404)
    return FileResponse(source, filename=source.name)


async def preview_file(request: Request) -> Response:
    name = request.path_params["name"]
    if not re.fullmatch(r"ref-[a-f0-9]{12}-[a-f0-9]{8}\.wav", name):
        return _error("Preview was not found.", 404)
    path = confine(TMP / "previews" / name, TMP)
    if not path.is_file():
        return _error("Preview was not found.", 404)
    return FileResponse(path, media_type="audio/wav")


async def narration_preview(request: Request) -> JSONResponse:
    body = await _body(request)
    text = body.get("text") if isinstance(body.get("text"), str) else ""
    settings = _effective_settings(body)
    try:
        plan = plan_narration(text, int(settings["sentence_pause_ms"]), int(settings["paragraph_pause_ms"]))
    except NarrationError as exc:
        return _error(str(exc), 400)
    label = PRESETS.get(settings.get("preset"), {}).get("label", settings.get("preset"))
    if matching_preset(settings) != settings.get("preset"):
        label = f"{label} (adjusted)"
    return JSONResponse(
        {
            "preview": format_preview(plan, settings, str(label)),
            "segments": [piece.model_text for piece in plan.model_segments()],
            "events": plan.to_dict(),
            "settings": settings,
        }
    )


async def start_generate(request: Request) -> JSONResponse:
    if generation_busy():
        return _error("Another generation is already running. Wait for it to finish.", 409)
    body = await _body(request)
    text = body.get("text") if isinstance(body.get("text"), str) else ""
    title = body.get("title") if isinstance(body.get("title"), str) else ""
    new_take = bool(body.get("new_take"))
    try:
        voice_id = validate_profile_id(str(body.get("voice_id") or ""))
        load_profile(voice_id)
        saved = ensure_voice_settings(voice_id)
        consistent = bool(saved.get("consistent", True))
        if consistent:
            settings = copy.deepcopy(saved)
        else:
            settings = _settings_from_body(body.get("settings") if isinstance(body.get("settings"), dict) else saved)
        settings = copy.deepcopy(settings)
        save_draft(text, title, screen="speak")
    except (ProfileError, PreferenceError) as exc:
        return _error(str(exc), 400)
    snapshot_text = text
    snapshot_title = title or None
    snapshot_settings = settings
    reuse = consistent and not new_take

    def run() -> None:
        try:
            result = generate_speech(
                voice_id,
                snapshot_text,
                snapshot_settings,
                SERVICE,
                title=snapshot_title,
                force_new=new_take or not consistent,
                reuse_complete=reuse,
            )
            public = {
                "job_id": result["job_id"],
                "cache_hit": bool(result.get("cache_hit")),
                "resumed": bool(result.get("resumed")),
                "notes": result.get("notes") or [],
                "device_used": result.get("device_used"),
                "sample_rate": result.get("sample_rate"),
                "elapsed_sec": result.get("elapsed_sec"),
                "wav_url": f"/api/history/{result['job_id']}/audio/wav",
                "mp3_url": f"/api/history/{result['job_id']}/audio/mp3" if result.get("mp3_path") else None,
                "mp3_error": result.get("mp3_error"),
            }
            with _RESULT_LOCK:
                _RESULT["result"] = public
                _RESULT["error"] = None
        except GenerationError as exc:
            with _RESULT_LOCK:
                _RESULT["error"] = str(exc)

    threading.Thread(target=run, name="hindi-voice-generate", daemon=True).start()
    return JSONResponse({"accepted": True, "voice_id": voice_id}, status_code=202)


async def generation_status(_: Request) -> JSONResponse:
    with _RESULT_LOCK:
        result = copy.deepcopy(_RESULT["result"])
        error = _RESULT["error"]
    return JSONResponse({"busy": generation_busy(), "progress": live_progress(), "result": result, "error": error})


async def history_collection(request: Request) -> JSONResponse:
    params = request.query_params
    try:
        page = int(params.get("page", "1"))
        page_size = int(params.get("page_size", "20"))
    except ValueError:
        return _error("Page must be a number.", 400)
    payload = query_history(
        text=params.get("q", ""),
        voice_id=params.get("voice_id", ""),
        status=params.get("status", ""),
        created_from=params.get("from", ""),
        created_to=params.get("to", ""),
        sort=params.get("sort", "newest"),
        page=page,
        page_size=page_size,
    )
    return JSONResponse(payload)


async def history_detail(request: Request) -> JSONResponse:
    try:
        return JSONResponse(get_record(request.path_params["job_id"]))
    except HistoryError as exc:
        return _error(str(exc), 404)


async def history_audio(request: Request) -> Response:
    kind = request.path_params["kind"]
    if kind == "wav":
        media = "audio/wav"
    elif kind == "mp3":
        media = "audio/mpeg"
    else:
        return _error("Choose wav or mp3.", 404)
    try:
        path = audio_path(request.path_params["job_id"], kind)
    except HistoryError as exc:
        return _error(str(exc), 404)
    download = request.query_params.get("download") == "1"
    return FileResponse(path, media_type=media, filename=path.name, content_disposition_type="attachment" if download else "inline")


def _studio_payload() -> dict:
    document = load_preferences()
    voice_id = selected_id(document)
    settings = None
    if voice_id:
        try:
            load_profile(voice_id)
            settings = ensure_voice_settings(voice_id)
        except ProfileError:
            voice_id = None
            settings = None
    return {
        "screen": document.get("last_screen") or "voices",
        "selected_voice_id": voice_id,
        "default_voice_id": document.get("default_voice_id"),
        "draft_text": document.get("draft_text") or "",
        "draft_title": document.get("draft_title") or "",
        "settings": settings,
        "voices": _voice_cards(""),
        "presets": [
            {"id": key, "label": item["label"], "note": item["note"], **preset_values(key)}
            for key, item in PRESETS.items()
        ],
        "sample_text": SAMPLE_HINDI,
        "example_text": NARRATION_EXAMPLE,
        "checkpoint": T3_FILENAME,
        "package_version": PACKAGE_VERSION,
        "language_id": LANGUAGE_ID,
        "sample_rate": MODEL_SAMPLE_RATE,
        "mp3_available": ffmpeg_available(),
        "device": requested_device(),
        "offline": offline_enabled(),
        "reference_note": NOT_A_MODEL,
        "profile_kind": PROFILE_KIND,
    }


def _voice_cards(query: str) -> list[dict]:
    document = load_preferences()
    selected = selected_id(document)
    needle = (query or "").casefold().strip()
    cards = []
    for profile in list_profiles():
        description = profile.get("description") or ""
        if needle and needle not in profile.get("display_name", "").casefold() and needle not in description.casefold():
            continue
        card = _card(profile)
        card["selected"] = card["id"] == selected
        card["is_default"] = card["id"] == document.get("default_voice_id")
        cards.append(card)
    return cards


def _card(profile: dict) -> dict:
    name = profile.get("display_name") or profile.get("id")
    return {
        "id": profile["id"],
        "name": name,
        "description": profile.get("description") or "",
        "initials": _initials(name),
        "language": "Hindi",
        "created_at": profile.get("created_at"),
        "reference_url": f"/api/voices/{profile['id']}/reference",
        "kind": profile.get("kind"),
        "note": NOT_A_MODEL,
    }


def _initials(name: str) -> str:
    parts = [part for part in name.split() if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        word = parts[0]
        return word[:2].upper() if word.isascii() else word[:1]
    return "".join(part[0] for part in parts[:2])


def _settings_from_body(body: dict) -> dict:
    preset = str(body.get("preset") or "neutral")
    settings = {
        "preset": preset,
        "consistent": bool(body.get("consistent", True)),
        "device": body.get("device") or "auto",
        "offline": bool(body.get("offline")),
        "exaggeration": body.get("exaggeration", 0.5),
        "cfg_weight": body.get("cfg_weight", 0.5),
        "temperature": body.get("temperature", 0.8),
        "repetition_penalty": body.get("repetition_penalty", 2.0),
        "min_p": body.get("min_p", 0.05),
        "top_p": body.get("top_p", 1.0),
        "sentence_pause_ms": body.get("sentence_pause_ms", 450),
        "paragraph_pause_ms": body.get("paragraph_pause_ms", 800),
        "seed": body.get("seed", ""),
    }
    if matching_preset(settings) != preset:
        settings["preset"] = "custom"
    return settings


def _effective_settings(body: dict) -> dict:
    voice_id = body.get("voice_id")
    if body.get("use_saved") and isinstance(voice_id, str) and voice_id:
        try:
            return ensure_voice_settings(validate_profile_id(voice_id))
        except (ProfileError, PreferenceError):
            pass
    raw = body.get("settings") if isinstance(body.get("settings"), dict) else body
    return _settings_from_body(raw if isinstance(raw, dict) else {})


def _upload_dir(upload_id: str) -> Path:
    if not UPLOAD_RE.fullmatch(upload_id or ""):
        raise ValueError("Upload id is not valid.")
    folder = confine(REFERENCES / upload_id, REFERENCES)
    if not folder.is_dir():
        raise ValueError("Upload was not found.")
    return folder


def _original_file(folder: Path) -> Path:
    matches = [path for path in folder.iterdir() if path.is_file() and path.name.startswith("original.")]
    if not matches:
        raise ValueError("Upload was not found.")
    return matches[0]


def _upload_payload(upload_id: str, info, start: float, end: float) -> dict:
    return {
        "upload_id": upload_id,
        "filename": info.path.name,
        "duration_sec": info.duration_sec,
        "start": start,
        "end": end,
        "warnings": info.warnings,
        "audio_url": f"/api/uploads/{upload_id}/audio",
        "recommendation": (
            "Use a short, clean Hindi sample. This model reads about 6 seconds for the voice "
            "and 10 seconds for the decoder. A longer recording is kept, but it is not used as training."
        ),
        "details": {
            "sample_rate": info.sample_rate,
            "channels": info.channels,
            "note": NOT_A_MODEL,
        },
    }


def _error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _body(request: Request) -> dict:
    try:
        body = await request.json()
    except Exception:
        return {}
    return body if isinstance(body, dict) else {}


# Imported by tests that mount routes without starting a server.
app = create_app()
