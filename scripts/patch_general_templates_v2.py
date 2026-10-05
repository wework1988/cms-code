#!/usr/bin/env python3
"""Targeted patch v2 — menace, negatives, clutter, staging, motion."""

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

NEW_SHARED_2 = """SHARED §2 — HOSTILE / SUSPECT / CRIMINAL SUBJECT CODING (CONDITIONAL)
--------------------------------------------------------------------------------

SCOPE: Apply ONLY when the STORY CONFIG BLOCK records "Hostile actors present: yes"
AND this scene's main or supporting subject is a confirmed hostile actor, suspect,
criminal operative, or threat-network member named in the story. Otherwise skip §2
entirely for this scene.

PRINCIPLE — behaviour over appearance coding:
Show story-supported threat through depicted ACTION, concealment, spatial
relationship, attention direction, expression, or tense gesture — not through
automatic sinister faces, dirty half-shadow, rough-grooming mandates, or bans on
ordinary appearance, clean-shaven faces, trimmed beards, soft daylight, or balanced
readable lighting.

A suspect or criminal courier MAY look ordinary — like any working-class person in
that region. Do NOT make role or morality determine facial anatomy, grooming,
clothing cleanliness, class markers, skin tone, or lighting quality.

WHEN §2 APPLIES, describe:
- the story-supported frozen beat (handoff, surveillance, flight, concealment, interception);
- gaze direction and body orientation toward exits, contacts, or story objects;
- tension appropriate to narration (guarded, evasive, startled) without caricature;
- clothing and props supported by the story with stable continuity across scenes;
- motivated lighting for time and place that keeps faces READABLE.

DO NOT:
- require heavy beard, skullcap, pakol, turban, or religious dress unless the story
  explicitly identifies that person and that appearance;
- ban clean-shaven faces, neatly trimmed beards, or "ordinary man / neutral civilian /
  working-class everyman / harmless appearance" in positives or negatives;
- apply §2 posture or lighting to bystanders, officers, or civilians;
- paste hostile-only NEGATIVE exclusions into scenes without hostile subjects.

§2.1 CONTINUITY
Story-established clothing, footwear, hair, bag material, and props remain stable
unless narration supports a change. Named recurring characters (including officers)
keep the same identifying details scene to scene.

§2.2 WHEN HOSTILE ACTORS ABSENT
When "Hostile actors present: no", all HOSTILE ACTOR VISUAL PROFILE fields in Stage A
are N/A. Stages B and C do not apply §2."""

NEW_SHARED_2_C = "\n".join("  " + line if line.strip() else line for line in NEW_SHARED_2.splitlines())

NEW_SHARED_11 = """SHARED §11 — NEGATIVE PROMPT SELECTION (Stage C)
--------------------------------------------------------------------------------

Stage C builds a compact NEGATIVE section per scene — approximately 6–12 items,
semicolon-separated. Do NOT copy the entire shared library, character-library
metadata blocks, or all story-level exclusions into every scene.

BASE CORE (include 5–7 of these on most scenes when relevant):
photorealistic; 3D render; CGI; text overlay; watermark; logo; readable labels;
readable document text; split-screen; collage; empty stage-like background.

ADD ONLY when this scene could plausibly err:
- weapons / gore / blood — only if narration touches violence or weapons;
- propaganda / extremist logos / readable religious text — only on propaganda or
  confirmed extremist-beat scenes;
- mobile UI / readable messages — only when phones or screens are focal;
- identity firewall — only when Library lock is present: merged identity; wrong
  locked character; identity drift; borrowed facial features;
- story-specific negatives from STAGE CONFIG — only items relevant to THIS scene.

NEVER bulk-paste anti-soft hostile lists (ordinary man; neutral civilian;
harmless appearance; balanced studio lighting; even soft daylight; clean-shaven;
skullcap; pakol; turban; long religious beard) into scenes without hostile subjects
or without a story-supported identity reason.

Before output, scan positive description against negatives and remove contradictions:
- glossy photographic paper or metal reflection is allowed; ban photorealistic and CGI,
  not all gloss;
- if background simplification is desired, ban illegible focal faces — do not ban all
  blur or depth of field while keeping the main subject sharp;
- ban photorealism and CGI rather than blanket-banning global illumination when natural
  daylight is the positive goal.

Stage A may list story-specific negatives; Stage C adds only those relevant to THIS scene."""

