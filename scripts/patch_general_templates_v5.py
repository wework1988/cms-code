#!/usr/bin/env python3
"""v5 — final gap fixes: beat-driven camera, locked-off examples, roster definites."""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

AUTOMATION = Path(
    "/Users/averma/project/research-story-17thmay-automation/general-story/bifuracted-template"
)
CMS = Path(
    "/Applications/MAMP/htdocs/myresearch2/web/modules/custom/story_pipeline/prompts/general-story/bifuracted-template"
)
TS = datetime.now().strftime("%Y-%m-%d-%H%M")
BACKUP = Path(f"/Applications/MAMP/htdocs/myresearch2/docs/general-visual-template-backup-{TS}")
EXPORT = Path(f"/Applications/MAMP/htdocs/myresearch2/docs/general-visual-template-export-{TS}")

FILES = [
    "stage-a-story-config.md",
    "stage-b-scene-breakdown.md",
    "stage-c-image-motion.md",
]

CAMERA_BEAT_BLOCK = """
Visual-beat camera decision (plan silently; record purpose in Breakdown note):
- What must the viewer notice in this beat?
- Is the purpose geography, interaction, emotion, action, evidence, or consequence?
- Does a small camera move help communicate that — slowly, within ~5 seconds and the starting frame?
- Choose locked-off when stillness serves; choose one slow move when it improves attention,
  depth, or spatial read. Do not default every scene to locked-off or push-in.
- Review adjacent scenes: repeated choices are fine when purposeful, not as unexamined fallback.
"""

NEG_AERIAL_NOTE = """
  NEGATIVE vs camera viewpoint:
  Exclusions such as futuristic spy gadgets or police gear refer to in-story devices — not
  aerial, elevated, or overhead cinematography. Do not add negatives that would forbid
  requested camera viewpoints, natural daylight, or selective focus when the scene needs them.
"""

ROSTER_DEFINITE = """
In roster and architecture fields choose ONE definite realization — never "jeep or sedan",
"maybe an officer", or "shirt or kurta". Vehicles and transport must name one type with
identifying features, not alternatives.
"""


def patch_stage_a(text: str) -> str:
    if "Vehicles and transport must name one type" not in text:
        text = text.replace(
            "§5.5 POSITIVE IDENTITY AND RECURRING OBJECTS",
            "§5.5 POSITIVE IDENTITY AND RECURRING OBJECTS" + ROSTER_DEFINITE,
            1,
        )
    return text


def patch_stage_b(text: str) -> str:
    if "Visual-beat camera decision" not in text:
        text = text.replace(
            "Insert / side / low / overhead viewpoints are valid when the beat requires them.\n",
            "Insert / side / low / overhead viewpoints are valid when the beat requires them.\n"
            + CAMERA_BEAT_BLOCK,
            1,
        )
    if "K. Role continuity" not in text:
        text = text.replace(
            "J. Camera purpose in Breakdown note matches Camera scale and Visual beat type.",
            "J. Camera purpose in Breakdown note matches Camera scale and Visual beat type.\n"
            "K. Role continuity — if an established suspect or witness becomes the driver or operator,\n"
            "   keep that same person's identity and clothing; do not invent a new unnamed figure.",
            1,
        )
    return text


def patch_stage_c(text: str) -> str:
    text = text.replace(
        '  - "Over-shoulder view holds on the analyst and the grainy monitor showing the yard recording."',
        '  - "Locked-off over-shoulder view on the analyst and the grainy monitor showing the yard recording."',
        1,
    )
    text = text.replace(
        """     - subtle handheld drift rarely, only for subjective tension — no shake or jitter
  - rack focus only when the video workflow supports it, two depth planes are already
    visible in frame, and the image style permits selective focus — never to hide poor faces""",
        """     - subtle handheld drift rarely, only for subjective tension — no shake or jitter
     - rack focus only when the video workflow supports it, two depth planes are already
       visible in frame, and the image style permits selective focus — never to hide poor faces""",
        1,
    )
    if "NEGATIVE vs camera viewpoint" not in text:
        text = text.replace(
            "  Stage A may list story-specific negatives; Stage C adds only those relevant to THIS scene.",
            "  Stage A may list story-specific negatives; Stage C adds only those relevant to THIS scene."
            + NEG_AERIAL_NOTE,
            1,
        )
    return text


PATCHERS = {
    "stage-a-story-config.md": patch_stage_a,
    "stage-b-scene-breakdown.md": patch_stage_b,
    "stage-c-image-motion.md": patch_stage_c,
}

CHECKS = {
    "stage-a-story-config.md": ["SHARED §1C", "PART 3 — INPUT SLOTS", "Vehicles and transport must name"],
    "stage-b-scene-breakdown.md": ["Visual-beat camera decision", "PART 14A", "PART 22B", "PART 3 — INPUT SLOTS"],
    "stage-c-image-motion.md": [
        "SHARED §1C", "CHARACTER CLARITY", "Locked-off over-shoulder",
        "NEGATIVE vs camera viewpoint", "3000 characters", " ||", "NEXT_RANGE:",
    ],
}

FORBIDDEN = [
    "When uncertain, choose a static hold",
    "view holds on",
    "Inspector Kavya",
    "Jaipur",
]


def validate(name: str, text: str) -> list[str]:
    errs = []
    for t in CHECKS[name]:
        if t not in text:
            errs.append(f"missing {t!r}")
    for t in FORBIDDEN:
        if t in text:
            errs.append(f"forbidden {t!r}")
    return errs


def main() -> int:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for label, root in [("automation", AUTOMATION), ("cms-module", CMS)]:
        d = BACKUP / label
        d.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            shutil.copy2(root / f, d / f)
    print("Backup:", BACKUP)

    ok = True
    for f in FILES:
        raw = (CMS / f).read_text(encoding="utf-8")
        patched = PATCHERS[f](raw)
        errs = validate(f, patched)
        if errs:
            ok = False
            print(f"FAIL {f}:")
            for e in errs:
                print(" ", e)
            continue
        for root in (CMS, EXPORT):
            root.mkdir(parents=True, exist_ok=True)
            (root / f).write_text(patched, encoding="utf-8")
        print(f"OK {f}")

    if ok:
        for f in FILES:
            (AUTOMATION / f).write_text((CMS / f).read_text(encoding="utf-8"), encoding="utf-8")
        print("Synced automation repo")
    print("Export:", EXPORT)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
