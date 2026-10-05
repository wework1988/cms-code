#!/usr/bin/env python3
"""v3 cleanup: fix §5/§6 corruption, motion dupes, strengthen reusable rules."""

from __future__ import annotations

import re
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

BROKEN_56 = """--------------------------------------------------------------------------------
SHARED §6
§5.5 POSITIVE IDENTITY IN OUTPUT
Recurring characters and objects need positive identity descriptions in IMAGE PROMPT text —
not generic negatives alone. Before any "no identity drift" negative, state the stable traits:
apparent age band, face structure, hairstyle and colour, facial hair, glasses, build,
clothing family, footwear, and identifying accessories for people; colour, material,
shape, size, and distinctive features for recurring objects. Allow changes only when
narration, elapsed time, or an explicitly established costume change supports them.

 — SOURCE TEXT (HINDI LINE) PRESERVATION
--------------------------------------------------------------------------------"""

FIXED_55_56 = """§5.5 POSITIVE IDENTITY IN OUTPUT
Recurring characters and objects need positive identity descriptions in IMAGE PROMPT text —
not generic negatives alone. Before any "no identity drift" negative, state the stable traits:
apparent age band, face structure, hairstyle and colour, facial hair, glasses, build,
clothing family, footwear, and identifying accessories for people; colour, material,
shape, size, and distinctive features for recurring objects. Allow changes only when
narration, elapsed time, or an explicitly established costume change supports them.

On repeat appearances, restate only the traits needed for recognition — do not paste full
roster paragraphs every scene unless identity or costume changed.

--------------------------------------------------------------------------------
SHARED §6 — SOURCE TEXT (HINDI LINE) PRESERVATION
--------------------------------------------------------------------------------"""

BROKEN_56_C = "\n".join(
    "  " + line if line.strip() else line for line in FIXED_55_56.splitlines()
).replace(
    "§5.5 POSITIVE IDENTITY IN OUTPUT",
    "  §5.5 POSITIVE IDENTITY IN OUTPUT",
    1,
)

# stage-c has broken block with same content but 2-space indent on most lines
BROKEN_56_C_OLD = """  --------------------------------------------------------------------------------
  SHARED §6
  §5.5 POSITIVE IDENTITY IN OUTPUT
  Recurring characters and objects need positive identity descriptions in IMAGE PROMPT text —
  not generic negatives alone. Before any "no identity drift" negative, state the stable traits:
  apparent age band, face structure, hairstyle and colour, facial hair, glasses, build,
  clothing family, footwear, and identifying accessories for people; colour, material,
  shape, size, and distinctive features for recurring objects. Allow changes only when
  narration, elapsed time, or an explicitly established costume change supports them.
 — SOURCE TEXT (HINDI LINE) PRESERVATION
  --------------------------------------------------------------------------------"""

FIXED_56_C = """  §5.5 POSITIVE IDENTITY IN OUTPUT
  Recurring characters and objects need positive identity descriptions in IMAGE PROMPT text —
  not generic negatives alone. Before any "no identity drift" negative, state the stable traits:
  apparent age band, face structure, hairstyle and colour, facial hair, glasses, build,
  clothing family, footwear, and identifying accessories for people; colour, material,
  shape, size, and distinctive features for recurring objects. Allow changes only when
  narration, elapsed time, or an explicitly established costume change supports them.

  On repeat appearances, restate only the traits needed for recognition — do not paste full
  roster paragraphs every scene unless identity or costume changed.

  --------------------------------------------------------------------------------
  SHARED §6 — SOURCE TEXT (HINDI LINE) PRESERVATION
  --------------------------------------------------------------------------------"""


def patch_shared_56(text: str, indented: bool) -> str:
    if indented:
        if BROKEN_56_C_OLD in text:
            return text.replace(BROKEN_56_C_OLD, FIXED_56_C, 1)
    else:
        if BROKEN_56 in text:
            return text.replace(BROKEN_56, FIXED_55_56, 1)
    return text