NEW_SHARED_11_C = "\n".join("  " + line if line.strip() else line for line in NEW_SHARED_11.splitlines())

NEW_SHARED_36 = """§3.6 PAKISTAN-BASED ISLAMIST MILITANT CONTEXT (CONDITIONAL)
Apply only when the story explicitly names the actor as a Pakistan-based Islamist
militant, terror commander, extremist recruiter, LeT/JeM-linked figure, Taliban-style
militant, or jihadist handler — not from religion or dress alone.

When this profile applies, use story-supported behaviour and period-accurate regional
clothing. Faces remain readable. Do NOT require heavy beard, skullcap, pakol, or turban
unless the story establishes that appearance. Do NOT ban clean-shaven or trimmed grooming
unless disguise is narratively excluded.

Avoid: readable religious text; extremist logos; propaganda glorification; graphic gore;
making ordinary Muslim civilians look threatening (SHARED §2.6)."""

NEW_SHARED_36_C = "\n".join("  " + line if line.strip() else line for line in NEW_SHARED_36.splitlines())

NEW_STAGE_B_PART3 = """================================================================================
PART 3 — HOSTILE / SUSPECT SUBJECT CODING (CONDITIONAL)
================================================================================

Apply only when STORY CONFIG BLOCK records hostile actors present AND this scene's
subject is a confirmed hostile actor, suspect, or criminal operative named in the story.

When §2 applies:
- identify role from narration (courier, handler, operative) in Main subject;
- describe the visible beat, action, and spatial relationship — not automatic sinister
  appearance or compulsory half-shadow;
- surrounding environment supports the story location and time of day with readable light.

A suspect may look ordinary. Do NOT require threat language in context labels beyond what
the narration supports.

Civilian separation rule:
Do NOT apply hostile coding because of religion, ethnicity, beard, skullcap, shalwar
kameez, hijab, mosque background, or regional dress alone."""

NEW_STAGE_B_STAGING = """
================================================================================
PART 22A — SILENT STAGING AND CONTINUITY CHECK (before locking each scene)
================================================================================

Using existing fields only — verify silently, then reflect fixes in Main subject,
Supporting visual elements, Surrounding environment, or Breakdown note:

A. People count — if you state a total, it must match every person described; prefer
   omitting explicit totals unless narration requires them.
B. Recurring identity — same footwear, bag, hair, clothing family, and props as prior
   scenes unless narration supports a change.
C. Named characters — if Meera (or any named officer/character) is the subject, identify
   her consistently; do not replace with a generic woman/man when the story names her.
D. Object geometry — show one plausible side of a photo/document; no impossible front-and-
   back at once; recorder/phone/key stays in the hand or surface the beat requires.
E. Critical text — do not substitute nonsense loops for story-critical times or labels;
   use On-screen name/location overlay fields when editor text is needed; otherwise keep
   text unreadable in the image and note the limitation in Breakdown note.
F. Lighting plausibility — tiny indicator lights do not main-light a face in daylight;
   state the dominant source and plausible fill.
G. Narrative fidelity — do not invent clue links (e.g. red bag linked to photograph)
   unless the source establishes them; distinguish essential clues from decorative detail.
"""

NEW_STAGE_C_HOSTILE_BLOCK = """  HOSTILE / SUSPECT SUBJECTS (when §2 applies)
  Describe the story-supported action, concealment, spatial relationship, and readable
  expression. Suspects may look ordinary. Do NOT front-load a menace template, mandatory
  half-shadow, or bulk anti-soft negatives. Apply SHARED §2 only for confirmed subjects."""

NEW_STAGE_C_NEG_RULES = """  NEGATIVE PROMPT RULES
  End every IMAGE PROMPT with NEGATIVE: followed by approximately 6–12 semicolon-separated
  items selected per SHARED §11 — not the full library dump.

  When Library lock is present, you may add 2–4 identity-firewall items (merged identity;
  wrong locked character; identity drift) — never paste entire character-library NEGATIVE
  FIREWALL blocks.

  Scan positives against negatives before output and remove contradictions."""

