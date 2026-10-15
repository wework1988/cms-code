"""Timeline semantic plan validation. Reveal times are not accepted from the model."""
from __future__ import annotations

import re
from typing import Any

from .styles import DEFAULT_STYLE, LIMITS

SCHEMA_VERSION = "1.0"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
YEAR_TOKEN = re.compile(r"(?<!\d)(\d{4})(?!\d)")
MONTHS = (
    "जनवरी", "फरवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त",
    "सितंबर", "सितम्बर", "अक्टूबर", "नवंबर", "नवम्बर", "दिसंबर", "दिसम्बर",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)
FORBIDDEN = {
    "css", "javascript", "script", "shell", "command", "html", "exec",
    "geometry", "coordinates", "geojson", "polygon", "reveal", "x", "y",
}


class TimelineValidationError(ValueError):
    pass


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise TimelineValidationError(message)


def year_in_quote(year: int, quote: str) -> bool:
    """A year counts only as its own number, not as digits inside a longer number."""
    return re.search(rf"(?<!\d){int(year)}(?!\d)", quote) is not None


def _reject_forbidden(payload: Any, where: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in FORBIDDEN:
                raise TimelineValidationError(
                    f"{where} contains unsupported field {key!r}. "
                    "Editorial text cannot add renderer commands or coordinates."
                )
            _reject_forbidden(value, where)
    elif isinstance(payload, list):
        for item in payload:
            _reject_forbidden(item, where)


def _label_claims_exact_date(label: str) -> bool:
    lowered = label.casefold()
    if any(month in lowered for month in MONTHS):
        return True
    if re.search(r"\d{1,2}[./-]\d{1,2}", label):
        return True
    return False


def validate_style(raw: dict | None) -> dict:
    style = dict(DEFAULT_STYLE)
    if not raw:
        return style
    _require(isinstance(raw, dict), "style must be an object")
    _reject_forbidden(raw, "style")
    if "preset" in raw and raw["preset"] != "documentary":
        raise TimelineValidationError("Only the documentary timeline preset is supported")
    for key in ("background", "background_end", "accent", "text", "muted", "track"):
        if key in raw:
            _require(isinstance(raw[key], str) and bool(HEX.fullmatch(raw[key])), f"{key} must be a #RRGGBB colour")
            style[key] = raw[key]
    if "layout" in raw and raw["layout"] != "horizontal":
        raise TimelineValidationError("Only the horizontal timeline layout is supported")
    if "transition_seconds" in raw:
        value = raw["transition_seconds"]
        _require(isinstance(value, (int, float)) and 0.3 <= float(value) <= 2.0, "transition_seconds must be 0.3–2")
        style["transition_seconds"] = float(value)
    if "final_hold_seconds" in raw:
        value = raw["final_hold_seconds"]
        _require(isinstance(value, (int, float)) and 2.0 <= float(value) <= 8.0, "final_hold_seconds must be 2–8")
        style["final_hold_seconds"] = float(value)
    return style


def validate_events(events: list, passage: str) -> list[dict]:
    _require(isinstance(events, list) and 3 <= len(events) <= 4, "A timeline clip needs 3 or 4 events from the source, not fewer and not a padded list")
    cleaned = []
    seen_ids = set()
    previous_year = None
    for index, event in enumerate(events, start=1):
        _require(isinstance(event, dict), "Event must be an object")
        _reject_forbidden(event, "event")
        event_id = event.get("id") or f"event_{index:02d}"
        _require(isinstance(event_id, str) and re.fullmatch(r"event_\d{2}", event_id), "Event id must look like event_01")
        _require(event_id not in seen_ids, f"Duplicate event id {event_id}")
        seen_ids.add(event_id)
        quote = event.get("evidence_quote")
        _require(isinstance(quote, str) and quote.strip() != "", "Every milestone needs a nonempty evidence quote")
        _require(quote in passage, "evidence_quote must be an exact substring of the selected passage")
        precision = event.get("date_precision")
        _require(precision in ("year", "undated"), "date_precision must be year or undated. Exact dates, ranges, decades, and BCE/CE are not supported")
        year = event.get("year")
        label = event.get("date_label")
        _require(isinstance(label, str) and label.strip() != "", "date_label is required")
        label = label.strip()
        _require(len(label) <= LIMITS["date_label"], f"date_label is longer than {LIMITS['date_label']} characters")
        _require(not _label_claims_exact_date(label), "date_label must not present an exact day or month. Use the year, or an undated stage label")
        caption = event.get("caption")
        _require(isinstance(caption, str) and caption.strip() != "", "caption is required")
        caption = caption.strip()
        _require(len(caption) <= LIMITS["caption"], f"caption is longer than {LIMITS['caption']} characters. Shorten it; do not shrink it into the frame")
        if precision == "year":
            _require(isinstance(year, int) and not isinstance(year, bool), "A year event needs an integer year")
            _require(1000 <= year <= 2099, f"Year {year} is outside the supported range 1000–2099")
            _require(year_in_quote(year, quote), f"Year {year} is not a standalone number in the evidence quote")
            _require(label == str(year), "For a year milestone, date_label must be that year and nothing else")
            if previous_year is not None and year <= previous_year:
                raise TimelineValidationError(
                    f"Years must move forward. {year} does not follow {previous_year}"
                )
            previous_year = year
        else:
            _require(year is None, "An undated stage must set year to null")
            _require(not YEAR_TOKEN.search(label), "An undated label must not look like a year")
        _require(event.get("needs_verification") is True, "needs_verification must be true. A matching quote is source support, not a fact check")
        cleaned.append({
            "id": event_id,
            "date_label": label,
            "year": year if precision == "year" else None,
            "caption": caption,
            "evidence_quote": quote,
            "date_precision": precision,
            "needs_verification": True,
        })
    return cleaned


def validate_semantic_plan(plan: dict, passage: str, *, duration_seconds: float) -> dict:
    _require(isinstance(plan, dict), "Timeline plan must be an object")
    _reject_forbidden(plan, "plan")
    _require(plan.get("schema_version") == SCHEMA_VERSION, "schema_version must be 1.0")
    _require(plan.get("animation_type") == "timeline", "animation_type must be timeline")
    title = plan.get("title")
    _require(isinstance(title, str) and title.strip() != "", "title is required")
    title = title.strip()
    _require(len(title) <= LIMITS["title"], f"title is longer than {LIMITS['title']} characters")
    _require(plan.get("language") in ("hi", "en"), "language must be hi or en")
    _require(plan.get("spacing") == "equal_steps", "spacing must be equal_steps. Proportional historical spacing is not implemented")
    duration = plan.get("duration_seconds")
    _require(isinstance(duration, (int, float)) and abs(float(duration) - float(duration_seconds)) < 0.01, "duration_seconds must match the job setting")
    _require(6 <= float(duration_seconds) <= 30, "duration must be 6–30 seconds")
    events = validate_events(plan.get("events") or [], passage)
    emphasis = plan.get("emphasis_event")
    if emphasis is not None:
        _require(isinstance(emphasis, str) and any(event["id"] == emphasis for event in events), "emphasis_event must be one of the event ids")
    style = validate_style(plan.get("style") if isinstance(plan.get("style"), dict) else None)
    return {
        "schema_version": SCHEMA_VERSION,
        "animation_type": "timeline",
        "title": title,
        "language": plan["language"],
        "duration_seconds": float(duration_seconds),
        "spacing": "equal_steps",
        "events": events,
        "emphasis_event": emphasis,
        "style": style,
        "verification_note": (
            "Each milestone is tied to an exact quote in the selected passage. "
            "That is source support, not an independent fact check."
        ),
    }