def patch_stage_a(text: str) -> str:
    text = patch_shared_56(text, False)
    if "§1B — DEFINITE VISUAL REALIZATION" in text and "Reject before output" not in text:
        text = text.replace(
            "Stage C: render the selected choice consistently; if plot-critical uncertainty cannot be\nresolved from source, use a broader supported depiction rather than inventing a fact.",
            """Stage C: render the selected choice consistently; if plot-critical uncertainty cannot be
resolved from source, use a broader supported depiction rather than inventing a fact.

Reject before output: slash-separated visual attributes, "A or B" grooming/garment/vehicle
alternatives, or wide age spans when a single casting band is required.""",
            1,
        )
    return text


def patch_stage_b(text: str) -> str:
    text = text.replace(
        """Main subject:
{main visible subject or group with role/archetype and action/state, no public figure names outside Hindi line}""",
        """Main subject:
{one definite main subject or group with role/archetype and action/state — no unresolved alternatives, no public figure names outside Hindi line}""",
        1,
    )
    return text


def patch_stage_c(text: str) -> str:
    text = patch_shared_56(text, True)

    # Fix duplicate separators before §1B
    text = text.replace(
        "  --------------------------------------------------------------------------------\n\n  --------------------------------------------------------------------------------\n  SHARED §1B",
        "  --------------------------------------------------------------------------------\n  SHARED §1B",
        1,
    )
    text = text.replace(
        "  --------------------------------------------------------------------------------\n    SHARED §2",
        "  --------------------------------------------------------------------------------\n  SHARED §2",
        1,
    )

    text = text.replace(
        """  PUBLIC FIGURE
  DEFINITE REALIZATION — IMAGE PROMPT BODY
  Apply SHARED §1B in every IMAGE PROMPT. State one hair colour, one grooming choice,
  one garment type, one vehicle state, one object side, and one age band per subject.
  Never output unresolved "A or B" visual alternatives. Copy library anchors verbatim.


  PUBLIC FIGURE / NO-EXPLICIT-NAME — apply SHARED §4 absolutely.""",
        """  DEFINITE REALIZATION — IMAGE PROMPT BODY
  Apply SHARED §1B in every IMAGE PROMPT. State one hair colour, one grooming choice,
  one garment type, one vehicle state, one object side, and one age band per subject.
  Never output unresolved "A or B" visual alternatives. Copy library anchors verbatim.
  Reject and rewrite if the prompt contains slash-separated visual attributes or
  mutually exclusive "or" choices for appearance, vehicle state, or object geometry.

  PUBLIC FIGURE / NO-EXPLICIT-NAME — apply SHARED §4 absolutely.""",
        1,
    )

    text = text.replace(
        """  SILENT CONSISTENCY CHECK — before outputting each scene (do not print this checklist)
  Verify: definite visual choices; stable recurring identities and objects; plausible
  single-frame geometry; accurate figure count; one camera purpose; image/motion agreement;
  no unsupported facts; no irrelevant decorative clutter; no positive/negative contradictions;
  required structure; IMAGE PROMPT body exceeds 3000 characters excluding narration and motion.""",
        """  SILENT CONSISTENCY CHECK — before outputting each scene (do not print this checklist)
  Verify: one definite choice per visual attribute (no "A or B", no slash alternatives);
  stable recurring identities and objects with positive traits (SHARED §5.5); plausible
  single-frame geometry (one photo side; object not held and resting elsewhere); accurate
  figure count; one camera purpose; image/motion agreement; no unsupported facts; selective
  environment detail only; no positive/negative contradictions; required structure;
  IMAGE PROMPT body exceeds 3000 characters excluding narration and motion.""",
        1,
    )

    text = re.sub(
        r"\n    OUTPUT REQUIREMENT  OUTPUT REQUIREMENT\n  The DIGEN MOTION PROMPT must be one short sentence with optional second\n  clause joined by a semicolon\.\n  It must not become a cinematic paragraph\.\n  It must not introduce new action beyond the still IMAGE PROMPT\.\n  When uncertain, choose a static hold — less motion\.\n",
        "\n",
        text,
        count=1,
    )

    text = text.replace(
        """  TEXTURE & MATERIALS RULES
  Describe specific material surfaces relevant to the scene. Use concrete
  details such as:""",
        """  TEXTURE & MATERIALS RULES
  Describe materials relevant to this beat only — not an automatic inventory. Clean or
  maintained surfaces are valid. Use concrete details when shown, such as:""",
        1,
    )

    text = text.replace(
        """  QUALITY CONSISTENCY
  - maintain identical descriptive depth, material specificity, lighting
    detail, composition density, environmental realism, and hostile-character
    severity across all scenes in the batch;
  - detail must not decay as scene numbers increase.""",
        """  QUALITY CONSISTENCY
  - maintain consistent descriptive depth, lighting clarity, and continuity across the batch;
  - detail must not decay as scene numbers increase;
  - do not inflate later scenes with decorative clutter or repeated full character blocks.""",
        1,
    )

    text = text.replace(
        """  - do not force every narrated detail into the image; do not duplicate objects to solve this.""",
        """  - do not force every narrated detail into the image; do not duplicate objects to solve this;
  - for documents/photos, show ONE physically plausible side or angle unless reflection is supported.""",
        1,
    )

    # Remove duplicate HARD LENGTH block if present twice - keep first extended version
    return text