NEW_STAGE_C_EXPANSION = """  EXPANSION RULE — depth through clarity, not clutter
  Prioritize essential subject, action, focal relationship, spatial layout, motivated
  lighting, and continuity. Expand architecture, materials, and atmosphere when they
  support the beat — not as decorative inventories.

  Use wear, dust, rust, stains, discarded cups, or scuffed surfaces ONLY when appropriate
  to this specific setting and action. A clean table, simple wall, or uncluttered foreground
  is valid. Do not make every Indian location dirty or deteriorated. Do not invent plot-
  bearing objects to pad length.

  Meet the ≥3000-character rule with useful spatial, lighting, character, and continuity
  detail — not repeated adjectives, not padding NEGATIVE lists, not unrelated background props."""

NEW_STAGE_C_COMPOSITION = """  COMPOSITION RULES — every scene must contain
  1. clear layered depth and subject hierarchy;
  2. Foreground / Midground / Background labels describe depth — each plane may be simple
     or empty if the beat supports it; do not force props into every plane;
  3. a world that feels believable for this exact moment — not a prop checklist;
  4. realistic material behaviour where shown;
  5. a frozen film frame, not a flat promotional poster;
  6. no empty stage-like void behind the subject unless narration supports isolation;
  7. one coherent frozen moment with physically plausible geometry and lighting."""

NEW_STAGE_C_STAGING = """
  SILENT STAGING AND CONTINUITY CHECK — before outputting each scene
  Re-read the locked breakdown and verify: people count matches description; recurring
  clothing/footwear/bag stable; named characters identified consistently; object positions
  plausible (one photo side; recorder in correct hand/surface); no invented clue links;
  lighting physically plausible; motion matches this IMAGE PROMPT's viewpoint, poses,
  and object locations exactly."""

NEW_MOTION_CORE = """  CORE PRINCIPLE — CAMERA MOVES, SUBJECTS STAY STILL
  The motion prompt must describe ONLY slow, controlled camera movement that matches the
  completed IMAGE PROMPT. People, faces, hands, objects, and backgrounds remain frozen.

  MOTION–IMAGE LOCK:
  - same viewpoint family as the IMAGE PROMPT (eye-level, over-shoulder, wide, etc.);
  - same visible subjects and object locations — never relocate props (recorder stays in
    the hand shown, not on a shelf);
  - one primary visual target — do not imply simultaneous close-up, over-shoulder, and
    distant reveal;
  - no unsupported reveal beyond what the still frame already shows.

  Choose exactly ONE camera behaviour:
  A) LOCKED-OFF HOLD — camera holds steady on the main subject or anchor; no drift wording.
  B) ONE RESTRAINED MOVE — one clearly described slow push, gentle track, or inward settle
     toward the primary target — only when it helps read the beat; static hold is valid.

  Do NOT default every scene to push-in. Do NOT rotate moves mechanically. Do NOT use
  "minimal drift only" — pick hold OR one move, not both."""

NEW_MOTION_PATTERNS = """  Pattern A — LOCKED-OFF HOLD (valid default):
    "[View matching IMAGE PROMPT] holds steady on [primary subject / anchor object]."

  Pattern B — ONE RESTRAINED MOVE (when wider context matters):
    "[Starting view matching IMAGE PROMPT] slowly [pushes closer / tracks gently] toward
    [single primary target], ending on the same frozen pose and object positions."

  Pattern C — DOORWAY / INTERIOR (when IMAGE PROMPT uses threshold framing):
    "From [same doorway/threshold as IMAGE PROMPT], camera slowly pushes inward and holds
    on [subject / group / object] in stillness."""

NEW_MOTION_AUDIT = """  MOTION FINAL AUDIT — BEFORE OUTPUT
  Compare DIGEN MOTION PROMPT to the IMAGE PROMPT just written: same viewpoint, same
  subjects, same object locations, same action state, no unsupported reveal, no subject
  animation, no compulsory aerial/descent, no hold-plus-drift wording, no simultaneous multi-target
  framing. When uncertain, use locked-off hold."""

NEW_SHARED_83 = """§8.3 SCENE LABEL CLARITY
Use concrete role + action + setting from the narration. Do not soften into vague labels,
but do not inject menace words (shadow, hardened, hostile) unless the story supports them.

  Weak (forbidden)              →   Clear (preferred)
  Young Man Watches Video       →   Courier Checks Phone Message
  Man Uses Phone                →   Suspect Reads Platform Alert
  Important Scene               →   Railway Locker Key Exchange
  Gentle Man In Room            →   Contact Waits At Tea Stall"""

