"""Shared checks for documentary plans. DeepSeek cannot add executable fields."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

PRESETS = ("cinematic_dark", "archival_paper", "clean_editorial")
FORBIDDEN = {
    "css", "javascript", "script", "shell", "command", "html", "exec",
    "url", "srcdoc", "innerhtml",
}


class PlanError(ValueError):
    pass


class NeedsAssets(PlanError):
    pass


class NeedsReview(PlanError):
    pass


def reject_forbidden(payload, where: str = "plan") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN:
                raise PlanError(f"{where} contains unsupported field {key!r}")
            reject_forbidden(value, where)
    elif isinstance(payload, list):
        for item in payload:
            reject_forbidden(item, where)


def require_quote(quote: str, passage: str) -> str:
    if not isinstance(quote, str) or not quote.strip() or quote not in passage:
        raise PlanError("Every beat needs an evidence quote that appears exactly in the selected passage")
    return quote


def number_in_text(number, text: str) -> bool:
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        return False
    token = str(int(number)) if float(number).is_integer() else str(number)
    return re.search(rf"(?<!\d){re.escape(token)}(?!\d)", text) is not None


def schedule(count: int, duration: float, hold: float = 2.0) -> list[dict]:
    if not 3 <= count <= 4:
        raise PlanError("A clip needs 3 or 4 beats, and missing facts are not invented to fill that range")
    usable = duration - hold
    if usable < count * 1.4:
        raise PlanError("Duration is too short for these beats and the final hold")
    slot = usable / count
    return [
        {"start": round(index * slot, 3), "end": round((index + 1) * slot, 3)}
        for index in range(count)
    ]


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: str | None) -> Path:
    if not path:
        raise NeedsAssets("This animation needs a local asset path")
    file = Path(path)
    if not file.is_file():
        raise NeedsAssets(f"Required asset is missing: {file.name}")
    return file