PATCHERS = {
    "stage-a-story-config.md": patch_stage_a,
    "stage-b-scene-breakdown.md": patch_stage_b,
    "stage-c-image-motion.md": patch_stage_c,
}

CHECKS = {
    "stage-a-story-config.md": [
        "PART 3 — INPUT SLOTS",
        "SHARED §1B — DEFINITE VISUAL REALIZATION",
        "SHARED §6 — SOURCE TEXT",
        "§5.5 POSITIVE IDENTITY IN OUTPUT",
        "{Paste the full Hindi / Hinglish / English story here.}",
    ],
    "stage-b-scene-breakdown.md": [
        "PART 3 — INPUT SLOTS",
        "PART 1B — DEFINITE STAGING COMMITMENT",
        "PART 22B — SILENT STAGING",
        "On-screen location:",
        "--- Scene {X} / ~{TOTAL_ESTIMATED_SCENES} ---",
    ],
    "stage-c-image-motion.md": [
        "PART 3 — INPUT SLOTS",
        "SCENE_RANGE:",
        "SHARED §6 — SOURCE TEXT",
        "3000 characters",
        "SCENE-DRIVEN CAMERA FRAMING",
        "SILENT CONSISTENCY CHECK",
        "IMAGE PROMPT",
        "DIGEN MOTION PROMPT",
        " ||",
        "NEXT_RANGE:",
    ],
}

FORBIDDEN = [
    "OUTPUT REQUIREMENT  OUTPUT REQUIREMENT",
    "SHARED §6\n§5.5",
    "MANDATORY TWO-CLAUSE",
]


def validate(name: str, text: str) -> list[str]:
    errs = []
    for t in CHECKS[name]:
        if t not in text:
            errs.append(f"missing {t!r}")
    for t in FORBIDDEN:
        if t in text:
            errs.append(f"forbidden {t!r}")
    if name == "stage-c-image-motion.md":
        if " — SOURCE TEXT (HINDI LINE) PRESERVATION" in text and text.count(
            "SHARED §6 — SOURCE TEXT"
        ) != 1:
            errs.append("§6 header count != 1")
    return errs


def backup() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for label, root in [("automation", AUTOMATION), ("cms-module", CMS)]:
        dest = BACKUP / label
        dest.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            shutil.copy2(root / f, dest / f)


def main() -> int:
    backup()
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
        for root in (AUTOMATION, CMS, EXPORT):
            root.mkdir(parents=True, exist_ok=True)
            (root / f).write_text(patched, encoding="utf-8")
        print(f"OK {f}")
    print("Export:", EXPORT)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
