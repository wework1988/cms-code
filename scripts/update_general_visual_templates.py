#!/usr/bin/env python3
"""Update General story Stage A/B/C prompt templates — visual pilot patch."""

from __future__ import annotations

import re
import sys
from pathlib import Path

AUTOMATION = Path(
    "/Users/averma/project/research-story-17thmay-automation/general-story/bifuracted-template"
)
CMS = Path(
    "/Applications/MAMP/htdocs/myresearch2/web/modules/custom/story_pipeline/prompts/general-story/bifuracted-template"
)
EXPORT = Path(
    "/Applications/MAMP/htdocs/myresearch2/docs/general-visual-template-export-2026-09-21"
)

FILES = [
    "stage-a-story-config.md",
    "stage-b-scene-breakdown.md",
    "stage-c-image-motion.md",
]

# --- Stage A / C shared blocks (no leading indent) ---

OLD_SHARED_1_A = """--------------------------------------------------------------------------------
SHARED §1 — GLOBAL STYLE LOCK
--------------------------------------------------------------------------------

Use this visual language implicitly when describing visual defaults:

2D digital animated illustration; cinematic hand-drawn 2D matte painting; clean
hand-drawn line art; flat cel shading; minimal texture; simplified forms with
strong readability; documentary realism; restrained stylisation; region-accurate
facial features; historically grounded environments; muted documentary color
palette unless the scene clearly requires warmer or brighter tonal treatment;
no photorealism; no 3D rendering; no ray tracing; no global illumination;
no depth of field blur; no cinematic lens artifacts; no glossy CGI finish;
no hyper-detailed skin texture; no HDR realism.

Always implicitly avoid: photorealistic; ultra realistic; 3D render; CGI;
ray tracing; global illumination; lens flare; bokeh; depth of field blur;
bloom; volumetric fantasy light; hyper-detailed pores; photo textures;
futuristic design unless era supports it; neon colors unless era and setting
clearly support them; watermark; logo; text overlay; poster layout;
empty stage-like backgrounds."""

NEW_SHARED_1_A = """--------------------------------------------------------------------------------
SHARED §1 — GLOBAL STYLE LOCK
--------------------------------------------------------------------------------

Use this visual language implicitly when describing visual defaults and in every
IMAGE PROMPT:

Semi-realistic hand-drawn 2D graphic novel illustration; clean readable contours;
controlled cel shading with one or two value steps; natural skin tones; expressive
but grounded faces; simplified forms with strong subject hierarchy; historically
grounded environments with concrete local detail; documentary realism with
restrained stylisation; region-accurate facial features; setting-specific colour
palettes and motivated lighting derived from this story's time of day, geography,
and mood — not a uniform dark or crime-template look.

Daylight and interior day scenes: natural readable illumination, visible facial
features, believable local colours. Night scenes: readable faces and key subjects
with motivated practical light (street lamps, windows, screens, bulbs) — not crushed
black silhouettes unless the narration explicitly calls for near-darkness.

Always implicitly avoid: photorealistic; ultra realistic; 3D render; CGI;
ray tracing; global illumination; lens flare; bokeh; depth of field blur;
bloom; volumetric fantasy light; hyper-detailed pores; photo textures;
uniformly dark or sinister grading on ordinary non-threat scenes; repetitive
desk-monitor-silhouette-evidence-board templates when narration supports a
different anchor; futuristic design unless era supports it; neon colors unless era
and setting clearly support them; watermark; logo; text overlay; poster layout;
empty stage-like backgrounds."""

NEW_SHARED_1A_A = """
--------------------------------------------------------------------------------
SHARED §1A — FACTUAL CONTINUITY LOCKS vs ADAPTABLE VISUAL DEFAULTS
--------------------------------------------------------------------------------

FACTUAL LOCKS (must stay consistent across all stages):
- era, geography, architecture, infrastructure, vehicles, technology;
- recurring character identity, library locks, origin, role category;
- hostile-actor presence and severity ONLY when identified in the source story;
- public-figure handling; sensitive-content exclusions; story-specific negatives.

ADAPTABLE VISUAL DEFAULTS (choose per scene from narration + config, not a global dark style):
- time of day and weather; lighting source and direction; palette warmth or coolness;
- camera scale and framing; dominant anchor (face, crowd, landscape, object, building);
- atmosphere family for that beat.

Stage A must ground abstract visual guidance in THIS story's actual locations,
period, and cast — not generic investigation or crime defaults. When hostile actors
are absent, mark HOSTILE ACTOR VISUAL PROFILE fields N/A and do NOT propagate
threat lighting to ordinary civilians or neutral scenes."""