NEW_SHARED_74 = """§7.4 ABSTRACT LINES INVOLVING DANGER / RADICALISATION / TERRORISM
Ground them through story-supported action and setting: tense faces, suspicious devices,
marked maps, closed shutters, coded notes without readable text, officers reviewing
evidence, guarded body language. Do NOT default to dim rooms or sinister faces when the
narration supports daylight or ordinary surroundings."""

NEW_SHARED_128 = """§12.8 INTERACTION WITH SHARED §2 (LIBRARY vs SUSPECT CODING)
If a library-locked anchor conflicts with SHARED §2 behaviour-based suspect coding or
readable-lighting rules, the LOCKED CHARACTER ANCHOR is copied VERBATIM — prompts cannot
override verbatim library bodies. Apply scene action, lighting, and staging around the
anchor. Note irreconcilable library menace wording in Breakdown note (Stage B) or
Lighting clause (Stage C) for human review — do not silently drop the anchor."""

NEW_SHARED_128_A = NEW_SHARED_128  # same text for stage-a


def replace_section(text: str, start: str, end: str, replacement: str) -> str:
    i = text.find(start)
    if i < 0:
        raise ValueError(f"start not found: {start[:70]!r}")
    j = text.find(end, i + len(start))
    if j < 0:
        raise ValueError(f"end not found after start: {end[:70]!r}")
    return text[:i] + replacement + text[j:]


def patch_shared_sections(text: str, indented: bool = False) -> str:
    s2 = NEW_SHARED_2_C if indented else NEW_SHARED_2
    s11 = NEW_SHARED_11_C if indented else NEW_SHARED_11
    s36 = NEW_SHARED_36_C if indented else NEW_SHARED_36
    s128 = "  " + NEW_SHARED_128 if indented else NEW_SHARED_128

    s2_starts = [
        "SHARED §2 — HOSTILE ACTOR VISUAL MENACE (CONDITIONAL — ONLY WHEN PRESENT IN STORY)",
        "SHARED §2 — HOSTILE / SUSPECT / CRIMINAL SUBJECT CODING (CONDITIONAL)",
    ]
    if not any(s in text for s in s2_starts):
        raise ValueError("SHARED §2 header not found")
    if "SHARED §2 — HOSTILE ACTOR VISUAL MENACE" in text:
        text = replace_section(
            text,
            "SHARED §2 — HOSTILE ACTOR VISUAL MENACE (CONDITIONAL — ONLY WHEN PRESENT IN STORY)",
            "SHARED §3 — REGION / ORIGIN / IDEOLOGY VISUAL MAPPING",
            s2 + "\n\n--------------------------------------------------------------------------------\n",
        )
    if "SHARED §11 — UNIVERSAL NEGATIVES" in text:
        text = replace_section(
            text,
            "SHARED §11 — UNIVERSAL NEGATIVES (sensitive content)",
            "SHARED §12 — LOCKED CHARACTER LIBRARY",
            s11 + "\n\n--------------------------------------------------------------------------------\n",
        )
    elif "SHARED §11 — NEGATIVE PROMPT SELECTION" not in text:
        raise ValueError("SHARED §11 header not found")
    if "§3.6 PAKISTAN-BASED ISLAMIST MILITANT VISUAL PROFILE (MANDATORY MINIMUMS)" in text:
        text = replace_section(
            text,
            "§3.6 PAKISTAN-BASED ISLAMIST MILITANT VISUAL PROFILE (MANDATORY MINIMUMS)",
            "§3.7 ARCHETYPE QUICK REFERENCE",
            s36 + "\n\n",
        )
    text = text.replace(
        """§8.3 HOSTILE-SCENE STRENGTHENING
If a scene includes a hostile actor, do NOT use soft labels. Strengthen the
label with grounded threat language. Examples:

  Soft (forbidden)              →   Stronger (preferred)
  Young Man Watches Video       →   Hostile Recruiter Watches Screen
  Religious Speaker Talks       →   Radical Handler Controls Room
  Group Listening Quietly       →   Suspicious Group Receives Message
  Man Uses Phone                →   Threat Network Studies Phone
  Calm Speaker Addresses Room   →   Hostile Propagandist Shapes Narrative
  Gentle Man In Room            →   Criminal Handler Waits In Shadow""",
        NEW_SHARED_83,
    )
    text = text.replace(
        """§7.4 ABSTRACT LINES INVOLVING DANGER / RADICALISATION / TERRORISM
Ground them through: tense faces, suspicious devices, dim rooms, hidden
phones, marked maps, closed shutters, coded notes without readable text,
officers reviewing evidence, hostile actors watching screens with guarded
body language. Do NOT create peaceful spiritual symbolism or soft emotional
portraits of hostile actors.""",
        NEW_SHARED_74,
    )
    if "§12.8 INTERACTION WITH SHARED §2 (HOSTILE ACTOR)" in text:
        text = replace_section(
            text,
            "§12.8 INTERACTION WITH SHARED §2 (HOSTILE ACTOR)",
            "§12.9",
            s128 + "\n\n  " if indented else s128 + "\n\n",
        )
    elif "§12.8 INTERACTION WITH SHARED §2 (LIBRARY vs SUSPECT CODING)" not in text:
        pass
    # stage-a §12.8 may differ
    if not indented and "§12.8 INTERACTION WITH SHARED §2 (HOSTILE ACTOR)" in text:
        text = replace_section(
            text,
            "§12.8 INTERACTION WITH SHARED §2 (HOSTILE ACTOR)",
            "§12.9",
            NEW_SHARED_128 + "\n\n",
        )
    return text


