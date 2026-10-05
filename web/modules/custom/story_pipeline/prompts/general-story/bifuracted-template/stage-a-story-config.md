================================================================================
STORYBOARD PIPELINE — STAGE A: STORY CONFIG ENGINE (standalone)
Derived from STORYBOARD MASTER PROMPT — UNIFIED v2.1
================================================================================

HOW TO USE THIS FILE WITH CHATGPT
1. Open a new ChatGPT chat.
2. Copy this ENTIRE file and paste it as your first message.
3. At the very bottom, fill in the input slot:
      FULL_STORY:        <-- paste the Hindi/Hinglish/English story
      OPTIONAL_GENRE_OR_TONE: <-- optional, can be left blank
4. Send. ChatGPT will return ONLY the STORY CONFIG BLOCK.
5. Save that STORY CONFIG BLOCK — it is the input to Stage B.

PIPELINE POSITION
   Story (Hindi / Hinglish / English)
        |
        v
   >>> STAGE A — STORY CONFIG ENGINE (this file) <<<
        produces: STORY CONFIG BLOCK
        |
        v
   STAGE B — SCENE BREAKDOWN ENGINE
        produces: LOCKED SCENE BREAKDOWN
        |
        v
   STAGE C — IMAGE + MOTION PROMPT ENGINE
        produces: IMAGE PROMPT + DIGEN MOTION PROMPT per locked scene


================================================================================
PART 0 — DISPATCHER (locked to STAGE A)
================================================================================

ACTIVE STAGE: A

Behavior:
- Execute ONLY the STAGE A SPEC below.
- Read the FULL_STORY (and OPTIONAL_GENRE_OR_TONE if provided).
- Read the CHARACTER_LIBRARY input slot if non-empty, and apply SHARED
  §12 (locked character library) before falling back to character
  inference per SHARED §3 and §5.
- Output ONLY the STORY CONFIG BLOCK in the exact format defined in this file.
- Do NOT generate scenes. Do NOT summarize. Do NOT add commentary.
- Do NOT output anything before or after the STORY CONFIG BLOCK.


================================================================================
PART 1 — SHARED LIBRARY (read by this stage)
================================================================================

This library is the single source of truth for cross-stage rules. The Stage A
spec references it by section number. Do NOT inline-rewrite these rules inside
the stage spec.

--------------------------------------------------------------------------------
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
ray tracing; lens flare; bokeh;
bloom; volumetric fantasy light; hyper-detailed pores; photo textures;
uniformly dark or sinister grading on ordinary non-threat scenes; repetitive
desk-monitor-silhouette-evidence-board templates when narration supports a
different anchor; futuristic design unless era supports it; neon colors unless era
and setting clearly support them; watermark; logo; text overlay; poster layout;
empty stage-like backgrounds.

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
threat lighting to ordinary civilians or neutral scenes.

--------------------------------------------------------------------------------
SHARED §1B — DEFINITE VISUAL REALIZATION
--------------------------------------------------------------------------------

Final IMAGE PROMPT text must describe ONE definite realization per visual attribute.
Do NOT leave mutually exclusive appearance, setting, camera, or action choices
unresolved in generated output.

Examples of FORBIDDEN unresolved alternatives:
- "shirt or kurta"
- "clean-shaven or trimmed beard"
- "dark-brown/black hair"
- "parked or slowly moving"
- wide age spans such as "30s to 50s" when a single casting band is required

This rule targets unresolved visual alternatives — not ordinary grammatical "or"
inside quoted narration or abstract prose.

FACTUAL vs CASTING:
- Do NOT invent a historical age, identity, or location and present it as established fact.
- When the source is silent, choose one plausible casting value; approximate age is acceptable.
- Library-locked traits are exact — copy verbatim; offer no alternatives.

Stage A: for recurring characters without library lock, record one definite visual identity
in roster fields (single hair colour, grooming choice, clothing baseline, build cues).
Stage B: commit to one supported staging choice per scene; do not output alternative
locations, poses, vehicle states, or object sides when one frame requires a decision.
Stage C: render the selected choice consistently; if plot-critical uncertainty cannot be
resolved from source, use a broader supported depiction rather than inventing a fact.
--------------------------------------------------------------------------------
SHARED §1C — VIEWPOINT, CAMERA MOVEMENT, AND SUBJECT MOVEMENT (THREE DECISIONS)
--------------------------------------------------------------------------------

These are separate decisions — do not collapse them:

A. VIEWPOINT / FRAMING (Stage B → Camera scale suggestion; Stage C → IMAGE PROMPT):
   wide, medium, close-up, insert, side/profile, over-shoulder, low angle, elevated,
   overhead, aerial — chosen for what the viewer must notice.

B. CAMERA MOVEMENT (Stage C → DIGEN MOTION PROMPT only):
   locked-off hold OR one slow restrained move (push-in, pull-back, small pan/tilt,
   short lateral slide, gentle tracking, limited arc, slow aerial drift when the image
   is already aerial). A close-up is not movement.

C. SUBJECT MOVEMENT (frozen in current pipeline):
   stillness or a small story-supported frozen action in the IMAGE PROMPT only.
   Do not add walking, driving, or lip-sync in the motion prompt.

Stage B records camera purpose silently in Breakdown note (geography, interaction,
emotion, action, evidence, consequence). Stage C matches motion to that purpose.

Reject before output: slash-separated visual attributes, "A or B" grooming/garment/vehicle
alternatives, or wide age spans when a single casting band is required.

--------------------------------------------------------------------------------
SHARED §2 — HOSTILE / SUSPECT / CRIMINAL SUBJECT CODING (CONDITIONAL)
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
are N/A. Stages B and C do not apply §2.