OLD_SHARED_2_HEADER = """--------------------------------------------------------------------------------
SHARED §2 — HOSTILE ACTOR VISUAL MENACE (MANDATORY)
--------------------------------------------------------------------------------

A "hostile actor" means:"""

NEW_SHARED_2_HEADER = """--------------------------------------------------------------------------------
SHARED §2 — HOSTILE ACTOR VISUAL MENACE (CONDITIONAL — ONLY WHEN PRESENT IN STORY)
--------------------------------------------------------------------------------

SCOPE: Apply §2 ONLY when the STORY CONFIG BLOCK records "Hostile actors present: yes".
For all other scenes and characters, use SHARED §1 natural motivated lighting and
neutral civilian coding. §2 rules must NEVER leak into ordinary domestic, political,
journalistic, or celebratory scenes unless a hostile actor is explicitly the subject.

A "hostile actor" means:"""

OLD_SHARED_27 = """§2.7 LIGHTING RULE FOR HOSTILE ACTORS
Use directional menace lighting:
- harder side light or back-rim light cutting one side of the face dark;
- weak phone glow under the chin or across one eye, leaving the rest in
  dirty shadow;
- single low overhead bulb creating harsh downward shadow under brows and
  cheekbones;
- sodium streetlight or weak tube light flattening the skin to dusty cool;
- doorway silhouette where the figure reads as outline first, face second.
Avoid soft beauty lighting, devotional glow, warm halo light, dreamy
backlight, heroic rim lighting, saintly illumination, balanced studio
three-point lighting, or even overcast daylight that flattens the face into
neutrality."""

NEW_SHARED_27 = """§2.7 LIGHTING RULE FOR HOSTILE ACTORS (HOSTILE-SUBJECT SCENES ONLY)
When §2 applies, use directional menace lighting on the hostile figure while
keeping the face readable (eyes, brow, beard line visible):
- harder side light or back-rim light with one side in controlled shadow;
- weak phone glow under the chin or across one eye, not full-face blackout;
- single low overhead bulb creating downward shadow under brows while preserving
  facial structure;
- sodium streetlight or weak tube light with dusty cool skin tones;
- partial doorway shadow where posture and grooming still read before silhouette.
Avoid soft beauty lighting, devotional glow, warm halo light, dreamy backlight,
heroic rim lighting, or saintly illumination on hostile subjects.
Do NOT apply §2.7 lighting to non-hostile civilians, neutral rooms, or ordinary
daylight scenes — use SHARED §1 motivated natural or institutional light instead."""

OLD_SHARED_29_TAIL = """When in doubt: more menace, not less. The story-safety risk is softness,
not severity."""

NEW_SHARED_29_TAIL = """When in doubt on a confirmed hostile-subject scene: strengthen menace through
expression, posture, and costume — not by crushing the entire frame to unreadable
darkness. The story-safety risk on hostile beats is softness, not severity."""

# Stage C uses 2-space indent on SHARED blocks
def indent_block(text: str, spaces: int = 2) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in text.splitlines())


OLD_SHARED_1_C = indent_block(OLD_SHARED_1_A.replace(
    "when describing visual defaults:",
    "in every IMAGE PROMPT:",
).replace(
    "Use this visual language implicitly when describing visual defaults:",
    "Use this visual language implicitly in every IMAGE PROMPT:",
), 2)

# Fix: stage-c original uses "in every IMAGE PROMPT" already
OLD_SHARED_1_C = """  --------------------------------------------------------------------------------
  SHARED §1 — GLOBAL STYLE LOCK
  --------------------------------------------------------------------------------

  Use this visual language implicitly in every IMAGE PROMPT:

  2D digital animated illustration; cinematic hand-drawn 2D matte painting; clean
  hand-drawn line art; flat cel shading; minimal texture; simplified forms with
  strong readability; documentary realism; restrained stylisation; region-accurate
  facial features; historically grounded environments; muted documentary color
  palette unless the scene clearly requires warmer or brighter tonal treatment;
  no photorealism; no 3D rendering; no ray tracing; no global illumination;
  no depth of field blur; no cinematic lens artifacts; no glossy CGI finish;
  no hyper-detailed skin texture; no HDR realism.

  Always implicitly avoid: photorealistic; ultra realistic; 3D render; CGI;
  ray tracing; global illumination; lens flare; bokeh; depth of field blur;
  bloom; volumetric fantasy light; hyper-detailed pores; photo textures;
  futuristic design unless era supports it; neon colors unless era and setting
  clearly support them; watermark; logo; text overlay; poster layout;
  empty stage-like backgrounds."""

