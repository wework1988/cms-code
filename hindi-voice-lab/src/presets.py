"""Delivery presets as visible Chatterbox generation settings.

These are experimental combinations of parameters that chatterbox-tts 0.1.7
actually accepts on ChatterboxMultilingualTTS.generate(). They are not emotion
labels, and the model has no emotion prompt or SSML input.

Verified against the installed 0.1.7 source: exaggeration, cfg_weight,
temperature, repetition_penalty, min_p, top_p. Temperature stays at the
package default of 0.8. Exaggeration and cfg_weight are the only knobs that
move, because the model authors describe higher exaggeration as faster and
more dramatic, and a lower cfg_weight as looser pacing.
"""

from __future__ import annotations

MODEL_PARAMETERS = (
    "exaggeration",
    "cfg_weight",
    "temperature",
    "repetition_penalty",
    "min_p",
    "top_p",
)

_SHARED = {
    "temperature": 0.8,
    "repetition_penalty": 2.0,
    "min_p": 0.05,
    "top_p": 1.0,
}

PRESETS: dict[str, dict] = {
    "neutral": {
        "label": "Neutral",
        "exaggeration": 0.5,
        "cfg_weight": 0.5,
        **_SHARED,
        "note": "The installed model's own defaults. A steady reading, not an emotion mode.",
    },
    "warm": {
        "label": "Warm storyteller",
        "exaggeration": 0.65,
        "cfg_weight": 0.35,
        **_SHARED,
        "note": (
            "Experimental. Exaggeration is a step above the default and CFG is lower, "
            "which this model associates with a looser, more animated pace. It does not "
            "guarantee a warm emotion."
        ),
    },
    "serious": {
        "label": "Serious documentary",
        "exaggeration": 0.4,
        "cfg_weight": 0.55,
        **_SHARED,
        "note": (
            "Experimental. Exaggeration is slightly below the default so the model is "
            "less pushed toward a faster dramatic read, and CFG stays near the default. "
            "It does not guarantee a serious tone."
        ),
    },
    "dramatic": {
        "label": "Dramatic",
        "exaggeration": 0.75,
        "cfg_weight": 0.3,
        **_SHARED,
        "note": (
            "Experimental. This is the strongest of these presets: exaggeration 0.75 and "
            "CFG 0.3, in the range the model authors describe as more dramatic. Bigger "
            "values are not used, because they are not assumed to sound better."
        ),
    },
}


def preset_choices() -> list[tuple[str, str]]:
    return [(item["label"], key) for key, item in PRESETS.items()]


def preset_values(preset_id: str) -> dict:
    try:
        preset = PRESETS[preset_id]
    except KeyError as exc:
        raise KeyError(f"Unknown delivery preset {preset_id!r}.") from exc
    return {name: preset[name] for name in MODEL_PARAMETERS}


def preset_note(preset_id: str) -> str:
    try:
        return str(PRESETS[preset_id]["note"])
    except KeyError as exc:
        raise KeyError(f"Unknown delivery preset {preset_id!r}.") from exc


def matching_preset(settings: dict) -> str | None:
    for key, preset in PRESETS.items():
        if all(abs(float(settings.get(name)) - float(preset[name])) < 1e-6 for name in MODEL_PARAMETERS):
            return key
    return None