def patch_stage_a(text: str) -> str:
    text = patch_shared_sections(text, indented=False)
    text = text.replace(
        """F. HOSTILE ACTOR DETECTION
Per SHARED §2 and §3.6/§3.7. If hostile actors exist, record:""",
        """F. HOSTILE ACTOR DETECTION (conditional — if absent, all fields N/A)
Per SHARED §2 when present. If hostile actors exist, record behaviour-based profile:""",
    )
    text = text.replace(
        """[If hostile actors appear, 3 to 5 concrete examples showing threat physically without gore, propaganda, or glorification — see SHARED §2. Otherwise N/A.]""",
        """[If hostile actors appear, 3 to 5 examples of story-supported action/concealment beats — not appearance menace. Otherwise N/A.]""",
    )
    text = text.replace(
        """[3 to 5 concrete examples of how origin + region + role + ideology should affect appearance, applying militant styling only to identified hostile actors and keeping civilians neutral — see SHARED §3.]""",
        """[3 to 5 examples of how origin + region + role affect ordinary appearance coding; civilians stay neutral; suspects may look ordinary — see SHARED §3.]""",
    )
    text = text.replace(
        """- The lock does NOT override SHARED §2 (hostile actor mandate) if the
  story identifies the character as hostile. SHARED §2 still applies on
  top, and the locked body is only used if it is consistent with §2;
  otherwise flag the conflict (this should be rare — the library is
  expected to be self-consistent with each character's role).""",
        """- Verbatim library anchors are never overridden by SHARED §2. Copy the anchor
  verbatim; apply scene action and readable lighting around it. If the anchor
  contains menace or lighting wording that conflicts with §2 behaviour-based
  rules, note the conflict for human review — do not drop or rewrite the anchor.""",
    )
    return text


def patch_stage_b(text: str) -> str:
    text = replace_section(
        text,
        "PART 3 — HOSTILE ACTOR VISUAL MENACE",
        "PART 4 — CHARACTER CONSISTENCY AND LIBRARY LOCKS",
        NEW_STAGE_B_PART3 + "\n\n",
    )
    if "PART 22A — SILENT STAGING" not in text:
        text = text.replace(
            "================================================================================\nPART 23 — OUTPUT FORMAT",
            NEW_STAGE_B_STAGING
            + "\n================================================================================\nPART 23 — OUTPUT FORMAT",
        )
    text = text.replace(
        """Breakdown note:
{one short line explaining split/merge logic and why this is one visual beat}""",
        """Breakdown note:
{one short line: split/merge logic; staging checks passed (people count, object side, identity continuity, no invented links)}""",
    )
    return text