--------------------------------------------------------------------------------
SHARED §3 — REGION / ORIGIN / IDEOLOGY VISUAL MAPPING
--------------------------------------------------------------------------------

For every recurring character or group, detect and assign:

§3.1 GEOGRAPHIC ORIGIN
country • state/province/region • city/town/village • border region •
diaspora/foreign location.

§3.2 ETHNO-REGIONAL VISUAL CONTEXT
South Asian Indian • Pakistani Punjabi • Pakistani Pashtun / KPK / tribal belt
• Afghan / Taliban-style border region • Kashmiri • Bengali • Middle Eastern
• Western • mixed • unknown.

§3.3 ROLE CATEGORY
ordinary civilian • family member • journalist • police officer • military
officer • intelligence official • politician/public figure • cyber analyst •
hostile actor • terrorist commander • extremist recruiter • radical
propagandist • criminal operative • handler • suspect • victim • student •
crowd.

§3.4 IDEOLOGICAL / ORGANISATIONAL CONTEXT
Islamist militant • Pakistan-based militant network • Taliban-style militant •
Lashkar-e-Taiba-linked militant • Jaish-e-Mohammed-linked militant •
separatist militant • criminal gang • cyber propaganda network • political
group • official state actor • neutral civilian • unknown.

§3.5 APPEARANCE COMBINATION RULE
Visual styling = origin + region + era + class + role + ideology + story
context. Do NOT apply hostile coding only because of religion, ethnicity,
country, beard, clothing, or region. Apply militant/extremist coding ONLY
when the story identifies the person/group as terrorist, extremist, militant,
radical handler, hostile recruiter, propagandist, violent conspirator, terror
commander, operative, handler, or suspect linked to hostile activity.

§3.6 PAKISTAN-BASED ISLAMIST MILITANT CONTEXT (CONDITIONAL)
Apply only when the story explicitly names the actor as a Pakistan-based Islamist
militant, terror commander, extremist recruiter, LeT/JeM-linked figure, Taliban-style
militant, or jihadist handler — not from religion or dress alone.

When this profile applies, use story-supported behaviour and period-accurate regional
clothing. Faces remain readable. Do NOT require heavy beard, skullcap, pakol, or turban
unless the story establishes that appearance. Do NOT ban clean-shaven or trimmed grooming
unless disguise is narratively excluded.

Avoid: readable religious text; extremist logos; propaganda glorification; graphic gore;
making ordinary Muslim civilians look threatening (SHARED §2.6).

§3.7 ARCHETYPE QUICK REFERENCE
A. Pakistan-based Islamist militant / LeT / JeM / terror commander — see §3.6.
B. KPK / tribal-belt / Afghan-border hostile militant — Pashtun cues, long
   beard, pakol/turban/skullcap, loose shalwar kameez, rough waistcoat, dusty
   sandals, weathered face, sharper cheekbones, guarded watchful posture,
   harsh side or sodium streetlight; no polished urban styling.
C. Taliban-style militant — long beard; turban or wrapped head covering;
   loose traditional clothing; rugged shawl or waistcoat; austere palette;
   severe expression; controlled stillness; no glamour; no heroic pose;
   no readable religious text or flags.
D. Urban radical propagandist / digital extremist — more urban than rural;
   trimmed or full beard depending on age/background; plain kurta, shirt,
   hoodie, jacket, or waistcoat; cheap smartphone, laptop, headphones,
   charging cables, dim room; tense screen-lit face; guarded expression;
   manipulative posture; no influencer glamour; no soft teacher warmth.
E. Generic criminal operative — local-class clothing; rough grooming;
   suspicious posture; watchful eyes; practical dark/muted clothing;
   no religious coding unless story gives it; no ethnic stereotyping.
F. Indian intelligence / police / official — disciplined posture; formal
   shirt, safari suit, suit, police uniform, field jacket, or plain civilian
   operational clothing per era; controlled expression; files, maps, radios,
   phones, desks, evidence boards; no flashy hero costume; no superhero pose.
G. Ordinary Pakistani / Indian / Afghan / Kashmiri Muslim civilian —
   everyday regional clothing; may have beard, skullcap, kurta, hijab, shawl,
   or traditional clothing per context; neutral, worried, cautious, or
   ordinary expression; domestic, street, market, family, or work posture;
   must NOT be made threatening unless story identifies them as hostile;
   avoid suspicious lighting just because of religious clothing.
H. Victims / families / bystanders — vulnerable, confused, tense, worried, or
   cautious body language; ordinary clothing and grounded domestic/public
   detail; never hostile-coded unless story later reveals them as hostile.

--------------------------------------------------------------------------------
SHARED §4 — PUBLIC FIGURE & NO-EXPLICIT-NAME RULE
--------------------------------------------------------------------------------

§4.1 SCOPE
Applies to politicians, ministers, advisors, military leaders, intelligence
chiefs, prime-ministerial figures, and any other recognizable real public
person.

§4.2 ABSOLUTE NAME RULE
Real names of public figures may appear ONLY where the original source itself
already contains the name inside "Hindi line:". They MUST NOT appear anywhere
else in any generated output, in any stage. This includes: scene context
labels, IMAGE PROMPT prefix, IMAGE PROMPT body, NEGATIVE section, DIGEN MOTION
PROMPT, metadata fields, breakdown notes, or any character reference outside
"Hindi line:".

§4.3 ARCHETYPE CONVERSION
Outside "Hindi line:", convert public figures into descriptive archetypes:
physical appearance, role, age, dress, posture, presence. Examples of valid
phrasing:
- "a senior Indian home minister figure, early 60s, heavyset, bald crown,
  close-cropped white-grey beard..."
- "a senior Indian national security strategist figure, around 70–75, lean,
  high forehead, rectangular spectacles, dark moustache..."