NEW_SHARED_1_C = indent_block(
    NEW_SHARED_1_A.replace(
        "when describing visual defaults and in every\nIMAGE PROMPT:",
        "in every IMAGE PROMPT:",
    ),
    2,
)

NEW_SHARED_1A_C = indent_block(NEW_SHARED_1A_A.strip(), 2)

OLD_SHARED_2_HEADER_C = indent_block(OLD_SHARED_2_HEADER, 2)
NEW_SHARED_2_HEADER_C = indent_block(NEW_SHARED_2_HEADER, 2)

OLD_SHARED_27_C = indent_block(OLD_SHARED_27, 2)
NEW_SHARED_27_C = indent_block(NEW_SHARED_27, 2)

OLD_SHARED_29_TAIL_C = indent_block(OLD_SHARED_29_TAIL, 2)
NEW_SHARED_29_TAIL_C = indent_block(NEW_SHARED_29_TAIL, 2)

# --- Stage A spec patches ---

STAGE_A_COLOR_I = """I. COLOR SCRIPT DEFAULT
Recommend a default palette per story tone — e.g. cold blue institutional;
warm amber domestic; desaturated grey tension; muted earth tones; night
sodium yellow; dusty daylight; restrained cyber screen glow. If hostile
actors appear, define their palette as muted, shadowed, dusty, desaturated,
or dimly lit — never warm, heroic, glamorous, or devotional."""

NEW_STAGE_A_COLOR_I = """I. COLOR SCRIPT DEFAULT
Recommend setting-specific palettes grounded in THIS story — e.g. monsoon
grey-green exteriors; warm afternoon domestic amber; cool institutional
fluorescent; dusty highway ochre; festival saffron and marigold; night market
sodium and shop-front tungsten. Daylight scenes should stay naturally lit with
local colour, not globally desaturated. If hostile actors appear, define their
palette separately as muted, shadowed, dusty, or dimly lit — never warm, heroic,
glamorous, or devotional. If hostile actors are absent, mark hostile palette
fields N/A."""

STAGE_A_ANCHOR_N = """N. PRIMARY VISUAL ANCHOR GUIDANCE
What dominates the frame across most scenes — e.g. face, phone, laptop
screen, evidence folder, map, checkpoint, officer's hand, family doorway,
empty street, press camera, courtroom bench, aircraft, border road,
hospital bed, long-bearded militant figure, shadowed phone-lit face,
closed shopfront, suspicious group posture. Explain how abstract lines
should be anchored. If hostile actors appear, indicate whether the anchor
should be threatening posture, shadowed face, suspicious phone use, tense
group attention, hidden device, evidence screen, or network map."""

NEW_STAGE_A_ANCHOR_N = """N. PRIMARY VISUAL ANCHOR GUIDANCE
What dominates the frame across most scenes — derive from THIS story's actual
beats (e.g. face, crowd, landscape, building facade, vehicle, market stall,
family doorway, podium, map, document, phone, checkpoint, aircraft, border
road, hospital bed). Do NOT default to desk-monitor-evidence-board templates
when the narration supports richer anchors. Explain how abstract lines should
be anchored in story-specific places and objects. If hostile actors appear,
indicate whether the anchor should be threatening posture, guarded expression,
suspicious phone use, tense group attention, or hidden device — otherwise N/A."""

STAGE_A_PART2_INSERT = """WHAT TO ANALYZE

A. STORY IDENTITY"""

NEW_STAGE_A_PART2_INSERT = """CONTINUITY vs VISUAL DEFAULTS (apply while analyzing)
- Lock factual continuity: era, geography, architecture, cast identity, library
  matches, hostile-actor presence (yes/no), public figures, sensitive exclusions.
- Set adaptable visual defaults per story: dominant times of day, seasonal light,
  regional palette families, typical environments — grounded in the FULL_STORY,
  not generic crime/investigation styling.
- When hostile actors are absent, output N/A for every HOSTILE ACTOR VISUAL PROFILE
  field and do not recommend threat lighting for ordinary scenes.

WHAT TO ANALYZE

A. STORY IDENTITY"""

