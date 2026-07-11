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
empty stage-like backgrounds.

--------------------------------------------------------------------------------
SHARED §2 — HOSTILE ACTOR VISUAL MENACE (MANDATORY)
--------------------------------------------------------------------------------

A "hostile actor" means: terrorist, extremist, radical handler, hostile
recruiter, radical propagandist, violent conspirator, terror commander,
operative, handler, suspect linked to hostile activity, criminal operative,
or hostile-network member — as identified by the source story or the
STORY CONFIG BLOCK.

§2.1 ABSOLUTE MANDATE
When a hostile actor appears in main subject or supporting subject, the
image MUST visually communicate menace clearly enough that any viewer reads
the figure as a hardened militant / extremist / threatening operative within
1–2 seconds of glancing at the frame. A hostile actor that looks like an
ordinary passer-by, a regular working-class man, a neutral civilian, a
gentle uncle, a humble teacher, or a calm stranger is a FAILED prompt.

The hostile figure must be visually DIFFERENT from ordinary civilians of
the same region — not because of religion or ethnicity, but because of
hardened expression, weathered face, rough grooming, dark/sunken eyes,
heavy beard discipline, posture, lighting, and costume choices that mark
them as operationally dangerous.

§2.2 MANDATORY VISUAL MARKERS (must include — not optional)

When describing a hostile actor in any IMAGE PROMPT, the description MUST
include AT LEAST one item from EACH of the four groups below. Combinations
are required; isolated single cues are insufficient.

GROUP A — FACE & GROOMING (must include at least 2)
- heavy long beard, dark or greying with age, untrimmed or rough-edged
- weathered sun-worn skin with deep lines or hollow cheeks
- hardened face with tense jaw and tight mouth
- dark sunken or shadowed eyes; sharp narrowed gaze
- rough stubble where a full beard is not contextually appropriate
- thick brow shadow over deep-set eyes
- a face that has seen violence, hardship, or operational stress

GROUP B — EXPRESSION & GAZE (must include at least 1)
- cold predatory stare directed at a phone, file, person, or off-frame point
- narrowed eyes with controlled menace
- guarded sideways glance toward a doorway or exit
- expressionless mask hiding internal calculation (NOT blank-neutral; must
  read as deliberate stillness, not absence of feeling)
- low-lidded watchful gaze with weight behind it
- jaw locked in suppressed aggression

GROUP C — BODY LANGUAGE & POSTURE (must include at least 1)
- shoulders hunched forward in secretive concentration
- body angled away from the dominant light source so half the face stays
  in shadow
- one hand gripping a phone, weapon stock, file, or device too tightly
- the other hand near a pocket, bag, doorway, or hidden compartment
- controlled stillness with weight forward — coiled, not relaxed
- watchful posture near corners, walls, exits, or shutter edges
- subtle protective stance shielding a device, screen, or paper

GROUP D — COSTUME & SETTING-LINKED CUES (must include at least 1)
- conservative dark or muted shalwar kameez (Pakistan/Pashtun context)
- loose kurta with rough waistcoat or shawl over it
- skullcap, prayer cap, pakol, turban, or wrapped head covering where the
  story geography supports it
- worn dusty sandals or scuffed practical footwear
- earth-tone or dust-toned fabric showing real wear and travel
- militant-context accessories: cloth bag, rolled paper, hidden phone,
  cheap smartphone clutched low
- harsh side or back lighting that throws half the face into deep shadow
  while edge-lighting the beard and brow

If any of A/B/C/D is missing, the prompt has not satisfied §2 and must be
strengthened before output.

§2.3 NEVER DESCRIBE HOSTILE ACTORS AS
gentle • calm in a peaceful way • soft-faced • innocent • kind-looking •
warm • graceful • saintly • pure • humble • harmless • charming • heroic •
stylish • attractive in a beauty sense • charismatic • emotionally
sympathetic • noble • ordinary • regular • neutral civilian • clean-shaven
modern man (unless story explicitly says disguise) • a normal passer-by •
a working-class everyman • an unremarkable face in the crowd •
documentary-flat • blank • generic.