- "a senior Indian prime-ministerial figure, late 60s to early 70s, white
  beard, swept-back white hair, composed statesman-like posture..."

§4.4 STRICTLY FORBIDDEN OUTSIDE "Hindi line:"
- Narendra Modi, Amit Shah, Ajit Doval, or any public figure's exact name
- initials or shortened forms clearly identifying the same person
- explicit identity labels, readable nameplates, readable insignia, readable
  party symbols
- exact-likeness instructions; rely on physical archetype description instead

§4.5 CONTINUITY
If a public figure appears repeatedly, lock the same descriptive archetype
across all relevant scenes.

--------------------------------------------------------------------------------
SHARED §5 — CHARACTER CONSISTENCY ENGINE
--------------------------------------------------------------------------------

§5.1 STABLE ATTRIBUTES (must remain constant across scenes unless story
forces a change)
age range; body build; face shape; skin tone; hairstyle; facial hair;
glasses; clothing family appropriate to story point; profession/status cues;
emotional baseline; posture language.

§5.2 CLOTHING-CHANGE TRIGGERS (only these justify a change)
time passage; location change; official setting change; disguise change;
day/night transition; uniform change.

§5.3 INFERENCE
If a recurring character first appears without enough textual detail, infer a
stable design from: era + geography + profession + class + role + context.
Lock the inferred identity and reuse it consistently.

§5.4 SUSPECT / HOSTILE RECURRING CHARACTERS (when §2 applies)
Maintain stable identity across scenes: same face structure, grooming, clothing,
footwear, bag, and props unless narration supports a change. Show tension through
story-supported action and expression — not automatic sinister appearance or
compulsory half-shadow.

§5.5 POSITIVE IDENTITY AND RECURRING OBJECTS
In roster and architecture fields choose ONE definite realization — never "jeep or sedan",
"maybe an officer", or "shirt or kurta". Vehicles and transport must name one type with
identifying features, not alternatives.

Recurring characters and objects need positive identity descriptions in IMAGE PROMPT text —
not generic negatives alone. Before any "no identity drift" negative, state the stable traits:
apparent age band, face structure, hairstyle and colour, facial hair, glasses, build,
clothing family, footwear, and identifying accessories for people; colour, material,
shape, size, and distinctive features for recurring objects (vehicles, bags, uniforms,
evidence items). Record recurring object traits in SPECIAL HANDLING NEEDS or roster-adjacent
notes when story-critical. Allow changes only when
narration, elapsed time, or an explicitly established costume change supports them.

On repeat appearances, restate only the traits needed for recognition — do not paste full
roster paragraphs every scene unless identity or costume changed.

--------------------------------------------------------------------------------
SHARED §6 — SOURCE TEXT (HINDI LINE) PRESERVATION
--------------------------------------------------------------------------------

The "Hindi line:" field carries the original Hindi/Hinglish/English wording.
Across all stages:

- Preserve exactly. Copy verbatim from source (Stage B) or from LOCKED SCENE
  BREAKDOWN (Stage C).
- Do NOT rewrite, paraphrase, summarize, simplify, correct grammar, add
  missing words, remove words, translate, modernize, or change punctuation
  unnecessarily.
- The only allowed modification is segmentation between scenes (Stage B only).

If the original Hindi line itself contains a public figure's real name, that
name is preserved ONLY inside "Hindi line:" (never repeated elsewhere — see
SHARED §4).

--------------------------------------------------------------------------------
SHARED §7 — ABSTRACT / CONCEPTUAL LINE TRANSLATION
--------------------------------------------------------------------------------

§7.1 IDENTIFICATION
Conceptual lines have no concrete subject or action — for example:
"तनाव नया नहीं था", "सन्नाटा अलग था", "Narrative की दिशा dangerous थी",
"यह सिर्फ video फैलाने की बात नहीं थी".

§7.2 IN STAGE B (BREAKDOWN)
Do not split abstract lines automatically. Merge short connected abstract
lines when:
- the same image can represent both;
- combined length is not too long;
- there is no location/subject/object/action/camera-scale change.
Do NOT merge abstract atmosphere with concrete operational detail (officers,
screens, files, maps, devices) — split those.

§7.3 IN STAGE C (IMAGE)
Translate the abstract line into one physically believable cinematic frame.
Use posture, setting, objects, lighting, and environmental tension to carry
meaning. Prefer grounded anchors: screens, maps, files, phones, hands, faces,
corridors, streets, closed rooms, evidence tables, muted crowds, empty
spaces, paused routines, silent offices, suspicious digital activity.
NEVER use fantasy symbolism, swirling smoke metaphors, surreal cross-sections,
or split-screen composites.

§7.4 ABSTRACT LINES INVOLVING DANGER / RADICALISATION / TERRORISM
Ground them through story-supported action and setting: tense faces, suspicious devices,
marked maps, closed shutters, coded notes without readable text, officers reviewing
evidence, guarded body language. Do NOT default to dim rooms or sinister faces when the
narration supports daylight or ordinary surroundings.

--------------------------------------------------------------------------------
SHARED §8 — SCENE CONTEXT LABEL RULES
--------------------------------------------------------------------------------

§8.1 SHAPE
3 to 8 words; title-like; concise; file-name friendly; no quotes; no slashes;
no punctuation overload; describes role, setting, action, mood, threat, or
object — not real names.

§8.2 NAME RULE
- Never use a public figure's real name.
- Avoid all real personal names where possible; describe role/archetype
  instead.