# --- Stage B patches ---

OLD_STAGE_B_PART1 = """================================================================================
PART 1 — GLOBAL STYLE LOCK
================================================================================

Use this visual language implicitly when describing scene metadata:

2D digital animated illustration; cinematic hand-drawn 2D matte painting;
clean hand-drawn line art; flat cel shading; documentary realism; restrained
stylisation; historically grounded environments; region-accurate faces;
muted documentary color palette; readable composition; no empty stage-like
backgrounds.

Avoid:
photorealism; ultra realism; 3D render; CGI; ray tracing; global illumination;
lens flare; bokeh; depth of field blur; glossy CGI; hyper-detailed pores;
HDR realism; neon unless story era supports it; watermark; logo; readable
text overlay; poster layout; split-screen collage."""

NEW_STAGE_B_PART1 = """================================================================================
PART 1 — GLOBAL STYLE LOCK
================================================================================

Use this visual language implicitly when describing scene metadata:

Semi-realistic hand-drawn 2D graphic novel illustration; clean readable contours;
controlled cel shading; natural skin tones; expressive grounded faces; historically
grounded environments with concrete detail; setting-specific palettes and motivated
lighting; readable composition; no empty stage-like backgrounds; no uniform dark
or repetitive desk-monitor-silhouette templates unless narration supports them.

Avoid:
photorealism; ultra realism; 3D render; CGI; ray tracing; global illumination;
lens flare; bokeh; depth of field blur; glossy CGI; hyper-detailed pores;
HDR realism; uniformly dark grading on ordinary scenes; neon unless story era
supports it; watermark; logo; readable text overlay; poster layout; split-screen collage."""

NEW_STAGE_B_PART1A = """
================================================================================
PART 1A — SCENE-SPECIFIC VISUAL PLANNING
================================================================================

For each scene, derive ONE meaningful visual beat directly from the Hindi line:
- Choose the visible subject, action, and focal information the narration
  actually supports — not a default investigation template.
- Vary framing when the story changes location, era, mood, or scale; preserve
  continuity when it does not.
- Include motivated time of day and lighting inside Surrounding environment
  (e.g. "late-morning hazy daylight", "monsoon overcast", "night market under
  sodium lamps with readable faces").
- Avoid repeating desks, monitors, silhouettes, evidence boards, dim corridors,
  or aerial establishing tropes unless the narration explicitly supports them.
- Do NOT rotate camera scales mechanically scene-to-scene; pick the scale that
  best serves this beat per PART 19.
- Do NOT invent events, evidence, locations, characters, or props absent from
  the FULL_STORY.
- Preserve segmented-run overlap and scene-offset handling per automation rails.
"""

OLD_PART19_TAIL = """Do not use the same scale repeatedly without need.
Do not choose close reaction frame for scenes that require spatial context.
Do not choose wide establishing for scenes that are about a file, phone, map,
face, or hand."""

NEW_PART19_TAIL = """Choose scale from the narration and visual beat — do NOT rotate scales
mechanically (wide → medium → close → repeat) without story motivation.
Do not use the same scale repeatedly without need.
Do not choose close reaction frame for scenes that require spatial context.
Do not choose wide establishing for scenes that are about a file, phone, map,
face, or hand unless the Hindi line calls for spatial overview."""

OLD_PART17_DIM = """- dim corridor lighting"""

NEW_PART17_DIM = """- motivated corridor lighting matching time of day (not default dim)"""

# --- Stage C patches ---

OLD_C_MASTER = """  - render in cinematic hand-drawn 2D matte painting (SHARED §1);"""

NEW_C_MASTER = """  - render in semi-realistic hand-drawn 2D graphic novel style (SHARED §1);"""

OLD_C_OPENER = """  Scene {number}. {short scene context label}. Create a cinematic hand-drawn 2D matte painting set in {ERA}; {CITY}; {STATE OR REGION}; {COUNTRY};"""

NEW_C_OPENER = """  Scene {number}. {short scene context label}. Create a semi-realistic hand-drawn 2D graphic novel illustration set in {ERA}; {CITY}; {STATE OR REGION}; {COUNTRY};"""