§2.4 RADICALISATION / PROPAGANDA / RECRUITMENT / CYBER-MANIPULATION
Show manipulation through: posture, screen framing, closed rooms, hidden
phones, coded communication, aggressive hand gestures, secretive group
attention, suspicious device use, tense silence, low-bulb lighting.
Do NOT make propagandists look like calm teachers, gentle spiritual guides,
innocent speakers, harmless content creators, or warm community elders.
A radical propagandist must look hardened, manipulative, controlling, or
predatory — not warm or paternal.
Avoid readable religious text; readable extremist slogans; explicit
propaganda symbols; extremist logos; graphic gore; glorified violence.
Communicate danger through behaviour, setting, lighting, and atmosphere —
not through gore.

§2.5 CONTINUITY
Hostile actors must remain visually tense, secretive, hardened, and morally
threatening across all scenes UNLESS the story explicitly shows disguise or
deception. Same hardened face structure, same beard discipline, same
clothing family, same posture language, same lack of warmth in every scene.

§2.6 CIVILIAN SEPARATION RULE (UNCHANGED — STILL MANDATORY)
Ordinary civilians from the same religion / region / ethnicity / clothing
family as hostile actors must REMAIN ordinary civilians — never inherit
hostile coding because of beard, skullcap, prayer cap, shalwar kameez,
hijab, mosque background, or religious clothing alone. Apply hostile coding
ONLY when the story or STORY CONFIG BLOCK clearly identifies the person as
a hostile actor.

The §2 mandate intensifies coding for IDENTIFIED hostile actors. It does
NOT spread that coding to ordinary civilians who happen to share a region,
religion, or clothing style. The two rules work together, not against each
other.

§2.7 LIGHTING RULE FOR HOSTILE ACTORS
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
neutrality.

§2.8 FIRST-GLANCE READABILITY MANDATE
A hostile-actor frame passes only if a viewer scrolling past at normal
speed can read the figure as a hardened militant / terrorist / extremist /
operative within 1–2 seconds — based on silhouette, beard, expression,
posture, lighting, and costume alone, BEFORE reading any context detail in
the background.

If the figure could plausibly be mistaken for a routine working-class man,
a calm religious teacher, a neighborhood shopkeeper, a generic uncle, or a
friendly passer-by, the prompt has FAILED §2.8 and must be strengthened
before output.

Concrete test: cover the background in your mind. Look only at the figure.
Does the silhouette + face + grooming + posture + lighting still read as
"this person is operationally dangerous"? If not, strengthen.

§2.9 CINEMATIC INTENSITY PERMISSION (within grounded realism)
Hostile actors may — and should — be rendered with heightened cinematic
expressiveness:
- strong directional chiaroscuro lighting on the face;
- exaggerated silhouette readability (heavy beard, distinctive headwear,
  layered fabric outline);
- compressed depth pulling the figure forward against a darker background;
- micro-expression intensity (visible jaw tension, breath held, controlled
  rage, quiet menace) instead of neutral inert face;
- grounded but emotionally charged staging.

This is NOT a permit for cartoon villainy, fantasy stylisation, surrealism,
or visual exaggeration that breaks documentary realism. It IS a permit for
the cinematic intensity of films like Sardar Udham, Article 15, The Family
Man, Mumbai Diaries, Tehran, Munich, or Zero Dark Thirty — grounded but
visually striking and emotionally readable.

When in doubt: more menace, not less. The story-safety risk is softness,
not severity.

§2.10 HOSTILE STAGING TEMPLATE BLOCK (mandatory verbatim insertion)
When a hostile actor is the main subject or co-subject of a scene, Stage C
MUST open the Foreground section with a description block built on this
template. The block must appear as the FIRST descriptive content inside
Foreground (before any environmental detail, before any object detail,
before any other character). Image models weight earlier tokens more
heavily — burying the hostile description mid-prompt is the primary cause
of softening.