def patch_stage_c(text: str) -> str:
    text = patch_shared_sections(text, indented=True)
    text = replace_section(
        text,
        "  HOSTILE ACTOR — FRONT-LOAD MANDATE",
        "  SCENE INTERPRETATION RULE",
        NEW_STAGE_C_HOSTILE_BLOCK + "\n\n",
    )
    text = text.replace(
        """  - strengthens soft hostile labels (SHARED §8.3);""",
        """  - uses concrete labels from breakdown (SHARED §8.3);""",
    )
    # Remove hostile foreground opener block
    if "HOSTILE-PRESENT FOREGROUND OPENER RULE" in text:
        text = replace_section(
            text,
            "  HOSTILE-PRESENT FOREGROUND OPENER RULE",
            "  STAGE C CHARACTER LOCK FINAL AUDIT",
            "",
        )
    # Fix co-apply rule referencing hostile template
    text = text.replace(
        """  Both rules co-apply: if the scene has BOTH a hostile actor and a
  LIBRARY-LOCKED character, the HOSTILE-PRESENT FOREGROUND OPENER RULE
  runs first (hostile staging template at the very start of Foreground),
  then the locked anchor for the non-hostile character is dropped into
  its appropriate slot per the placement rules above. If the locked
  character is itself the hostile actor, follow SHARED §12.8.""",
        """  If both a suspect/hostile subject and a LIBRARY-LOCKED character appear,
  copy each locked anchor verbatim per SHARED §12.6; describe story-supported action
  around anchors per SHARED §2 when applicable. Library anchors are never overridden.""",
    )
    text = replace_section(
        text,
        "  NEGATIVE PROMPT RULES",
        "  HOSTILE ACTOR PROMPTING EXAMPLES (in-line guidance, not output)",
        NEW_STAGE_C_NEG_RULES + "\n\n",
    )
    if "HOSTILE ACTOR PROMPTING EXAMPLES" in text:
        text = replace_section(
            text,
            "  HOSTILE ACTOR PROMPTING EXAMPLES (in-line guidance, not output)",
            "  DIGEN MOTION PROMPT RULES",
            "",
        )
    text = replace_section(
        text,
        "  EXPANSION RULE — fully expand",
        "  COMPOSITION RULES — every scene must contain",
        NEW_STAGE_C_EXPANSION + "\n\n",
    )
    text = replace_section(
        text,
        "  COMPOSITION RULES — every scene must contain",
        "  SHOT-TYPE GUIDANCE",
        NEW_STAGE_C_COMPOSITION + "\n\n",
    )
    # Remove old composition tail if duplicate lines remain - find SHOT-TYPE after new block
    text = text.replace(
        """  Always reflect: region-specific architecture/street details; class-specific
  objects and wear; era-accurate vehicles, furniture, uniforms, communication
  devices, public signage style; correct weather/light behaviour; visible use,
  aging, dust, moisture, wear, and maintenance level appropriate to the place;""",
        """  Always reflect: region-specific architecture/street details; class-specific
  objects and wear; era-accurate vehicles, furniture, uniforms, communication
  devices, public signage style; correct weather/light behaviour; wear and aging
  only when appropriate to this setting — not automatic dirt on every surface;""",
    )
    if "SILENT STAGING AND CONTINUITY CHECK — before outputting" not in text:
        text = text.replace(
            "  DIGEN MOTION PROMPT RULES",
            NEW_STAGE_C_STAGING + "\n  DIGEN MOTION PROMPT RULES",
        )
    # Motion section fixes
    text = text.replace(
        """  CORE PRINCIPLE — CAMERA MOVES, SUBJECTS STAY STILL
  The motion prompt must describe ONLY slow, controlled camera movement.
  People, faces, hands, crowds, vehicles, objects, smoke, fire, doors, papers,
  clothes, and background elements must remain still or near-still.""",
        NEW_MOTION_CORE,
    )
    text = text.replace(
        """  The safest motion style is:

  aerial / elevated / doorway / raised view
  → slowly descending / slowly lowering
  → gently pushing forward
  → settling closer on the main subject or key object

  The motion prompt should feel like a slow 5-second image-to-video camera move,
  not an action scene.

  Why this matters: Digen and similar image-to-video models deform faces,""",
        """  Why this matters: Digen and similar image-to-video models deform faces,""",
    )
    if "MOTION STRUCTURE — static hold or one restrained camera move" in text:
        text = replace_section(
            text,
            "  MOTION STRUCTURE — static hold or one restrained camera move",
            "  Scene-specific guidance:",
            """  MOTION STRUCTURE — locked-off hold or one restrained move
  Every DIGEN MOTION PROMPT must match the completed IMAGE PROMPT (see MOTION–IMAGE LOCK).
  Choose ONE behaviour — not hold plus drift:

"""
            + NEW_MOTION_PATTERNS
            + """

  Rules:
  - Match starting viewpoint to the IMAGE PROMPT — no aerial/descent unless IMAGE PROMPT is wide exterior;
  - ONE continuous camera move maximum when using Pattern B or C; Pattern A has no move;
  - Subjects and object locations stay frozen; never relocate props;
  - Night scenes remain readable.

  Forbidden as default:
  - Mandatory aerial / high aerial / night aerial opening;
  - Compulsory slowly descending as clause 1 for every scene;
  - Two-clause aerial descent + push-in template;
  - "minimal drift", hold-plus-drift wording, or simultaneous multi-target framing.

  Legacy conflict: preserve library anchors verbatim; apply readable scene lighting in Lighting: if needed.

  Preferred motion verbs:
  holds steady on • holds on • slowly pushes closer • gently moves closer • slowly tracks toward • softly settles on.

  Canonical examples:
  - "Medium character view holds steady on Meera's restrained expression and the recorder in her right hand."
  - "Over-shoulder view matching the locker scene slowly pushes closer toward the open locker and recorder in her hand."
  - "Wide establishing view of the morning street holds steady on Meera walking among ordinary commuters."

  """,
        )
    text = text.replace("minimal drift", "steady hold")
    text = replace_section(
        text,
        "  MOTION FINAL AUDIT — BEFORE OUTPUT",
        "  OUTPUT REQUIREMENT",
        NEW_MOTION_AUDIT + "\n\n  OUTPUT REQUIREMENT",
    )
    text = text.replace(
        """  - hostile actor severity when relevant;""",
        """  - story-supported suspect action when §2 applies;""",
    )
    text = text.replace(
        """  - removing hostile actor severity from later scenes.""",
        """  - dropping story-specific detail from later scenes.""",
    )
    return text


