"""Named reference profiles.

A profile stores a prepared clip for zero-shot inference. It is not a
fine-tuned model, and saving one does not train anything.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import PROFILES, confine

PROFILE_ID_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,46}[a-z0-9])?$")
PROFILE_KIND = "reference_profile"
NOT_A_MODEL = (
    "This profile stores a reference clip for zero-shot inference. "
    "It is not a fine-tuned or trained model."
)


class ProfileError(ValueError):
    """A voice profile could not be saved or loaded."""


def validate_profile_id(profile_id: str) -> str:
    if not PROFILE_ID_RE.fullmatch(profile_id or ""):
        raise ProfileError("Profile id is not valid.")
    return profile_id


def save_profile(
    display_name: str,
    reference_wav: Path,
    source_meta: dict,
    root: Path | None = None,
    description: str = "",
) -> dict:
    name = _clean_name(display_name)
    profile_id = _new_id(name)
    base = Path(root) if root is not None else PROFILES
    folder = confine(base / profile_id, base)
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "reference.wav"
    _copy_atomic(Path(reference_wav), destination)
    document = {
        "id": profile_id,
        "display_name": name,
        "description": _clean_description(description),
        "kind": PROFILE_KIND,
        "label": NOT_A_MODEL,
        "created_at": _now(),
        "reference_wav": "reference.wav",
        "source": source_meta,
    }
    _write_json(folder / "profile.json", document)
    return document


def list_profiles(root: Path | None = None) -> list[dict]:
    base = Path(root) if root is not None else PROFILES
    if not base.exists():
        return []
    found: list[dict] = []
    for folder in sorted(base.iterdir()):
        if not folder.is_dir():
            continue
        path = folder / "profile.json"
        if not path.is_file():
            continue
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            validate_profile_id(str(document.get("id", "")))
        except (OSError, json.JSONDecodeError, ProfileError):
            continue
        if document.get("kind") != PROFILE_KIND:
            continue
        found.append(document)
    found.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return found


def load_profile(profile_id: str, root: Path | None = None) -> dict:
    validate_profile_id(profile_id)
    base = Path(root) if root is not None else PROFILES
    path = confine(base / profile_id / "profile.json", base)
    if not path.is_file():
        raise ProfileError(f"No voice profile named {profile_id}.")
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("id") != profile_id or document.get("kind") != PROFILE_KIND:
        raise ProfileError("The profile file does not match its folder.")
    reference = confine(base / profile_id / "reference.wav", base)
    if not reference.is_file():
        raise ProfileError("The profile is missing its reference clip.")
    document["reference_path"] = str(reference)
    return document


def update_profile(
    profile_id: str,
    *,
    display_name: str | None = None,
    description: str | None = None,
    root: Path | None = None,
) -> dict:
    """Rename or edit details without changing the profile id or reference file."""
    loaded = load_profile(profile_id, root)
    base = Path(root) if root is not None else PROFILES
    path = confine(base / profile_id / "profile.json", base)
    document = json.loads(path.read_text(encoding="utf-8"))
    if display_name is not None:
        document["display_name"] = _clean_name(display_name)
    if description is not None:
        document["description"] = _clean_description(description)
    document["id"] = profile_id
    document["kind"] = PROFILE_KIND
    document["reference_wav"] = document.get("reference_wav") or "reference.wav"
    _write_json(path, document)
    if not Path(loaded["reference_path"]).is_file():
        raise ProfileError("The profile is missing its reference clip.")
    return load_profile(profile_id, root)


def profile_choices(root: Path | None = None) -> list[tuple[str, str]]:
    choices = []
    for document in list_profiles(root):
        label = f"{document['display_name']} ({document['id']})"
        choices.append((label, document["id"]))
    return choices


def _clean_description(description: str) -> str:
    text = " ".join((description or "").split())
    if len(text) > 240:
        raise ProfileError("Description must be 240 characters or fewer.")
    return text


def _clean_name(display_name: str) -> str:
    name = " ".join((display_name or "").split())
    if not name:
        raise ProfileError("Enter a name for this voice profile.")
    if len(name) > 80:
        raise ProfileError("Profile name must be 80 characters or fewer.")
    return name


def _new_id(display_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", display_name.lower()).strip("-")
    slug = slug[:32].strip("-")
    suffix = uuid.uuid4().hex[:8]
    candidate = f"{slug}-{suffix}" if slug else f"voice-{suffix}"
    if not PROFILE_ID_RE.fullmatch(candidate) or ".." in candidate:
        candidate = f"voice-{suffix}"
    return validate_profile_id(candidate)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_json(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _copy_atomic(source: Path, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".partial")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)