TEMPLATE (fill the bracketed slots from the scene; never omit any slot):

  "{role-archetype} figure, {age range} years old, {ethno-regional descriptor},
   {build} build, {face descriptor including weathered/hardened cues},
   {beard descriptor — heavy/long/dark/greying as appropriate to age},
   {headwear if context supports — skullcap / pakol / turban / wrapped scarf
   / none-with-rough-hair}, {costume — shalwar kameez / kurta + waistcoat /
   muted regional clothing, with wear and dust}, {expression — hardened /
   narrowed / cold / predatory / guarded — never neutral, never gentle},
   {gaze direction and intensity}, {posture — hunched / coiled / angled
   away from light / shoulders forward}, {hand placement — gripping device /
   near pocket / shielding object / resting on file}, {lighting effect on
   face — half-shadow / phone-glow / harsh side / single bulb under-light}"

EXAMPLE FILLED:
"A hardened Pakistan-based Islamist militant figure, late thirties to early
forties, Pakistani Pashtun with weathered sun-worn skin and sharp cheekbones,
medium build, hollow-cheeked face with deep brow shadow and tense jaw, heavy
dark untrimmed beard reaching mid-chest, brown wool pakol pulled low over
the forehead, loose dust-toned shalwar kameez with a rough grey-brown
waistcoat over it, narrowed cold eyes fixed on a cheap smartphone in his
left hand, fingers gripping the device too tightly, right hand resting near
a cloth shoulder bag at his hip, shoulders hunched forward in secretive
concentration, body angled so the harsh tube light from upper-left throws
the right side of his face into deep dirty shadow while edge-lighting the
beard and brow"

This block must NEVER be skipped, NEVER softened, NEVER replaced with a
shorter neutral description, and NEVER pushed to Midground or Background.

§2.11 SOFTENING DETECTION & REJECTION
Before finalising any IMAGE PROMPT containing a hostile actor, scan the
generated text for softening markers. Strike and rewrite if any of these
appear in the hostile-actor description:
- "ordinary", "regular", "normal", "everyday" applied to the hostile figure
- "calm", "peaceful", "gentle", "soft", "warm", "kind", "humble"
- "neutral expression", "blank face", "relaxed posture", "pleasant"
- "well-groomed", "clean-cut", "modern", "fashionable", "stylish"
  (unless story explicitly states disguise)
- "smiling", "friendly", "approachable", "open posture"
- "spiritual", "saintly", "devotional", "reverent" (for hostile figures)
- "documentary-flat", "balanced lighting", "even illumination"
- any descriptor that, removed from context, could equally describe a
  shopkeeper, schoolteacher, or family man.

If any of the above are detected in the hostile-actor description block,
the description has failed and must be regenerated using §2.2 mandatory
markers and §2.10 staging template.

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

§3.6 PAKISTAN-BASED ISLAMIST MILITANT VISUAL PROFILE (MANDATORY MINIMUMS)
Apply only when the story explicitly identifies the actor as a Pakistan-based
Islamist militant, terror commander, extremist recruiter, LeT-linked figure,
JeM-linked figure, Taliban-style militant, jihadist handler, radical preacher,
or militant network operative.
Do NOT describe them merely as "Muslim civilians."
Do NOT make ordinary Muslim civilians look threatening (SHARED §2.6).

When this profile applies, the IMAGE PROMPT description MUST include ALL of
the following — these are not optional cues, they are mandatory minimums:

REQUIRED (must be present):
1. Heavy long beard, dark or greying with age, untrimmed and rough-edged
   (a clean-shaven or trimmed-modern look is FORBIDDEN unless the story
   explicitly states disguise).