PATCHERS = {
    "stage-a-story-config.md": patch_stage_a,
    "stage-b-scene-breakdown.md": patch_stage_b,
    "stage-c-image-motion.md": patch_stage_c,
}

REQUIRED = {
    "stage-a-story-config.md": [
        "PART 3 — INPUT SLOTS",
        "{Paste the full Hindi / Hinglish / English story here.}",
        "STORY CONFIG BLOCK",
        "Hostile actors present: [yes / no]",
        "behaviour over appearance coding",
    ],
    "stage-b-scene-breakdown.md": [
        "PART 3 — INPUT SLOTS",
        "--- Scene {X} / ~{TOTAL_ESTIMATED_SCENES} ---",
        "PART 22A — SILENT STAGING",
        "Library lock:",
    ],
    "stage-c-image-motion.md": [
        "PART 3 — INPUT SLOTS",
        "SCENE_RANGE:",
        "IMAGE PROMPT",
        "DIGEN MOTION PROMPT",
        " ||",
        "NEXT_RANGE:",
        "3000 characters",
        "MOTION–IMAGE LOCK",
        "approximately 6–12",
    ],
}

FORBIDDEN = [
    "MANDATORY TWO-CLAUSE STRUCTURE — descent + push-in",
    "HOSTILE ACTOR — FRONT-LOAD MANDATE",
    "§2.10 HOSTILE STAGING TEMPLATE",
    "§2.11 softening",
    "ordinary man; regular passer-by; neutral civilian look",
    "When hostile actors are present, ALWAYS include these strong anti-soft",
    "minimum of 7 concrete physical objects",
    "minimal drift only",
    "HOSTILE-PRESENT FOREGROUND OPENER",
]


def validate(name: str, text: str) -> list[str]:
    errs = []
    for t in REQUIRED[name]:
        if t not in text:
            errs.append(f"missing: {t!r}")
    for t in FORBIDDEN:
        if t in text:
            errs.append(f"forbidden still present: {t!r}")
    if name == "stage-c-image-motion.md" and text.count("STAGE C FORMATTING RULES") != 1:
        errs.append("STAGE C FORMATTING RULES count != 1")
    return errs


def backup() -> None:
    for label, root in [("automation", AUTOMATION), ("cms-module", CMS)]:
        dest = BACKUP / label
        dest.mkdir(parents=True, exist_ok=True)
        for f in FILES:
            shutil.copy2(root / f, dest / f)


def main() -> int:
    import os

    if os.environ.get("SKIP_BACKUP") != "1":
        backup()
        print("Backup:", BACKUP)
    ok = True
    only = os.environ.get("ONLY_FILE")
    todo = [only] if only else FILES
    for f in todo:
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