OLD_C_EXAMPLE = """  Scene 1. Opening Cyber Room Silence. Create a cinematic hand-drawn 2D matte painting set in Contemporary 2020s; Delhi; Delhi NCR; India;"""

NEW_C_EXAMPLE = """  Scene 1. Opening Cyber Room Silence. Create a semi-realistic hand-drawn 2D graphic novel illustration set in Contemporary 2020s; Delhi; Delhi NCR; India;"""

OLD_C_OUTPUT_FORMAT = """  Scene {X}. {short scene context label}. Create a cinematic hand-drawn 2D matte painting set in {ERA}; {CITY}; {STATE OR REGION}; {COUNTRY}; {full single-line descriptive prompt with Foreground: Midground: Background: Lighting: Texture & Materials: Atmosphere: NEGATIVE:} ||"""

NEW_C_OUTPUT_FORMAT = """  Scene {X}. {short scene context label}. Create a semi-realistic hand-drawn 2D graphic novel illustration set in {ERA}; {CITY}; {STATE OR REGION}; {COUNTRY}; {full single-line descriptive prompt with Foreground: Midground: Background: Lighting: Texture & Materials: Atmosphere: NEGATIVE:} ||"""

OLD_C_ROLE = """  specialized in historically grounded 2D matte painting scene generation."""

NEW_C_ROLE = """  specialized in historically grounded semi-realistic 2D graphic novel scene generation."""

# Motion block replacement (large)
OLD_MOTION_BLOCK_START = "  MANDATORY TWO-CLAUSE STRUCTURE — descent + push-in"
OLD_MOTION_BLOCK_END = "  which range to request next. No other commentary or explanation."