2. Conservative regional clothing — shalwar kameez, loose kurta, with rough
   waistcoat or shawl where regionally appropriate, in muted earth tones
   with visible dust and wear.
3. Hardened weathered face — sun-worn skin, deep brow shadow, hollow or
   sharp cheek lines, tense jaw, narrowed or sunken eyes.
4. Visible posture menace — guarded, hunched, watchful, or angled-away-
   from-light stance. Never an open, relaxed, friendly, or balanced stance.
5. Directional menace lighting — half-shadow on the face, harsh side or
   under-light, weak phone glow, or single low bulb (SHARED §2.7). Never
   soft balanced light.

REQUIRED WHERE GEOGRAPHY SUPPORTS:
- skullcap, prayer cap, pakol, turban, or wrapped head covering
- worn dusty sandals or scuffed practical footwear

ABSOLUTELY FORBIDDEN:
- modern stylish influencer look
- clean-shaven soft modern face (unless story says disguise)
- fashionable hero jacket, polished urban styling
- glamorous villain styling
- warm devotional glow, saintly religious-teacher look
- innocent civilian framing
- balanced studio lighting on the face
- friendly smile, open posture, gentle expression
- readable religious text, readable extremist slogans, extremist logos
- glorified weapons display, graphic gore

KPK / tribal belt / Waziristan / Peshawar outskirts / Afghan-border context:
Pashtun/north-western Pakistan cues — long beard; pakol or turban where
appropriate; loose shalwar kameez; rough waistcoat; dusty sandals; weathered
skin; sharp cheekbones; sun-worn face; guarded body language.

Punjab / urban Pakistan extremist networks: shalwar kameez; waistcoat; long
beard; skullcap where appropriate; conservative grooming; muted colours;
controlled suspicious posture.

Avoid for any of the above: modern stylish influencer look; clean-shaven soft
face unless story states disguise; fashionable hero jacket; glamorous villain
styling; warm devotional glow; saintly religious-teacher look; innocent
civilian framing; readable religious text; readable extremist slogans;
extremist logos; glorified weapons display; graphic gore.

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

§5.4 HOSTILE RECURRING CHARACTERS
Maintain the same threatening visual identity across scenes: same hardened
face structure; same guarded eye behaviour; same rough grooming family;
same clothing logic; same suspicious posture language; same lack of warmth
or heroism.

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
Ground them through: tense faces, suspicious devices, dim rooms, hidden
phones, marked maps, closed shutters, coded notes without readable text,
officers reviewing evidence, hostile actors watching screens with guarded
body language. Do NOT create peaceful spiritual symbolism or soft emotional
portraits of hostile actors.

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

§8.3 HOSTILE-SCENE STRENGTHENING
If a scene includes a hostile actor, do NOT use soft labels. Strengthen the
label with grounded threat language. Examples:

  Soft (forbidden)              →   Stronger (preferred)
  Young Man Watches Video       →   Hostile Recruiter Watches Screen
  Religious Speaker Talks       →   Radical Handler Controls Room
  Group Listening Quietly       →   Suspicious Group Receives Message
  Man Uses Phone                →   Threat Network Studies Phone
  Calm Speaker Addresses Room   →   Hostile Propagandist Shapes Narrative
  Gentle Man In Room            →   Criminal Handler Waits In Shadow

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
SHARED §11 — UNIVERSAL NEGATIVES (sensitive content)
--------------------------------------------------------------------------------

Always exclude in IMAGE PROMPT NEGATIVE section (Stage C). Stage A may add
story-specific negatives on top of these.

Universal:
photorealism; ultra realism; 3D render; CGI; ray tracing; global
illumination; glossy surfaces; HDR realism; lens flare; blur; depth of field;
bloom; neon colors; fantasy smoke; exaggerated caricature; text overlay;
watermark; logo; readable labels; readable document text; readable insignia;
modern futuristic infrastructure not supported by era.

