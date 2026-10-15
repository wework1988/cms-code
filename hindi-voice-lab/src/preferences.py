"""Local studio preferences. One file, written atomically.

Settings are stored per voice. Existing voices with no saved settings receive
conservative defaults the first time they are opened.
"""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path

from .config import DATA, confine, offline_enabled, requested_device
from .presets import PRESETS, preset_values
from .voice_profiles import ProfileError, validate_profile_id

PREFERENCES_VERSION = 1
PREFERENCES_NAME = "preferences.json"


class PreferenceError(ValueError):
    """Studio preferences could not be read or saved."""


def preferences_path(root: Path | None = None) -> Path:
    base = Path(root) if root is not None else DATA
    return confine(base / PREFERENCES_NAME, base)


def load_preferences(root: Path | None = None) -> dict:
    path = preferences_path(root)
    if not path.is_file():
        return _empty()
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PreferenceError(f"Could not read preferences: {exc}") from exc
    if not isinstance(document, dict):
        raise PreferenceError("Preferences file is not an object.")
    document.setdefault("version", PREFERENCES_VERSION)
    document.setdefault("selected_voice_id", None)
    document.setdefault("default_voice_id", None)
    document.setdefault("last_screen", "voices")
    document.setdefault("draft_text", "")
    document.setdefault("draft_title", "")
    document.setdefault("voices", {})
    if not isinstance(document["voices"], dict):
        document["voices"] = {}
    return document


def save_preferences(document: dict, root: Path | None = None) -> dict:
    path = preferences_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(document)
    payload["version"] = PREFERENCES_VERSION
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return payload


def default_settings() -> dict:
    values = preset_values("neutral")
    try:
        device = requested_device()
    except RuntimeError:
        device = "auto"
    return {
        "preset": "neutral",
        "consistent": True,
        "device": device,
        "offline": offline_enabled(),
        "sentence_pause_ms": 450,
        "paragraph_pause_ms": 800,
        "seed": secrets.randbelow(2_147_483_647),
        **values,
    }


def ensure_voice_settings(profile_id: str, root: Path | None = None) -> dict:
    validate_profile_id(profile_id)
    document = load_preferences(root)
    voices = document["voices"]
    if profile_id not in voices or not isinstance(voices.get(profile_id), dict):
        voices[profile_id] = default_settings()
        save_preferences(document, root)
    return dict(voices[profile_id])


def save_voice_settings(profile_id: str, settings: dict, root: Path | None = None) -> dict:
    validate_profile_id(profile_id)
    document = load_preferences(root)
    document["voices"][profile_id] = _checked_settings(settings)
    save_preferences(document, root)
    return dict(document["voices"][profile_id])


def reset_voice_settings(profile_id: str, root: Path | None = None) -> dict:
    validate_profile_id(profile_id)
    document = load_preferences(root)
    previous = document["voices"].get(profile_id) if isinstance(document["voices"].get(profile_id), dict) else {}
    fresh = default_settings()
    if isinstance(previous, dict) and previous.get("seed") is not None:
        fresh["seed"] = previous["seed"]
    document["voices"][profile_id] = fresh
    save_preferences(document, root)
    return dict(fresh)


def select_voice(profile_id: str | None, root: Path | None = None, make_default: bool = False) -> dict:
    document = load_preferences(root)
    if profile_id:
        validate_profile_id(profile_id)
        ensure_voice_settings(profile_id, root)
        document = load_preferences(root)
        document["selected_voice_id"] = profile_id
        if make_default or not document.get("default_voice_id"):
            document["default_voice_id"] = profile_id
    else:
        document["selected_voice_id"] = None
    document["last_screen"] = "speak"
    return save_preferences(document, root)


def save_draft(text: str, title: str, root: Path | None = None, screen: str | None = None) -> dict:
    document = load_preferences(root)
    document["draft_text"] = text if isinstance(text, str) else ""
    document["draft_title"] = " ".join((title or "").split())[:120]
    if screen in {"voices", "speak", "history"}:
        document["last_screen"] = screen
    return save_preferences(document, root)


def save_screen(screen: str, root: Path | None = None) -> dict:
    if screen not in {"voices", "speak", "history"}:
        raise PreferenceError("Unknown screen.")
    document = load_preferences(root)
    document["last_screen"] = screen
    return save_preferences(document, root)


def _checked_settings(settings: dict) -> dict:
    from .generation import GenerationError, _normalize_settings

    try:
        normalized = _normalize_settings(settings)
    except GenerationError as exc:
        raise PreferenceError(str(exc)) from exc
    if settings.get("preset") not in set(PRESETS) | {"custom"}:
        normalized["preset"] = "custom" if normalized.get("preset") not in PRESETS else normalized["preset"]
    normalized["consistent"] = bool(settings.get("consistent", True))
    if normalized.get("seed") is None:
        normalized["seed"] = secrets.randbelow(2_147_483_647)
    return normalized


def _empty() -> dict:
    return {
        "version": PREFERENCES_VERSION,
        "selected_voice_id": None,
        "default_voice_id": None,
        "last_screen": "voices",
        "draft_text": "",
        "draft_title": "",
        "voices": {},
    }


def selected_id(document: dict) -> str | None:
    value = document.get("selected_voice_id") or document.get("default_voice_id")
    if not value:
        return None
    try:
        return validate_profile_id(str(value))
    except ProfileError:
        return None