NEW_MOTION_SECTION = """  MOTION STRUCTURE — static hold or one restrained camera move
  Every DIGEN MOTION PROMPT must use ONE of these patterns (choose what fits
  the locked Camera scale suggestion and scene — do NOT default to aerial):

  Pattern A — STATIC HOLD (preferred for close/medium beats):
    "[View type matching breakdown scale] holds steady on [main subject /
    anchor object]; minimal drift only if needed for life."

  Pattern B — ONE RESTRAINED PUSH or TRAVEL (when wider context matters):
    "[Starting view aligned to breakdown scale] slowly [pushes closer /
    tracks gently / lowers slightly] toward [main subject or anchor object],
    ending on a tighter but still readable framing."

  Pattern C — DOORWAY / INTERIOR REVEAL (domestic or institutional interiors):
    "From [doorway / threshold / over-shoulder view], camera slowly pushes
    inward and settles on [main subject / group / object] held in stillness."

  Rules:
  - Match the starting viewpoint to the locked Camera scale suggestion from
    Stage B — do NOT override with aerial/descent unless the breakdown
    explicitly chose Wide establishing / Elevated street view AND the
    narration supports an exterior overview.
  - ONE continuous camera move maximum; slow, smooth, restrained.
  - Subjects stay STILL; describe camera motion only (preserve subject-stillness
    rules above this section).
  - Motion must end equal or closer to the main subject; never pull back wider.
  - Night scenes remain readable — do not chase darkness in motion wording.

  Forbidden as default (use only when breakdown explicitly requires):
  - Mandatory aerial view / high aerial / night aerial opening;
  - Compulsory "slowly descending" as clause 1 for every scene;
  - Two-clause aerial descent + push-in template applied uniformly.

  Legacy conflict flag: If the LOCKED SCENE BREAKDOWN or STORY CONFIG carries
  lighting/pose language that conflicts with SHARED §1 readable-face rules or
  §2 hostile-only menace lighting, preserve library anchors verbatim but apply
  this template's scene-specific readable lighting in the Lighting: clause —
  do not silently drop locked anchors or ignore readable-face requirements.

  Preferred starting viewpoints (choose to match breakdown scale, not by rotation):
  - Eye-level or medium character view on [subject]
  - Over-shoulder view from behind [character archetype]
  - Doorway view into [the room / space]
  - Medium-wide environmental view of [location]
  - Elevated room view (interiors only, when breakdown specifies)
  - Wide establishing / elevated street view (exteriors only, when breakdown specifies)
  - Tight object detail view on [anchor object]

  Preferred motion verbs:
  holds steady on • holds on • minimal drift • slowly pushes closer • gently
  moves closer • slowly tracks toward • softly settles on • slowly pushes inward.

  Do NOT use verbs that imply speed, performance, or compulsory aerial descent:
  fast push, rapid move, rush, sweep, whip, dramatic zoom, aggressive push,
  subject reacts, lips move, eyes blink, expression changes, slowly descending
  (unless breakdown explicitly requires exterior aerial overview).

  Length: ONE short sentence or two short sentences joined by `;`. Never a long
  cinematic paragraph. When unsure, choose a static hold with less motion.

  Canonical examples — follow this rhythm (not aerial-by-default):
  - "Medium character view holds steady on the seated strategist's restrained
    expression and folded hands; minimal drift only."
  - "Medium-wide environmental view of the campaign lane slowly pushes closer
    toward the poster wall and the figure paused mid-step."
  - "From doorway view into the family kitchen, camera slowly pushes inward
    and settles on the mother held in stillness beside the window light."
  - "Over-shoulder view from behind the analyst slowly moves closer toward the
    paused screen; camera holds on the tense hands near the keyboard."
  - "Wide establishing view of the riverside ghat holds steady on the crowd
    and the central figure, readable faces in late-afternoon light."
  - "Tight object detail view on the sealed file slowly pushes closer and
    holds on the worn paper edge and official stamp."

  Scene-specific guidance:
  - exteriors / streets / crowds → match breakdown scale; prefer eye-level or
    medium-wide unless overview is narratively required; readable faces;
  - domestic interiors → doorway or over-shoulder start, slow inward push,
    settle on faces, seated group, table, or window light;
  - object-led beats → tight or medium detail on the object, restrained push;
  - institutional / strategy rooms → elevated room or over-shoulder when breakdown
    specifies; restrained forward push, hold on people or maps — not default
    monitor glow unless narration supports it;
  - hostile actor scenes (when §2 applies) → partial-shadow framing acceptable
    but face structure must remain readable; one restrained push toward tense
    hands, guarded eyes, or device — not compulsory aerial descent.

  MOTION FINAL AUDIT — BEFORE OUTPUT
  Before writing each DIGEN MOTION PROMPT, scan it and reject/rewrite if it
  contains any lip-sync, mouth movement, blinking, facial animation, expression
  change, subject movement, fast camera movement, sudden movement, compulsory
  aerial opening, or uniform descent template. The final prompt must describe
  only one very slow static hold or one gentle camera move ending on the frozen
  subject.

  OUTPUT REQUIREMENT
  The DIGEN MOTION PROMPT must be one short sentence with optional second
  clause joined by a semicolon.
  It must not become a cinematic paragraph.
  It must not introduce new action beyond the still IMAGE PROMPT.
  When uncertain, choose a static hold — less motion.

  OUTPUT FORMAT (STAGE C) — exact format per scene

  --- Scene {X} / ~{TOTAL_ESTIMATED_SCENES} ---
  Hindi line:
  {exact Hindi line copied from the LOCKED SCENE BREAKDOWN}

  IMAGE PROMPT
  Scene {X}. {short scene context label}. Create a semi-realistic hand-drawn 2D graphic novel illustration set in {ERA}; {CITY}; {STATE OR REGION}; {COUNTRY}; {full single-line descriptive prompt with Foreground: Midground: Background: Lighting: Texture & Materials: Atmosphere: NEGATIVE:} ||

  DIGEN MOTION PROMPT
  {camera motion description}

  STAGE C FORMATTING RULES
  - no empty lines inside a scene block other than the structural breaks above;
  - "Hindi line:" must match the LOCKED SCENE BREAKDOWN exactly (SHARED §6);
  - never split, merge, rewrite, renumber, add, or remove scenes;
  - never force multi-location content into one scene unless the locked scene
    itself supports one visible frame;"""

OLD_C_COLOR = """  COLOR SCRIPT GUIDANCE
  Let color mood evolve with story tension while staying historically grounded:
  - routine life = muted natural tones;
  - fear/uncertainty = cooler desaturated tones;
  - night control = sodium yellow, weak tungsten, deep blue-grey ambient;
  - decision/power interiors = restrained warm interiors with disciplined contrast;
  - cyber monitoring = dim blue-grey screen light + weak institutional ceiling;
  - investigation = cool screens, dull file-paper beige, muted desk-lamp warmth;
  - domestic tension = low warm bulbs, phone glow, shadowed corners;
  - hostile actor (SHARED §2.7) = dim side light, shadowed faces, muted earth
    tones, cold phone glow, rough interior darkness, no beauty lighting;
  - aftermath / dread-heavy = drained dusty or cold subdued palette.
  Never use decorative color for its own sake. Color must support story mood
  and period realism."""