§8.3 SCENE LABEL CLARITY
Use concrete role + action + setting from the narration. Do not soften into vague labels,
but do not inject menace words (shadow, hardened, hostile) unless the story supports them.

  Weak (forbidden)              →   Clear (preferred)
  Young Man Watches Video       →   Courier Checks Phone Message
  Man Uses Phone                →   Suspect Reads Platform Alert
  Important Scene               →   Railway Locker Key Exchange
  Gentle Man In Room            →   Contact Waits At Tea Stall

§8.4 GOOD EXAMPLES
Opening Cyber Room Silence • Screens Replay Suspicious Video • Officer
Detects Forwarding Pattern • Digital Weapon Metaphor • Network Map Under
Review • Closed Room Security Briefing • Device Seizure Evidence Table •
Silent Street Under Watch • Domestic Phone Anxiety • Final Confirmation
Moment • Administrative Power Before Decision • Silent Strategist Studies
Thread Map • Hidden Propaganda Clip Reviewed.

§8.5 BAD EXAMPLES
This Scene Shows A Very Important Thing • Modi Takes Decision • Ajit Doval
Looks At Map • Amit Shah Sitting In Room • PM Scene • Very Dramatic Scene •
Innocent Looking Terrorist • Peaceful Extremist Speaker.

--------------------------------------------------------------------------------
SHARED §9 — CAMERA SCALE VOCABULARY
--------------------------------------------------------------------------------

Choose ONE per scene. Do not flatten every scene to the same scale.

- Wide establishing — geography, atmosphere, public space, institutional
  exterior, room-level mood.
- Medium-wide environmental — streets, rooms, checkpoints, offices, domestic
  interiors, investigation spaces, suspicious rooms, hostile gathering spaces.
- Medium character beat — posture, tension, interaction, restrained facial
  expression, guarded eye contact, body language.
- Tight object detail — phone, file, laptop, map, evidence item, hand
  gesture, door lock, document, screen, bag, device, key object.
- Over-shoulder analysis — digital evidence, investigation screens, planning
  tables, maps, laptops, propaganda videos, strategic review.
- Doorway interior view — domestic interiors, hidden observation, quiet
  tension, family clusters, secretive gatherings, room-entry perspectives.
- Elevated room view — monitoring rooms, meetings, evidence rooms, command
  rooms, institutional spaces, suspicious group rooms.
- Elevated street view — lanes, checkpoints, public tension, movement,
  crowds, deployment, exterior watch, suspicious street movement.
- Close reaction frame — emotional shock, realization, silence, fear,
  dialogue impact, hostile suspicion, predatory focus.
- Evidence-table view — seized devices, files, phones, maps, documents,
  coded notes without readable text, forensic review.

--------------------------------------------------------------------------------
SHARED §10 — VISUAL BEAT TYPE VOCABULARY
--------------------------------------------------------------------------------

Choose ONE per scene from:
Establishing atmosphere • Operational detail • Character reaction • Dialogue
turning point • Investigation analysis • Digital evidence • Domestic
reaction • Street tension • Closed-room decision • Field movement • Raid
preparation • Device seizure • Forensic review • Network mapping •
Consequence beat • Emotional punch • Climax beat • Aftermath beat •
Abstract commentary visualized physically.

--------------------------------------------------------------------------------
SHARED §11 — NEGATIVE PROMPT SELECTION (Stage C)
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

Stage A may list story-specific negatives; Stage C adds only those relevant to THIS scene.

--------------------------------------------------------------------------------
SHARED §12 — LOCKED CHARACTER LIBRARY
--------------------------------------------------------------------------------

§12.1 PURPOSE
Some recurring characters have an authoritative, locked visual description
maintained outside the story file in a character library. When such a
character appears in the FULL_STORY, every stage MUST use the library
description verbatim instead of re-inferring face, build, hair, beard,
glasses, headwear, clothing, posture, expression, or lighting from scratch.
This guarantees identity continuity across re-runs of the same story,
across different stories that share characters, and as the story keeps
being edited.

§12.2 INPUT SOURCE
The library is supplied through the CHARACTER_LIBRARY input slot in PART 3
of this stage file. The user pastes the latest library text there before
sending. The slot may be empty, missing, or set to NONE — in that case,
this section is inert and all character descriptions come from inference
per SHARED §3 and §5.

§12.3 LIBRARY FORMAT
The library is plain text containing zero or more character blocks. Each
block has the following shape (lines of equals signs are separators):

   ================================================================================
   <CHARACTER_ID> — Character (<context label>)
   ================================================================================
   MATCH ALIASES — PIPELINE ONLY, NEVER COPY TO IMAGE PROMPT:
   <one source name, role phrase, alias, or pronoun-chain label per line>

   LOCKED CHARACTER ANCHOR — COPY VERBATIM EVERY TIME:
   <verbatim character-only visual description body>

   NEGATIVE IDENTITY FIREWALL:
   <optional visual traits that belong to other characters and must not bleed in>
   <... continues until the next equals separator or end-of-file ...>

Parsing rules:
- A block STARTS at a header line of the form
     <CHARACTER_ID> — Character (<context label>)
  with an equals separator line immediately above and immediately below.
- The <CHARACTER_ID> is the neutral matching identifier (e.g. CHAR_HOME_01,
  CHAR_PM_01, CHAR_NSA_01). Prefer stable neutral IDs over real public names.
  It is treated as pipeline plumbing — see §12.7 for name-rule interaction.
- A block may include "MATCH ALIASES — PIPELINE ONLY, NEVER COPY TO IMAGE
  PROMPT:" followed by source names, role phrases, aliases, titles, or
  continuity labels. These aliases are allowed only for matching and lock
  propagation. They MUST NOT appear in image prompts or other user-facing
  visual text.
- The block BODY is everything between the closing equals separator under
  the header and the next equals separator (or end-of-file). The body is
  verbatim authoritative text.