When hostile actors are present, ALWAYS include these strong anti-soft
exclusions (these are the highest-priority negatives for hostile scenes):
gentle face; innocent expression; warm smile; friendly smile; saintly glow;
heroic pose; glamorous styling; cute look; sympathetic victim framing;
soft devotional lighting; polished influencer appearance; fashionable
villain glamour; harmless appearance; noble martyr framing; romanticised
extremist look; ordinary man; regular passer-by; neutral civilian look;
working-class everyman; unremarkable face in the crowd; documentary-flat
hostile actor; blank neutral face; relaxed posture; open friendly stance;
balanced studio lighting on the face; even soft daylight on the face;
clean-shaven soft modern face (unless story states disguise); trimmed
fashionable beard; humble teacher look; calm spiritual guide look; gentle
uncle look; pleasant approachable expression; warm community elder framing;
modern stylish jacket; polished urban styling on militant.

When Islamist militant context is present, additionally exclude:
readable religious text; readable propaganda slogans; extremist logos;
extremist flags; ordinary Muslim civilians portrayed as threatening;
religion-only threat coding; ethnic stereotyping; clean-shaven soft
militant if config requires heavy long beard; gentle religious-teacher look
for confirmed hostile extremist; saintly preacher framing for hostile
recruiter; warm devotional glow on hostile figure; soft balanced light on
militant face; modern fashionable dress on confirmed militant.

Common scene-specific exclusions (add when relevant):
visible weapon if it should not appear; beard / clean-shaven if continuity
requires; suit / tie if inappropriate; hero pose if inappropriate; crowd if
scene should feel empty; smiling expression if mood is serious; readable app
names; readable chat text; readable website names; readable phone numbers;
readable maps; readable official seals; real political party symbols;
explicit public figure labels; graphic gore; explicit brutality; blood
splatter unless specifically required.

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
- The lock does NOT override SHARED §2 (hostile actor mandate) if the
  story identifies the character as hostile. SHARED §2 still applies on
  top, and the locked body is only used if it is consistent with §2;
  otherwise flag the conflict (this should be rare — the library is
  expected to be self-consistent with each character's role).

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
For each recurring character/group not LIBRARY-LOCKED, record per
SHARED §3 and §5:
name (only if in source); origin/region; ethno-regional visual context;
role category; ideological/organisational context; age range; gender;
profession/role; class; build; face shape; skin tone; hair; facial hair;
headwear; glasses; clothing baseline; posture language; emotional baseline;
visual coding rule; do-not-misclassify rule; continuity rule; whether
public-figure protection applies (SHARED §4).

F. HOSTILE ACTOR DETECTION
Per SHARED §2 and §3.6/§3.7. If hostile actors exist, record:
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
Recommend a default palette per story tone — e.g. cold blue institutional;
warm amber domestic; desaturated grey tension; muted earth tones; night
sodium yellow; dusty daylight; restrained cyber screen glow. If hostile
actors appear, define their palette as muted, shadowed, dusty, desaturated,
or dimly lit — never warm, heroic, glamorous, or devotional.

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
What dominates the frame across most scenes — e.g. face, phone, laptop
screen, evidence folder, map, checkpoint, officer's hand, family doorway,
empty street, press camera, courtroom bench, aircraft, border road,
hospital bed, long-bearded militant figure, shadowed phone-lit face,
closed shopfront, suspicious group posture. Explain how abstract lines
should be anchored. If hostile actors appear, indicate whether the anchor
should be threatening posture, shadowed face, suspicious phone use, tense
group attention, hidden device, evidence screen, or network map.

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
[If hostile actors appear, 3 to 5 concrete examples showing threat physically without gore, propaganda, or glorification — see SHARED §2. Otherwise N/A.]

ORIGIN-BASED CHARACTER APPLICATION GUIDANCE
[3 to 5 concrete examples of how origin + region + role + ideology should affect appearance, applying militant styling only to identified hostile actors and keeping civilians neutral — see SHARED §3.]

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