NEW_C_COLOR = """  COLOR SCRIPT GUIDANCE
  Follow the STORY CONFIG BLOCK palette first. Let color mood evolve with story
  tension while staying historically grounded and readable:
  - routine daylight life = natural local tones (warm stone, green foliage, sky blue);
  - fear/uncertainty = cooler desaturated tones without crushing blacks;
  - night = sodium yellow, shop tungsten, window spill — faces still readable;
  - decision/power interiors = restrained warm interiors with disciplined contrast;
  - cyber monitoring = screen spill + ambient room light (not pitch-dark room default);
  - investigation = cool screens, file-paper beige, desk-lamp warmth when narrated;
  - domestic = window daylight or warm bulbs matching time of day;
  - hostile actor (SHARED §2.7, hostile-subject scenes only) = directional side light,
    readable facial structure, muted earth tones, cold phone glow when relevant;
  - aftermath / dread-heavy = drained dusty or cold subdued palette when narrated.
  Never use decorative color for its own sake. Never apply investigation-dark or
  hostile palette globally. Color must support story mood and period realism."""

OLD_C_INTERP = """  SCENE INTERPRETATION RULE
  Each locked scene = ONE final 5-second visual beat = ONE single frozen
  cinematic frame. Within one scene:"""

NEW_C_INTERP = """  SCENE INTERPRETATION RULE
  Each locked scene = ONE final 5-second visual beat = ONE single frozen
  graphic-novel frame with clear subject hierarchy. Follow the locked breakdown
  without rewriting narration or scene IDs. Within one scene:"""


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    i = text.find(start)
    if i < 0:
        raise ValueError(f"Start marker not found: {start[:60]!r}...")
    j = text.find(end, i + len(start))
    if j < 0:
        raise ValueError(f"End marker not found after {start[:60]!r}...")
    return text[:i] + replacement + text[j:]


def patch_stage_a(text: str) -> str:
    text = text.replace(OLD_SHARED_1_A, NEW_SHARED_1_A)
    text = text.replace(
        OLD_SHARED_2_HEADER,
        NEW_SHARED_2_HEADER,
        1,
    )
    text = text.replace(OLD_SHARED_27, NEW_SHARED_27, 1)
    text = text.replace(OLD_SHARED_29_TAIL, NEW_SHARED_29_TAIL, 1)
    if NEW_SHARED_1A_A.strip() not in text:
        text = text.replace(
            NEW_SHARED_1_A.split("Always implicitly avoid")[0].rstrip(),
            NEW_SHARED_1_A.split("Always implicitly avoid")[0].rstrip() + NEW_SHARED_1A_A,
            1,
        )
    text = text.replace(STAGE_A_COLOR_I, NEW_STAGE_A_COLOR_I, 1)
    text = text.replace(STAGE_A_ANCHOR_N, NEW_STAGE_A_ANCHOR_N, 1)
    text = text.replace(STAGE_A_PART2_INSERT, NEW_STAGE_A_PART2_INSERT, 1)
    return text


def patch_stage_b(text: str) -> str:
    text = text.replace(OLD_STAGE_B_PART1, NEW_STAGE_B_PART1, 1)
    if "PART 1A — SCENE-SPECIFIC VISUAL PLANNING" not in text:
        text = text.replace(
            NEW_STAGE_B_PART1,
            NEW_STAGE_B_PART1 + NEW_STAGE_B_PART1A,
            1,
        )
    text = text.replace(OLD_PART19_TAIL, NEW_PART19_TAIL, 1)
    text = text.replace(OLD_PART17_DIM, NEW_PART17_DIM, 1)
    return text