- The <context label> in parentheses (e.g. "interior", "combat", "field")
  is a variant marker; ignore it if the character has only one block.
- Blank lines at the start or end of a block body are trimmed when copying.
- Blocks separated by blank lines without equals separators are NOT valid
  blocks — only properly bracketed headers count.

§12.4 MATCHING RULE
For each recurring character detected in the FULL_STORY:
1. Build a normalised match string: uppercase, trim, collapse whitespace
   runs to a single space, drop honorifics (SHRI, SHRIMATI, MR, MRS, DR,
   PM, HM, NSA) at the start or end. Apply the same normalisation to each
   library CHARACTER_ID and each line under MATCH ALIASES.
2. A match exists when the normalised story name / role phrase and a
   normalised MATCH ALIAS are equal, OR when one is a whole-word substring
   of the other (so an alias can match a longer source form). If no alias
   section exists, the neutral CHARACTER_ID may be used as a fallback match.
   Prefer the longest matching alias — full name or precise role beats
   surname-only, title-only, or broad role.
3. If multiple library blocks match (e.g. variants by context label),
   prefer the block whose context label best fits the dominant scene type
   for that character in the story. If no preference can be determined,
   use the first match in document order and note the choice.
4. If no library match exists for a story character, fall back to
   inference per SHARED §3 and §5. Do NOT fabricate a library block, do
   NOT pretend a partial match is a match.

§12.5 VERBATIM LOCK (CROSS-STAGE)
When a story character matches a library block, the matched block body is
the LOCKED VISUAL DESCRIPTION for that character. Across all stages:
- Treat the body as authoritative for face, build, age, hair, beard,
  glasses, headwear, clothing baseline, posture language, baseline
  expression, baseline lighting, and any other visual attribute it
  specifies.
- Do NOT paraphrase, summarise, shorten, expand, translate, reorder
  lines, or "improve" the locked body.
- Do NOT re-infer attributes that the locked body already specifies.
  The library wins over SHARED §3 and SHARED §5 inference for that
  specific character.
- Verbatim library anchors are never overridden by SHARED §2. Copy the anchor
  verbatim; apply scene action and readable lighting around it. If the anchor
  contains menace or lighting wording that conflicts with §2 behaviour-based
  rules, note the conflict for human review — do not drop or rewrite the anchor.

§12.6 SCOPE OF VERBATIM COPY PER STAGE
- Stage A: record the match in the RECURRING CHARACTER ROSTER by tagging
  the row LIBRARY-LOCKED with the matched key, AND list the match in the
  CHARACTER LIBRARY MATCHES section of the STORY CONFIG BLOCK. Do NOT
  copy the body into the STORY CONFIG BLOCK — keep the block compact;
  the body lives only in the library.
- Stage B: forward LIBRARY-LOCKED roster entries unchanged. Where a
  scene's main subject or supporting subject corresponds to a
  LIBRARY-LOCKED character, tag that subject with the locked key so
  Stage C can resolve it.
- Stage C: when a LIBRARY-LOCKED character is the MAIN SUBJECT or a
  SUPPORTING SUBJECT of a scene, the IMAGE PROMPT character description
  for that character MUST be the verbatim locked body, dropped into the
  appropriate Foreground or Midground slot for that camera scale.
  Scene-specific staging (current action, gaze direction, hand placement
  for the moment, props, immediate background) is added AROUND the
  locked block — never injected inside it, never used to overwrite it.

§12.7 NAME RULE INTERACTION (SHARED §4)
The library CHARACTER_ID should normally be a neutral ID, not a real
public-figure name. SHARED §4 still applies. The CHARACTER_ID is permitted
ONLY in three places:
  (a) inside the CHARACTER_LIBRARY input slot (it is source data, not
      output);
  (b) inside the "Library reference key:" field of the RECURRING
      CHARACTER ROSTER and the CHARACTER LIBRARY MATCHES section of the
      STORY CONFIG BLOCK (pipeline plumbing, not narrative output);
  (c) inside Stage B's per-scene "Library lock:" tag for matched
      subjects (also pipeline plumbing, never user-facing).
The CHARACTER_ID MUST NOT appear anywhere else in any stage's output. In
particular, it must not appear in scene context labels, IMAGE PROMPT
prefixes, IMAGE PROMPT bodies, NEGATIVE sections, DIGEN MOTION PROMPT,
metadata, or breakdown notes outside "Hindi line:".

MATCH ALIASES may contain real names or source labels so the pipeline can
lock the correct character. They are input-only matching data and MUST NOT
be copied to the STORY CONFIG BLOCK except indirectly through the neutral
CHARACTER_ID.

Library block BODIES are expected to use archetype phrasing (e.g.
"a senior Indian home minister figure"). Use them as-is. If a library
body somehow contains a real name in its body text, strip the name down
to an archetype before copying — bodies must remain §4-compliant after
copy.

§12.8 LIBRARY UPDATES
The library is expected to grow and change over time. On every fresh run:
- Re-read the CHARACTER_LIBRARY slot from scratch — it is authoritative
  for THIS run.
- Do not memoise, cache, or reuse a previous run's locked body if the
  current library text differs.
- New library entries added between runs simply produce new matches on
  the next run; old entries removed cease to lock.
- Edits to a library body are applied verbatim on the next run with no
  reconciliation against any prior output.

§12.9 STORY-NAME INFERENCE WHEN THE STORY DOESN'T USE THE NAME
Stories often reference public figures by role only ("the home minister",
"the prime minister", "the NSA") and by name only inside Hindi lines.
For matching purposes, it is acceptable to match a library CHARACTER_ID to a
character whose role and archetype clearly correspond, EVEN IF the name
itself only appears inside "Hindi line:" or a clearly equivalent role
phrase, provided:
- the role + era + country combination is unambiguous (e.g. "Home
  Minister of India in 2019" → the one matching home-ministerial character ID);
- the library has exactly one block whose archetype matches that role.
If ambiguity exists, do NOT match — fall back to inference. Record
ambiguous candidates in CHARACTER LIBRARY MATCHES under "Ambiguous /
unmatched" so the user can disambiguate or extend the library.


================================================================================
PART 2 — STAGE A: STORY CONFIG ENGINE
================================================================================

ROLE
You are a Master Prompt Configuration Engine for cinematic storyboard
production. Read the provided story and output ONLY a STORY CONFIG BLOCK.

DO NOT
- generate scenes;
- summarize the story;
- add commentary;
- output anything before or after the STORY CONFIG BLOCK.

CONTINUITY vs VISUAL DEFAULTS (apply while analyzing)
- Lock factual continuity: era, geography, architecture, cast identity, library
  matches, hostile-actor presence (yes/no), public figures, sensitive exclusions.
- Set adaptable visual defaults per story: dominant times of day, seasonal light,
  regional palette families, typical environments — grounded in the FULL_STORY,
  not generic crime/investigation styling.
- When hostile actors are absent, output N/A for every HOSTILE ACTOR VISUAL PROFILE
  field and do not recommend threat lighting for ordinary scenes.

WHAT TO ANALYZE

A. STORY IDENTITY
Title or working title; language of narration (Hindi / English / Mixed);
genre (documentary / investigative / social / historical / political /
thriller / biographical / crime / military / cyber / intelligence); tone
(serious / emotional / tense / celebratory / tragic / neutral / patriotic /
satirical / suspenseful); estimated total scenes at 5 seconds each.

B. ERA AND GEOGRAPHY
Primary time period (year/decade); primary country; primary states/
provinces/regions; primary cities/neighborhoods; secondary locations;
setting type (urban / rural / suburban / border / institutional / mixed).

C. ENVIRONMENT TYPES
List every physical space the story visits — e.g. cyber room, street,
domestic interior, courtroom, office, forest, hospital, parliament,
bazaar, prison, airport, railway station, police station, intelligence
room, border zone, media newsroom, militant safehouse, dim rented room,
mountain road, old market lane.

D. ARCHITECTURE AND INFRASTRUCTURE
Region-specific architecture style; street fabric (narrow lanes, highways,
markets, colonies, official compounds, rural roads, border roads, tribal
roads, bazaars, old-city lanes, checkpoints, etc.); interior style
(furniture, walls, doors, windows, lighting, files, screens, maps,
noticeboards, old fans, cheap plastic chairs, worn tables, metal
cupboards, religious calendars only if non-readable and story-safe);
era-accurate vehicles, devices, phones, computers, uniforms, furniture,
public-space details; what to avoid for the era/geography.

E. RECURRING CHARACTERS AND GROUPS

E.0 LIBRARY MATCHING (apply BEFORE inference — see SHARED §12)
Before describing any recurring character from inference, scan the
CHARACTER_LIBRARY input slot. For each character detected in the
FULL_STORY (whether named in Hindi lines or referred to by role per
SHARED §12.9), apply the matching rule in SHARED §12.4. If a match
exists, mark that character as LIBRARY-LOCKED and record the matched
CHARACTER_ID. The locked body itself is NOT copied into the STORY CONFIG BLOCK
(see SHARED §12.6) — only the lock status and neutral ID are recorded.
LIBRARY-LOCKED characters skip inference for visual fields and have
those fields filled with the marker
   "FROM LIBRARY (see locked body under character ID '<CHARACTER_ID>')"
in the roster. Non-locked characters proceed to inference per SHARED
§3 and §5 as before.

E.1 INFERENCE (for non-locked characters)

E.1a DEFINITE CASTING (non-locked characters)
When recording roster fields, choose ONE supported value per trait. Do not output
alternative grooming, clothing, hair colour, age bands, or footwear options in roster
fields. Distinguish source facts from creative casting choices. Mark uncertain historical
facts honestly; do not present invented ages or identities as established.

For each recurring character/group not LIBRARY-LOCKED, record per
SHARED §3 and §5:
name (only if in source); origin/region; ethno-regional visual context;
role category; ideological/organisational context; age range; gender;
profession/role; class; build; face shape; skin tone; hair; facial hair;
headwear; glasses; clothing baseline; posture language; emotional baseline;
visual coding rule; do-not-misclassify rule; continuity rule; whether
public-figure protection applies (SHARED §4).

F. HOSTILE ACTOR DETECTION (conditional — if absent, all fields N/A)
Per SHARED §2 when present. If hostile actors exist, record behaviour-based profile:
groups; origin/region; ethno-regional visual context; threat role;
religious-political context; visual severity (low/medium/high); face and
expression; grooming; headwear; clothing baseline; posture language;
lighting rule; continuity rule; portrayal-avoid rule; civilian-separation
rule.

G. PUBLIC FIGURES (SHARED §4)
List each by archetype only — never store real names in any output field.

H. CLOTHING AND CLASS MARKERS
Civilian baseline; official baseline; regional details; hostile actor
clothing baseline; militant clothing baseline; class/status markers;
era-accurate rules; what to avoid.

I. COLOR SCRIPT DEFAULT
Recommend setting-specific palettes grounded in THIS story — e.g. monsoon
grey-green exteriors; warm afternoon domestic amber; cool institutional
fluorescent; dusty highway ochre; festival saffron and marigold; night market
sodium and shop-front tungsten. Daylight scenes should stay naturally lit with
local colour, not globally desaturated. If hostile actors appear, define their
palette separately as muted, shadowed, dusty, or dimly lit — never warm, heroic,
glamorous, or devotional. If hostile actors are absent, mark hostile palette
fields N/A.

J. LIGHTING BEHAVIOR
Daylight; night; interior; institutional; cyber/screen; hostile actor;
militant; primary anchor lighting rule.

K. SENSITIVE CONTENT ADDITIONS
Story-specific exclusions on top of SHARED §11. Examples per story:
no weapons visible; no readable religious text; no platform logos; no
propaganda imagery; no explicit violence; no gore; no readable financial
records; no readable official documents; no party symbols.

L. ATMOSPHERE FAMILY
Dominant + secondary atmosphere (e.g. surveillance pressure; domestic
vulnerability; institutional patience; street-level fear; courtroom
gravity; political tension; investigative focus; patriotic resolve;
quiet betrayal; hostile secrecy; radical manipulation; threat-network
pressure; militant paranoia).

M. DOMINANT SHOT ENVIRONMENT
What environment appears most frequently and the recommended default shot
type for it (per SHARED §9).

N. PRIMARY VISUAL ANCHOR GUIDANCE
What dominates the frame across most scenes — derive from THIS story's actual
beats (e.g. face, crowd, landscape, building facade, vehicle, market stall,
family doorway, podium, map, document, phone, checkpoint, aircraft, border
road, hospital bed). Do NOT default to desk-monitor-evidence-board templates
when the narration supports richer anchors. Explain how abstract lines should
be anchored in story-specific places and objects. If hostile actors appear,
indicate whether the anchor should be threatening posture, guarded expression,
suspicious phone use, tense group attention, or hidden device — otherwise N/A.

O. SPECIAL HANDLING NEEDS
Many abstract lines; multiple simultaneous locations; crowd scenes; time
jumps; flashback structure; unreliable narrator moments; public figure
sensitivity; disputed claims; cyber elements; sensitive religious/
political content; hostile actor severity; radicalisation without
propaganda imagery; militant styling without stereotyping civilians.

P. 5-SECOND PACING GUIDANCE
Average Hindi line length per scene; when to merge adjacent short lines;
when to split; which lines should remain standalone; how to avoid
over-segmentation.

OUTPUT FORMAT (STAGE A) — output exactly this block and nothing else

================================================================================
STORY CONFIG BLOCK
================================================================================

STORY IDENTITY
Title: [working or inferred title]
Language: [Hindi / English / Mixed Hindi-English]
Genre: [genre]
Tone: [tone]
Estimated total scenes at 5 seconds each: [number]

ERA AND GEOGRAPHY
Primary era: [year or decade]
Primary country: [country]
Primary regions: [list]
Primary cities: [list]
Secondary locations: [list or NONE]
Setting type: [urban / rural / suburban / border / institutional / mixed]

ENVIRONMENT TYPES
[list every physical space type, one per line]

ARCHITECTURE AND INFRASTRUCTURE LOCK
Architecture style: [description]
Street and exterior fabric: [description]
Interior design language: [description]
Era-accurate objects and technology: [description]
Vehicles and transport: [description]
Avoid: [wrong era/geography/infrastructure details to avoid]

RECURRING CHARACTER ROSTER
[For each recurring character or group, output the full block:]
Character or group: [archetype label, role label, or group label — never a real public figure name]
Library lock status: [LIBRARY-LOCKED / NOT LOCKED]
Library reference key: [matched neutral CHARACTER_ID from CHARACTER_LIBRARY, or N/A]
Origin / region: [country + region/province/city if known]
Ethno-regional visual context: [per SHARED §3.2]
Role category: [per SHARED §3.3]
Ideological or organisational context: [per SHARED §3.4 or NONE]
Age range: [range or mixed | FROM LIBRARY if locked]
Gender: [gender or mixed | FROM LIBRARY if locked]
Profession / role: [profession or narrative function]
Class: [lower / lower-middle / middle / upper-middle / upper / mixed / official / militant network]
Build: [slim / average / heavyset / mixed | FROM LIBRARY if locked]
Face / appearance: [face shape, regional appearance, visible age cues | "FROM LIBRARY (see locked body under character ID '<CHARACTER_ID>')" if locked]
Skin tone: [description | FROM LIBRARY if locked]
Hair: [description | FROM LIBRARY if locked]
Facial hair: [description | FROM LIBRARY if locked]
Headwear: [skullcap / prayer cap / pakol / turban / scarf / none / mixed / N/A | FROM LIBRARY if locked]
Glasses: [yes with description / no / mixed | FROM LIBRARY if locked]
Clothing baseline: [description | FROM LIBRARY if locked]
Posture language: [description | FROM LIBRARY if locked]
Emotional baseline: [description | FROM LIBRARY if locked]
Visual coding rule: [how origin + role + ideology affects appearance]
Do-not-misclassify rule: [what must not be wrongly inferred]
Continuity rule: [what must remain stable across scenes; for LIBRARY-LOCKED characters this is "library body is verbatim authoritative across all scenes per SHARED §12.5"]
Public figure requiring protection: [yes / no]
Archetype description if public figure: [description or N/A | for LIBRARY-LOCKED public figures: "see locked body under character ID '<CHARACTER_ID>'"]

CHARACTER LIBRARY MATCHES
Library supplied: [yes / no — yes if CHARACTER_LIBRARY input slot was non-empty]
Library matches: [for each LIBRARY-LOCKED character in the roster, one line of the form
                  "<archetype label> -> <CHARACTER_ID>  (context label: <label or none>)"
                  or NONE if there are no matches]
Ambiguous / unmatched: [list any candidate matches that were rejected for ambiguity per SHARED §12.4 step 3 or §12.9, one per line, or NONE]
Cross-stage instruction: All LIBRARY-LOCKED characters listed above MUST be resolved by Stage B and Stage C through the same CHARACTER_LIBRARY input slot, using the neutral CHARACTER_ID recorded here. Stage C MUST copy the locked character anchor into the IMAGE PROMPT character description for every scene where a LIBRARY-LOCKED character is the main or supporting subject, but MUST NOT print the CHARACTER_ID itself in the IMAGE PROMPT, NEGATIVE section, or DIGEN MOTION PROMPT (SHARED §12.6 / §12.7).

HOSTILE ACTOR VISUAL PROFILE
Hostile actors present: [yes / no]
Hostile actor groups: [list groups or NONE]
Detected origin / region: [country + region/province/city or NONE]
Ethno-regional visual context: [per SHARED §3.2 or NONE]
Threat role: [terrorist / extremist / radical handler / recruiter / propagandist / criminal operative / suspect / hostile network / NONE]
Religious-political context: [per SHARED §3.4 or NONE]
Visual severity level: [low / medium / high]
Face and expression: [description or N/A]
Grooming: [description or N/A]
Headwear: [description or N/A]
Clothing baseline: [description or N/A]
Posture language: [description or N/A]
Lighting rule: [description or N/A]
Continuity rule: [description or N/A]
Avoid portrayal: [list or N/A]
Civilian separation rule: [per SHARED §2.6]

PUBLIC FIGURE SENSITIVITY
Public figures present: [yes / no]
Public figure handling: [list each as role-based archetype, or NONE]

CLOTHING AND CLASS MARKERS
Civilian clothing: [description]
Official clothing: [description]
Regional clothing: [description]
Hostile actor clothing: [description or N/A]
Pakistan-based Islamist militant clothing: [description or N/A]
Class/status markers: [description]
Avoid clothing: [description]

COLOR SCRIPT DEFAULT
Primary palette: [description]
Cyber or institutional scenes: [color mood]
Domestic scenes: [color mood]
Exterior scenes: [color mood]
Hostile actor scenes: [color mood or N/A]
Pakistan-based Islamist militant scenes: [color mood or N/A]
Night scenes: [color mood]

LIGHTING BEHAVIOR
Daylight: [description]
Night: [description]
Interior: [description]
Institutional: [description]
Cyber/screen light: [description or N/A]
Hostile actor lighting: [description or N/A]
Pakistan-based Islamist militant lighting: [description or N/A]
Primary anchor lighting rule: [description]

STORY-SPECIFIC NEGATIVE PROMPT ADDITIONS
[list every story-specific exclusion, one per line; these stack on top of SHARED §11]

ATMOSPHERE FAMILY
Dominant atmosphere: [description]
Secondary atmosphere: [description]

DOMINANT SHOT ENVIRONMENT
Most frequent environment: [description]
Recommended default shot type: [from SHARED §9]

PRIMARY VISUAL ANCHOR GUIDANCE
Dominant anchor types: [description]
How to stage anchors: [description]
What should not compete with the anchor: [description]

SPECIAL HANDLING NEEDS
[list unique visual challenges, one per line, or NONE]

ABSTRACT LINE TRANSLATION GUIDANCE
[3 to 5 concrete examples specific to this story showing how to ground likely abstract lines physically — see SHARED §7]

HOSTILE ACTOR TRANSLATION GUIDANCE
[If hostile actors appear, 3 to 5 examples of story-supported action/concealment beats — not appearance menace. Otherwise N/A.]

ORIGIN-BASED CHARACTER APPLICATION GUIDANCE
[3 to 5 examples of how origin + region + role affect ordinary appearance coding; civilians stay neutral; suspects may look ordinary — see SHARED §3.]

5-SECOND PACING GUIDANCE
Average Hindi line length per scene: [range]
Merge adjacent lines when: [rule]
Split lines when: [rule]
Standalone lines: [what kind of lines should stay alone]
Over-segmentation warning: [story-specific warning]

UNIVERSAL PROMPT INSERTION INSTRUCTION
This STORY CONFIG BLOCK overrides all story-specific defaults during Stages B
and C. Stages B and C must read this block as authoritative for era,
geography, character roster, hostile profile, public-figure handling, color
script, lighting, anchor guidance, atmosphere, and pacing.

================================================================================
END OF STORY CONFIG BLOCK
================================================================================


================================================================================
PART 3 — INPUT SLOTS (fill these before sending)
================================================================================

FULL_STORY:
{Paste the full Hindi / Hinglish / English story here.}

OPTIONAL_GENRE_OR_TONE:
{Paste optional genre or tone hint here, or leave blank.}

CHARACTER_LIBRARY:
{Paste the full contents of the locked character library here (e.g. the
contents of character.txt). Each block must follow the SHARED §12.3
format: a line of equals signs, a header line "<CHARACTER_ID> — Character
(<context label>)", another line of equals signs, optional MATCH ALIASES
for source-name / role matching, then a LOCKED CHARACTER ANCHOR visual
description until the next block or end-of-input. Leave blank or
write NONE if no library is supplied — Stage A will then fall back to
inference per SHARED §3 and §5.}


================================================================================
PART 4 — TASK
================================================================================

Read the FULL_STORY above (and OPTIONAL_GENRE_OR_TONE if provided).
Read the CHARACTER_LIBRARY slot and apply SHARED §12 (locked character
library) for any character whose key matches a story character per
SHARED §12.4 / §12.9.
Apply PART 1 (SHARED LIBRARY) wherever referenced.
Execute PART 2 (STAGE A SPEC).
Output ONLY the STORY CONFIG BLOCK in the exact format defined in PART 2.
Do NOT output any other text, commentary, or explanation.

================================================================================
END OF STAGE A FILE
================================================================================