def patch_stage_c(text: str) -> str:
    text = text.replace(OLD_SHARED_1_C, NEW_SHARED_1_C, 1)
    if "SHARED §1A — FACTUAL CONTINUITY LOCKS" not in text:
        insert_at = text.find("  --------------------------------------------------------------------------------\n  SHARED §2")
        if insert_at < 0:
            raise ValueError("Could not find SHARED §2 in stage C")
        text = text[:insert_at] + NEW_SHARED_1A_C + "\n\n" + text[insert_at:]
    text = text.replace(OLD_SHARED_2_HEADER_C, NEW_SHARED_2_HEADER_C, 1)
    text = text.replace(OLD_SHARED_27_C, NEW_SHARED_27_C, 1)
    text = text.replace(OLD_SHARED_29_TAIL_C, NEW_SHARED_29_TAIL_C, 1)
    text = text.replace(OLD_C_MASTER, NEW_C_MASTER, 1)
    text = text.replace(OLD_C_ROLE, NEW_C_ROLE, 1)
    text = text.replace(OLD_C_OPENER, NEW_C_OPENER, 1)
    text = text.replace(OLD_C_EXAMPLE, NEW_C_EXAMPLE, 1)
    text = text.replace(OLD_C_OUTPUT_FORMAT, NEW_C_OUTPUT_FORMAT, 1)
    text = text.replace(OLD_C_COLOR, NEW_C_COLOR, 1)
    text = text.replace(OLD_C_INTERP, NEW_C_INTERP, 1)
    # Replace motion block through formatting rules header (keep rest of formatting rules from file)
    text = replace_between(
        text,
        OLD_MOTION_BLOCK_START,
        "  STAGE C FORMATTING RULES\n  - no empty lines inside a scene block",
        NEW_MOTION_SECTION + "\n",
    )
    return text


PATCHERS = {
    "stage-a-story-config.md": patch_stage_a,
    "stage-b-scene-breakdown.md": patch_stage_b,
    "stage-c-image-motion.md": patch_stage_c,
}

REQUIRED_CHECKS = {
    "stage-a-story-config.md": [
        "PART 3 — INPUT SLOTS",
        "{Paste the full Hindi / Hinglish / English story here.}",
        "CHARACTER_LIBRARY:",
        "STORY CONFIG BLOCK",
        "END OF STORY CONFIG BLOCK",
    ],
    "stage-b-scene-breakdown.md": [
        "PART 3 — INPUT SLOTS",
        "{Paste the STORY CONFIG BLOCK output from Stage A here.}",
        "{Paste the full Hindi / Hinglish / English story here — same as used in Stage A.}",
        "--- Scene {X} / ~{TOTAL_ESTIMATED_SCENES} ---",
        "Hindi line:",
        "Library lock:",
    ],
    "stage-c-image-motion.md": [
        "PART 3 — INPUT SLOTS",
        "SCENE_RANGE:",
        "{Paste the STORY CONFIG BLOCK output from Stage A here.}",
        "{Paste the LOCKED SCENE BREAKDOWN output from Stage B here.}",
        "IMAGE PROMPT",
        "DIGEN MOTION PROMPT",
        " ||",
        "NEXT_RANGE:",
    ],
}

REMOVED_REFS = [
    "MANDATORY TWO-CLAUSE STRUCTURE — descent + push-in",
    "Every motion prompt MUST follow this exact two-clause shape",
]

STAGE_C_MUST_HAVE = [
    "3000 characters",
    "semi-realistic hand-drawn 2D graphic novel",
    "MOTION STRUCTURE — static hold or one restrained camera move",
]


def validate(name: str, text: str) -> list[str]:
    errors: list[str] = []
    for token in REQUIRED_CHECKS[name]:
        if token not in text:
            errors.append(f"missing required token: {token!r}")
    if name == "stage-c-image-motion.md":
        for token in STAGE_C_MUST_HAVE:
            if token not in text:
                errors.append(f"missing stage-c requirement: {token!r}")
    for bad in REMOVED_REFS:
        if bad in text:
            errors.append(f"removed instruction still present: {bad!r}")
    return errors


def main() -> int:
    EXPORT.mkdir(parents=True, exist_ok=True)
    all_ok = True
    results: dict[str, list[str]] = {}

    for fname in FILES:
        src = AUTOMATION / fname
        raw = src.read_text(encoding="utf-8")
        patched = PATCHERS[fname](raw)
        errors = validate(fname, patched)
        results[fname] = errors
        if errors:
            all_ok = False
            print(f"FAIL {fname}:")
            for e in errors:
                print(f"  - {e}")
            continue

        for dest_root in (AUTOMATION, CMS, EXPORT):
            dest = dest_root / fname
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(patched, encoding="utf-8")
        print(f"OK {fname} -> automation, cms, export")

    print("\nExport folder:", EXPORT)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
