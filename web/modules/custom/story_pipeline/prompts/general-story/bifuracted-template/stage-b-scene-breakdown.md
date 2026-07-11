 
================================================================================
STORYBOARD PIPELINE — STAGE B: CONTEXT-AWARE SCENE BREAKDOWN ENGINE
Derived from STORYBOARD MASTER PROMPT — UNIFIED v2.4 — GENERAL SAFE 5-SECOND AUDIO FIT + CHARACTER LOCK AUDIT
================================================================================

HOW TO USE THIS FILE WITH CHATGPT
1. First, run Stage A and save its STORY CONFIG BLOCK output.
2. Open a new ChatGPT chat for Stage B.
3. Copy this ENTIRE file and paste it as your first message.
4. At the very bottom, fill in the input slots:
      STORY_CONFIG_BLOCK:  <-- paste Stage A output
      FULL_STORY:          <-- paste the full Hindi / Hinglish / English story
      CHARACTER_LIBRARY:   <-- paste locked character library, or write NONE
5. Send.
6. ChatGPT must return ONLY the LOCKED SCENE BREAKDOWN.
7. Save that LOCKED SCENE BREAKDOWN — it is the input to Stage C.

PIPELINE POSITION
   Story
      ↓
   Stage A — Story Config Engine
      ↓
   >>> Stage B — Context-Aware Scene Breakdown Engine <<<
      ↓
   Stage C — Image + Motion Prompt Engine


================================================================================
PART 0 — DISPATCHER
================================================================================

ACTIVE STAGE: B

Execute ONLY Stage B.

Your job:
- Read STORY_CONFIG_BLOCK.
- Read FULL_STORY.
- Read CHARACTER_LIBRARY if supplied.
- Segment the story into locked 5-second visual beats.
- Preserve the Hindi line exactly.
- Add enough context metadata so Stage C can generate images that understand:
  current story scenario, surrounding environment, continuity, emotional state,
  story arc, recurring characters, and concrete visual details.
- Attach Library lock tags wherever the scene subject matches a locked character.

Do NOT:
- generate image prompts;
- generate motion prompts;
- explain your reasoning;
- add commentary before or after the breakdown;
- summarize the story;
- rewrite Hindi lines;
- remove story lines;
- add new narration;
- output tables.


Automation / continuation safety:
- If the pipeline sends CONTEXT OVERLAP, PREVIOUS SCENE RANGE, AUTHORITATIVE
  CONTINUATION, or similar recap rails inside FULL_STORY, treat overlap as
  already-filmed context only.
- Do not emit new Scene entries exclusively for overlap/recap text.
- Continue strict chronological narration from the authoritative new body.
- Never insert extra LOCKED SCENE BREAKDOWN headings, excerpt titles, or “END
  OF ...” ribbons between Scene blocks; automation may merge slices into one
  file.


================================================================================
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
text overlay; poster layout; split-screen collage.


================================================================================
PART 2 — PUBLIC FIGURE AND NAME RULE
================================================================================

Applies to politicians, ministers, advisors, military leaders, intelligence
chiefs, public officials, public commentators, and other recognizable real
public persons.

ABSOLUTE RULE:
Real public-figure names may appear ONLY inside Hindi line if the original
source line already contains them.

Outside Hindi line, never write:
- real public figure names;
- initials that clearly identify them;
- exact likeness instructions;
- readable nameplates;
- readable party symbols;
- readable official insignia;
- readable logos.

Outside Hindi line, convert public figures into role-based archetypes:
- senior national political strategist figure
- senior prime-ministerial figure
- senior home-ministerial figure
- state chief-ministerial figure
- senior party organiser
- national security official
- senior opposition figure
- political analyst
- grassroots worker

Library lock IDs are allowed ONLY in the Library lock field as pipeline
metadata. Do not use library IDs anywhere else.


================================================================================
PART 3 — HOSTILE ACTOR VISUAL MENACE
================================================================================

A hostile actor means:
terrorist, extremist, radical handler, hostile recruiter, radical propagandist,
violent conspirator, terror commander, criminal operative, handler, suspect
linked to hostile activity, hostile network member.

When hostile actors appear:
- context label must carry threat language;
- main subject must identify them as hostile actor / militant / criminal
  operative / radical handler as appropriate;
- surrounding environment must support threat reading;
- do not describe them as gentle, innocent, harmless, ordinary, soft,
  warm, saintly, charming, or neutral.

Civilian separation rule:
Do NOT apply hostile coding only because of religion, ethnicity, country,
beard, skullcap, shalwar kameez, hijab, mosque background, or regional dress.
Only apply hostile coding when the story identifies the person/group as hostile.


================================================================================
PART 4 — CHARACTER CONSISTENCY AND LIBRARY LOCKS
================================================================================

If CHARACTER_LIBRARY is supplied, Stage B must propagate library locks.

Rules:
1. Identify each scene’s main subject and important supporting subjects.
2. Check STORY_CONFIG_BLOCK roster and CHARACTER_LIBRARY.
3. If a subject corresponds to a locked character, add the exact neutral
   character ID from the roster's "Library reference key:" field in:
      Library lock:
4. Multiple IDs are comma-separated.
5. If no locked character appears, write:
      Library lock:
      NONE
6. Do not copy the character library body into the breakdown.
7. Do not paraphrase locked character descriptions.
8. Stage B only carries the neutral character ID. Stage C will resolve the
   full appearance.

Important:
If the story repeatedly refers to a locked character through pronouns,
roles, titles, or indirect references, still attach the correct Library lock.

Example:
Hindi line contains a real name:
“अमित शाह अदालत पहुँचे।”
Metadata outside Hindi line:
Main subject:
senior national political strategist figure entering court pressure

Library lock:
CHAR_HOME_01

Do not write the public figure name in Main subject, Scene context label,
Current story context, Main location, Surrounding environment, Breakdown note,
or anywhere outside Hindi line. The Library lock field should contain only the
neutral character ID from the STORY CONFIG BLOCK, not a real public name.


--------------------------------------------------------------------------------
PART 4A — CRITICAL LIBRARY LOCK ENFORCEMENT
--------------------------------------------------------------------------------

CHARACTER LIBRARY SIZE GUIDELINE:
A well-formed CHARACTER_LIBRARY for any single story should register no more
than 3 locked characters. These 3 should be the most visually recurring and
identity-critical figures (e.g. protagonist, main antagonist, one supporting
lead). All other recurring characters — even important ones — should be handled
via the UNREGISTERED: reference mechanism below, not by expanding the library
indefinitely.

This stage must work with ANY story and ANY supplied character library.

The character library may change from project to project. Do not hard-code any
specific person, public figure, politician, officer, criminal, victim, child,
family member, journalist, analyst, hostile actor, or fictional character.
Instead, detect the available neutral character IDs from the supplied
CHARACTER_LIBRARY and the STORY_CONFIG_BLOCK roster for the current story.

A Library lock ID is pipeline metadata, not an image-prompt name.
Therefore:
- public figure names are still forbidden outside Hindi line;
- real names are still forbidden in Main subject, Current story context,
  Scene context label, Main location, Surrounding environment, Supporting
  visual elements, Camera scale suggestion, Scene function, and Breakdown note;
- but the exact neutral character ID from CHARACTER_LIBRARY / STORY CONFIG
  is allowed and required inside Library lock when that locked character is
  visually present or clearly referenced.

MANDATORY LOCK PROPAGATION:
If a scene visually contains, references, implies, recalls, shows a photograph
of, shows a younger version of, shows an older version of, shows from behind,
shows in silhouette, shows on a screen, shows through a reflection, shows
through a file/photo/news clipping, shows only a hand/face/back/profile, or
describes the actions, emotions, reputation, history, strategy, memory, decision,
or public reaction around any character present in CHARACTER_LIBRARY, the
matching Library lock MUST be added.

Do not write Library lock: NONE when the scene clearly belongs to a locked
character through any of these forms:
- direct name in Hindi line;
- alias, surname, title, role, office, or relationship;
- pronouns such as he, she, they, वह, वे, उनके, उसका, उसका चेहरा, उनकी सोच,
  उनका फैसला, when the surrounding context clearly points to a locked character;
- phrases like protagonist, central figure, central strategist figure, senior
  leader figure, officer figure, investigator figure, criminal figure, child,
  mother, father, friend, victim, witness, handler, recruiter, analyst, or any
  role that the current story config maps to a locked character;
- younger version, older version, flashback version, future version, public
  photo, archive photo, portrait, screen image, memory image, silhouette, or
  symbolic version of a locked character.

If the Hindi line contains a locked character's exact name, alias, title, or
clear role reference, Library lock MUST NOT be NONE.

If the scene's Main subject or Supporting visual elements describe a locked
character even without a real name, Library lock MUST NOT be NONE.

If two or more locked characters appear in the same visual beat, list all IDs:
Library lock:
CHAR_HOME_01, CHAR_PM_01

If a locked character is only present as a background photograph, screen image,
archive clipping, memory figure, silhouette, reflection, or partial body detail,
still add the ID. Stage C will decide foreground/midground/background placement.

GENERIC ARCHETYPE OUTSIDE LOCK FIELD:
Outside Hindi line and Library lock, describe locked public figures and other
recognizable people by role/archetype only.

Examples:
- senior national political strategist figure
- senior home-ministerial figure
- senior prime-ministerial figure
- senior national security strategist figure
- young grassroots organiser
- older business-family patriarch
- middle-aged police investigator
- hostile criminal operative
- worried family member
- teenage student
- local journalist
- political analyst

Do not depend on one fixed archetype. Pick the archetype from the current story,
era, age, role, and scene context.

LOCK FIELD IS NOT OPTIONAL:
When CHARACTER_LIBRARY is supplied and a scene maps to a locked character,
Library lock is required even if:
- the scene is abstract;
- the character appears only symbolically;
- the character is seen from behind;
- the character is younger/older than the main library reference;
- the character is not the main subject but is important to the frame;
- the character appears on a TV screen, newspaper photo, poster, court file,
  old album, archive wall, phone screen, or memory montage;
- the image prompt later must avoid the real name.

ONLY use Library lock: NONE when no locked character is visually present,
directly referenced, indirectly referenced, or contextually implied in that
scene.

--------------------------------------------------------------------------------
PART 4B — STORY-GENERIC CHARACTER MATCHING METHOD
--------------------------------------------------------------------------------

Before emitting each scene, silently perform this matching sequence:

1. Extract all available neutral character IDs from CHARACTER_LIBRARY.
2. Read STORY_CONFIG_BLOCK roster, aliases, public figure mappings, and any
   character-library matches.
3. For the current scene, identify the visible subject(s), implied subject(s),
   supporting subject(s), named subject(s), and pronoun referent(s).
4. Match scene subjects against the current story's library IDs using:
   - exact name in Hindi line;
   - aliases and titles;
   - role mapping from STORY_CONFIG_BLOCK;
   - previous-scene continuity;
   - current story arc;
   - pronoun chain from the last 1–3 scenes;
   - location/context continuity;
   - visual phrases such as younger version, older version, photo, silhouette,
     hand, face, back view, screen image, reflection, or memory.
5. If a match exists, write the matching neutral character ID in Library lock.
6. If multiple matches exist, write all matching IDs in stable story order.

Do not invent new IDs.
Use only IDs that exist in CHARACTER_LIBRARY or are explicitly enumerated as
library-locked in STORY_CONFIG_BLOCK.

If a scene refers to a recurring character but the character is NOT registered
in CHARACTER_LIBRARY, do NOT write NONE. Instead write the raw detected alias
or name from the Hindi line or story context as an unregistered reference:

Library lock:
UNREGISTERED: {detected_name_or_alias}

Examples:
Library lock:
UNREGISTERED: डोभाल

Library lock:
UNREGISTERED: Ajit Doval

Library lock:
UNREGISTERED: Chhota Rajan

This preserves the character reference so it can be retroactively added to
CHARACTER_LIBRARY in a future run. The UNREGISTERED: prefix marks it as
pipeline-detected but not yet formally registered.

Write NONE only when the scene contains NO identifiable recurring character at
all — neither registered nor unregistered.

--------------------------------------------------------------------------------
PART 4C — REQUIRED LOCK AUDIT BEFORE FINAL OUTPUT
--------------------------------------------------------------------------------

Before returning the LOCKED SCENE BREAKDOWN, scan every scene and reject these
failures:

FORBIDDEN FAILURE 1:
Hindi line contains a locked character name, but Library lock is NONE.

FORBIDDEN FAILURE 2:
Current story context, Visual continuity anchor, Main subject, or Supporting
visual elements clearly describe a locked character, but Library lock is NONE.

FORBIDDEN FAILURE 3:
Main subject uses a generic archetype for a character that exists in the
CHARACTER_LIBRARY, but Library lock is NONE.

FORBIDDEN FAILURE 4:
Scene shows a younger/older version, photograph, screen image, reflection,
silhouette, back view, partial hand/face/body detail, archive image, or memory
image of a locked character, but Library lock is NONE.

FORBIDDEN FAILURE 5:
Two locked characters appear in one scene, but only one ID is listed.

FORBIDDEN FAILURE 6:
A public figure real name appears outside Hindi line or outside Library lock.

FORBIDDEN FAILURE 7:
Hindi line contains a name, alias, or clear role reference to a recurring
character that does not exist in CHARACTER_LIBRARY, but Library lock is NONE.
Correct pattern: Library lock: UNREGISTERED: {detected_name_or_alias}
This failure is the most common missed lock. A real name or clear alias in the
Hindi line ALWAYS requires a Library lock entry — either a registered ID or an
UNREGISTERED: reference. NONE is never acceptable when a name is detectable.

If any failure is found, fix the scene before output.

Note: UNREGISTERED: references inside the Library lock field are pipeline
metadata and do not violate the public-figure name rule. Real names are
permitted inside Library lock — registered IDs and UNREGISTERED: aliases are
both valid entries in that field only.

Correct pattern:
Main subject:
senior role-based archetype figure standing under legal and media scrutiny

Library lock:
{MATCHING_CHARACTER_ID}

Incorrect pattern:
Main subject:
senior role-based archetype figure standing under legal and media scrutiny

Library lock:
NONE

The second pattern is wrong whenever the role-based archetype corresponds to a
locked character in this story.


================================================================================
PART 5 — SOURCE TEXT PRESERVATION
================================================================================

The Hindi line field must preserve the original wording exactly.

Allowed:
- segmenting the story into scene units;
- merging adjacent full sentences when they form one visual beat;
- splitting only at valid sentence-level boundaries when one line carries
  multiple visual beats.

Not allowed:
- paraphrasing;
- grammar correction;
- rewriting;
- translation;
- removing words;
- adding new words;
- changing names;
- changing tone;
- changing punctuation unnecessarily.

Every Hindi line must end with:
।  ?  !  or a close quote.

Never output a Hindi line that ends with:
comma, open dash, trailing dash, colon, or incomplete phrase.


================================================================================
PART 6 — CORE OBJECTIVE
================================================================================

Convert FULL_STORY into a LOCKED SCENE BREAKDOWN.

Each scene must represent:
- one 5-second visual beat;
- one visual idea;
- one camera setup;
- one emotional or narrative beat;
- one grounded story-world context.

Stage B is not only a segmentation engine.
Stage B is also the context bridge for Stage C.

The main failure to avoid:
Do not output thin metadata that only says “office”, “room”, “court”,
“political figure”, “map”, or “analysts”.

Stage C needs to understand:
- where we are in the larger story arc;
- what is happening at this exact moment;
- what surrounding environment should be visible;
- what previous or continuing context this scene belongs to;
- which objects, background details, crowd mood, institutional setting,
  domestic setting, battlefield setting, media setting, campaign setting,
  or political setting make the image understandable;
- what this scene does in the narrative: setup, reveal, escalation, reaction,
  decision, consequence, investigation, threat build-up, climax, aftermath,
  transition, or CTA.

The Hindi line gives the narration.
The metadata gives the image-world.


================================================================================
PART 7 — CONTEXT-AWARE METADATA RULE
================================================================================

For every scene, metadata must answer:

1. Current story arc:
   Which larger section of the story are we in?

2. Current story context:
   What is happening in the story at this exact moment?

3. Visual continuity anchor:
   What recurring location, emotional state, strategy thread, investigation
   thread, campaign arc, legal arc, battlefield arc, media arc, or metaphor
   does this scene continue?

4. Surrounding environment:
   What should be visible around the subject?

5. Supporting visual elements:
   What concrete objects/background details make the scene readable?

6. Scene function:
   Why does this scene exist in the story?

Bad metadata:
Main location:
office

Main subject:
political figure

Surrounding environment:
room

Good metadata:
Main location:
2010 Gujarat court corridor under media pressure

Main subject:
senior national political strategist figure standing under legal and media scrutiny

Surrounding environment:
institutional court corridor with waiting reporters, security barricades,
camera flashes, legal file bundles, and tense public attention

Supporting visual elements:
media cameras, court doorway, security barricade, legal folder, muted crowd

Metadata may infer grounded surroundings from:
- STORY_CONFIG_BLOCK;
- previous 1–3 scenes;
- next 1–2 scenes;
- era;
- geography;
- character role;
- emotional situation;
- ongoing story arc.

Metadata must never invent new events or change chronology.


================================================================================
PART 8 — STORY ARC LABELING
================================================================================

Every scene must include:

Current story arc:
{short phrase}

Use grounded arc names suitable to the story.

Examples:
- Opening downfall arc
- Court media pressure arc
- Business-market thinking arc
- Grassroots organisation arc
- Early partnership arc
- Gujarat rise arc
- Legal crisis arc
- Exile and preparation arc
- Uttar Pradesh comeback arc
- Booth machinery arc
- National organisation machine arc
- Controversy and criticism arc
- Home Ministry decision arc
- Kashmir policy arc
- Citizenship debate arc
- Public image debate arc
- Future leadership question arc
- Closing reflection arc

For non-political stories, create equivalent grounded arcs:
- Childhood origin arc
- Investigation begins arc
- Hostile network arc
- Family reaction arc
- Police chase arc
- Courtroom climax arc
- Aftermath arc
- Moral reflection arc

Do not use public figure names in arc labels.


================================================================================
PART 9 — SCENE SEGMENTATION UNIT
================================================================================

A scene is one 5-second visual beat.

The SEGMENTATION UNIT is NOT one source sentence by default. The segmentation
unit is ONE clear visual beat that can be shown as one 5-second image/video
moment with one primary subject, one camera setup, and one emotional or
narrative purpose.

SAFE 5-SECOND AUDIO FIT TARGET — spoken rhythm is authoritative:

HARD CEILING — NON-NEGOTIABLE:
A Hindi line MUST NOT exceed 25 spoken words OR 100 visible characters,
whichever limit is reached first. If a proposed line exceeds either limit,
it MUST be split. There are no exceptions, no "length exception accepted"
workarounds, and no Breakdown note overrides for this ceiling.
Split at the nearest valid sentence-level marker: । ? ! close quote or
a strong full-clause em-dash (—).

- IDEAL RANGE: 8–14 spoken Hindi/Hinglish words. This is the cleanest range
  for 5-second clips and should be the default target.
- FLEX RANGE: 15–18 spoken words. Allow this only when the line is smooth,
  grammatically complete, visually indivisible, and still sounds natural in
  one 5-second narration beat.
- MUST-SPLIT: 19–24 spoken words OR 96–99 visible characters. You MUST split
  unless the entire source clause has no internal punctuation at all (no comma,
  no em-dash, no semicolon). If any internal punctuation exists, split there.
- HARD STOP: 25+ spoken words OR 100+ visible characters. ALWAYS split.
  No exceptions whatsoever. Find the nearest clean split point — never emit
  a line that exceeds this ceiling under any circumstances.
- TRUE FAILURE: any line above the HARD CEILING is invalid output regardless
  of story type, sentence complexity, or narrative context.

5-SECOND AUDIO FIT TEST:
Before finalizing any Hindi line, silently ask:
“Can this exact Hindi line be spoken clearly, naturally, and without rushing in
one 5-second clip?”
- If YES, keep it only if it also satisfies the one-visual-beat mandate.
- If NO and a safe split exists, split it.
- If NO and no preferred split exists, split at a comma as a last resort — a
  comma split is always better than emitting a line above the HARD CEILING.
  A line above the HARD CEILING is never acceptable under any circumstances.

WORD COUNT METHOD:
Count spoken tokens separated by spaces in the Hindi line, including English
words, numerals, names, quoted words, and mixed Hindi-English words. Word count
is the primary audio-fit pacing check.

CHARACTER COUNT METHOD:
Count every visible character in the Hindi line exactly as emitted:
Devanagari letters, matras, spaces, punctuation, numerals, English words,
quotation marks, and dashes. Do not count metadata fields. Character count is
only a readability warning after 95 visible characters, not the main scene rule.

Acceptable short lines:
- 5–6 words only when the line is a true punch/reveal/command/hook.
- Below 5 words only when it is a major standalone punch and cannot merge
  without weakening the beat.

Acceptable longer lines:
- 15–18 words only when smooth, indivisible, and still natural in 5 seconds.
- 19–24 words only after confirming no valid split point exists (no comma,
  no em-dash, no sentence stop inside the clause).
- 25+ words: NEVER ACCEPTABLE. Always split.
- 100+ visible characters: NEVER ACCEPTABLE. Always split.

Do not default to one sentence = one scene.

Adjacent short sentences must merge when they share:
- same location;
- same subject;
- same visual anchor;
- same camera setup;
- same emotional beat;
- same story function;
- no new action;
- no new object focus;
- no location change;
- combined narration still fits the SAFE 5-SECOND AUDIO FIT TARGET.

Do not merge only because the meaning is related.
Merge only when it can be shown in one 5-second shot.

MERGE LIMIT UNDER 5-SECOND AUDIO FIT TARGET:
Mandatory merge patterns still apply, but do NOT merge two complete short
sentences if the combined Hindi line becomes too long for one natural 5-second
beat. If the merged line reaches 19+ words, review for split. If it reaches
25+ words OR 100+ visible characters, split unconditionally — the HARD CEILING
applies to merged lines too, with no exceptions.

MINIMUM-LENGTH MERGE:
Before emitting any scene below ~5–6 words, check:
1. Is it a true standalone punch? If yes, keep it.
2. If not, merge with the immediately adjacent sentence only when the merge
   preserves one location, one subject, one camera setup, and one visual beat.
3. If every neighbour changes location/action/subject/beat, keep the short
   scene. A short clean scene is better than a fused multi-idea scene.


================================================================================
PART 10 — ONE-VISUAL-BEAT MANDATE
================================================================================

Each scene must contain exactly one visual idea.

Split when a line contains:
- two different physical locations;
- two different physical actions;
- setup and payoff;
- cause and effect requiring different camera setups;
- attack and aftermath;
- map planning and field execution;
- speaker emotion plus dialogue;
- dialogue plus listener reaction;
- wide establishing plus close object detail;
- atmosphere plus operational detail;
- court exterior plus newsroom;
- public street plus private interior;
- crowd reaction plus backroom strategy;
- media debate plus field deployment.

Test:
Can this be shown clearly in one 5-second shot with one camera angle and
one primary subject?

If no, split.

But split only at valid sentence-level markers:
।  ?  !  close quote  or a strong full-clause dash.

Prefer not to split on an internal comma. However, when all options above
(।  ?  !  close quote  em-dash  clause marker) are exhausted AND the line
exceeds 25 spoken words or 100 visible characters, a comma split is required.
A line above the HARD CEILING cannot be kept intact — comma split it.

SAFE COMPLETE-UNIT SPLIT LADDER:
When a scene line is above 18 spoken words, above 22 spoken words, or above 95
visible characters, try to split in this exact order:

1. FULL SENTENCE BOUNDARY:
   Split at `।`, `?`, `!`, or a close quote when both resulting scenes remain
   complete and preserve chronology.

2. DIALOGUE / REACTION BOUNDARY:
   Split speaker emotion, spoken dialogue, listener reaction, and resulting
   action into separate beats when the source provides a safe boundary.

3. EM-DASH COMPLETE-CLAUSE BOUNDARY:
   Split at `—` only when both sides are complete spoken units and neither side
   becomes a dash-stub.

4. MAJOR CLAUSE BOUNDARY:
   Split at strong clause markers such as `कि`, `जिसकी`, `जो`, `जब`, `लेकिन`,
   `मगर`, `और`, `क्योंकि`, `जहाँ`, `वहाँ` ONLY when both resulting parts remain
   understandable complete units and preserve exact source wording.

5. COMMA BOUNDARY (last resort):
   When all options 1–4 are exhausted and the line still exceeds 25 spoken
   words or 100 visible characters, split at the strongest comma boundary
   where both sides have at least 4 words and neither side ends mid-clause
   with a trailing comma. Write:
   Breakdown note: Comma-boundary split — no sentence terminator or clause
   marker available; split at comma to respect the HARD CEILING.

   There is no "Length exception accepted" path. A line above the HARD
   CEILING is invalid output. Always find a split point.

NO-BROKEN-SCENE RULE:
Never split just to satisfy length if the result ends with a comma, trailing
em-dash, open quote, half clause, dangling modifier, or unfinished thought.
Never split inside participial / adverbial chains (`-करके`, `-कर`, `-ते हुए`,
`-ती हुई`, `-होते हुए`, `-लेकर`) when they modify one main verb.
Never split inside a list, parallel descriptor chain, or appositive if all
parts belong to one camera setup.
Never produce mechanically trimmed excerpts such as incomplete phrases that
sound like the sentence will continue.

NO COMMA-STUB RULE:
A scene's Hindi line MUST end with a sentence terminator: `।`, `?`, `!`, or a
close quote. It MUST NEVER end with a comma, a trailing em-dash, an open quote,
or any non-terminator. If a split creates a line ending with comma or dash, the
split is invalid and must be re-merged or moved to a safer boundary.

SENTENCE BOUNDARY AND PIPE RULE:
Detect boundaries using: `।`, `.`, `?`, `!`, close quote, or long dash only
when it separates a full clause.

For `|`:
- Treat `|` as a strong preferred split/review marker in the source text.
- Split at `|` when both sides carry different beats, actions, subjects,
  locations, contexts, or camera setups.
- Keep both sides together only when they clearly belong to the same one
  5-second visual beat and combined narration still fits the audio target.
- Never preserve `|` by creating broken fragments. Each resulting Hindi line
  must still be complete and must end with a valid terminator.
- If `|` separates two complete narration units, prefer separate scenes unless
  the second side is only a direct clarification/gloss of the first.

MULTI-SENTENCE HARD SPLIT REVIEW — 2+ FULL STOPS:
If a proposed Hindi line contains TWO OR MORE full Hindi sentence stops (`।`),
strongly review it for splitting. Do not split automatically, but split if any
next sentence introduces:
- a new time reference or backstory layer;
- a new person or relationship;
- a new physical action;
- a new location or implied camera setup;
- a new cause/effect detail;
- a new emotional reaction;
- a new investigation clue or object focus;
- a new story arc or timeline shift.

Example that MUST split:
“ये करीब सात महीने पहले की बात है। स्टेफीना की एक सबसे करीबी दोस्त थी। उस दोस्त के बॉयफ्रेंड की एक बाइक एक्सीडेंट में मौत हो गई थी।”
RIGHT:
Scene A = “ये करीब सात महीने पहले की बात है।”
Scene B = “स्टेफीना की एक सबसे करीबी दोस्त थी।”
Scene C = “उस दोस्त के बॉयफ्रेंड की एक बाइक एक्सीडेंट में मौत हो गई थी।”
Reason: time setup → friend introduction → boyfriend death backstory are three
different visual/narration beats.

3-SENTENCE SCENE RESTRICTION:
Do NOT keep 3 complete sentences in one scene unless ALL are true:
- all 3 are individually short;
- all 3 share the same location, same subject, same visual anchor, same
  emotional beat, and same camera setup;
- all 3 belong to the same frozen visual moment;
- none introduces a new object, action, person, relationship, backstory layer,
  clue, or tighter focus;
- combined narration still fits a natural 5-second spoken beat.

Allowed exception:
Three very short atmosphere/restatement sentences may remain one scene if they
all describe the exact same frozen visual frame.

ESTABLISHING VS DETAIL — MUST SPLIT:
Do not merge an establishing setup beat with a detailed interior/action beat.
If line A establishes time, place, silence, exterior mood, room-level setup,
institutional pressure, emotional emptiness, or environmental stillness, and
line B introduces specific people, screens, files, phones, maps, weapons,
vehicles, doors, documents, radios, laptops, monitored video, active operation,
or a tighter object focus, split them.

Correct pattern:
Scene A = mood / location / atmosphere.
Scene B = people / object / screen / file / phone / map / action detail.

This rule prevents confusing Stage C images that combine a wide establishing
shot and close operational detail in the same frame.


================================================================================
PART 11 — MERGE RULES
================================================================================

Merge adjacent sentences when all are true:
- same physical location;
- same main subject or same visual anchor;
- same emotional beat;
- same story function;
- same camera scale;
- no new key object;
- no new action;
- no new location;
- no shift from atmosphere to detail;
- no shift from setup to payoff;
- no public exterior/private interior jump;
- combined line still feels like one 5-second beat.

Mandatory merge patterns:
1. Date stamp + place stamp.
2. Time stamp + sky / light / atmosphere.
3. Identity setup + identity reveal.
4. Paired rhetorical questions.
5. Setup + clarification.
6. Two or three short atmosphere sentences.
7. Statement + paraphrase.
8. Unit-change / rotation chain.
9. Gear list + intent.
10. Negation + affirmation.
11. Atmosphere + emotional framing.
12. Outro / CTA fragments.
13. Short abstract line + its immediate clarification.
14. Public reaction pair: supporters vs critics on same issue.
15. Repeated contrast pair: “X यह देखता था। Y वह देखता था.”
16. Role ladder fragments when they form one career-transition montage,
    unless each role change needs a clearly different location and frame.

Examples:
“मकसद पूरा हो चुका था। मिशन कामयाब रहा।”
→ one scene.

“समर्थकों ने इसे ऐतिहासिक निर्णय कहा। विरोधियों ने इसे लोकतंत्र पर प्रश्न बताया।”
→ one scene.

“Comment में अपनी राय जरूर बताइए। अगर आपको यह कहानी पसंद आई हो, तो video को like जरूर करिए...”
→ one CTA scene.

Do not leave CTA fragments as separate scenes unless each has a distinct
visual purpose.

ECHO / TRANSLATION / GLOSS MERGE RULE:
When a sentence only translates, echoes, paraphrases, restates, or explains the
IMMEDIATELY preceding sentence, the two MUST be one scene if the combined line
still fits the audio target. An echo/gloss line is not a separate visual beat.

This includes:
- English quote + Hindi meaning;
- regional word + Hindi explanation;
- short statement + immediate paraphrase;
- repeated emotional statement with no new visual idea;
- slogan/motto + narrator explanation;
- question + immediate restated answer when the visual frame remains the same.

Examples:
“No Man Left Behind। कोई साथी पीछे नहीं छूटेगा।”
→ one scene.

“मकसद पूरा हो चुका था। मिशन कामयाब रहा।”
→ one scene.

Test for echo:
If removing the second sentence does not remove a new visual event, location,
subject, or action, then the second sentence is likely an echo/gloss and should
merge with the previous scene.

ABSTRACT CLARIFICATION MERGE:
A short abstract sentence and its immediate clarification should merge when both
can be represented by one physical anchor, such as a file, map, screen, empty
room, closed door, or symbolic object. Do not merge abstract commentary with
concrete operational detail if the camera setup must change.

PUBLIC REACTION PAIR MERGE:
Supporters/critics, public/private opinion, or two sides of the same debate may
merge into one scene only when they are about the same issue and can be shown as
one debate/reaction frame. Split if the two sides require different locations,
new characters, or different camera setups.

ROLE-LADDER FRAGMENT MERGE:
Career or status ladder fragments may merge into one montage-style beat only
when they describe one continuous identity transition. Split when each role
requires a distinct location, era, or image-world.


================================================================================
PART 12 — SPLIT RULES
================================================================================

Split when any of these change:
- location;
- time period;
- physical action;
- main subject;
- camera scale;
- object of focus;
- story arc;
- emotional beat;
- speaker;
- listener reaction;
- public scene vs private scene;
- courtroom vs newsroom;
- political rally vs campaign backroom;
- map analysis vs field execution;
- policy archive vs public reaction;
- media allegation vs legal consequence.

Do not split:
- participial chains;
- list clauses;
- parallel descriptors;
- appositive clauses;
- same subject doing micro-actions in same frame;
- same metaphor continuing in same scene.

Never produce comma-stub fragments.


STANDALONE PUNCH DISCIPLINE:
A short Hindi line below ~5–6 words may stand alone ONLY when it is a clear,
quotable, beat-defining moment. It must be one of:
- major reveal;
- major warning;
- short command or order;
- turning-point dialogue line;
- strong rhetorical question;
- chapter-opening hook;
- climax beat;
- one-line foreshadow or beat-shift hook.

Not standalone punches:
- translation/gloss lines;
- fragments of a longer thought;
- generic descriptive phrases;
- tiny atmosphere fragments that continue the same visual frame;
- partial clauses before/after comma or dash.

If it is not a true punch, merge with an adjacent same-beat sentence only when
one-visual-beat and audio-fit rules remain satisfied.

HARD SPLIT OVERRIDE:
Short connected units MUST still split when any of these change between them:
- physical location;
- inside vs outside;
- public street vs private interior;
- city view vs room view;
- one character group vs another;
- officials vs civilians;
- public speech vs private strategy;
- active outdoor deployment vs indoor reaction;
- establishing beat vs detailed action;
- silence/mood beat vs people/screens/documents/phones/maps;
- combining would force split-screen, collage, cross-section, or impossible
  multi-location image.

Length-driven merging never overrides the one-visual-beat mandate.


================================================================================
PART 13 — WITHIN-SENTENCE COHESION
================================================================================

Keep one sentence as one scene when it has:
- internal commas;
- participial chains like करके, कर, होते हुए, लेकर, देखते हुए;
- list of objects;
- repeated clauses describing same room/scene;
- metaphor clauses that share one anchor;
- same subject and one final main verb.

Example:
“वह उन कमरों में मौजूद रहते थे जहाँ फैसले लिए जाते थे, जहाँ चुनावी रणनीति बनती थी, जहाँ सत्ता की दिशा तय होती थी।”
→ one scene.

Example:
“उसमें जातीय समीकरण थे, स्थानीय नाराज़गियाँ थीं, कार्यकर्ताओं की ताकत थी, बूथ की मशीनरी थी...”
→ one scene if it is one layered map/table visual.

Do not split these into comma-based fragments.


WITHIN-SENTENCE SPLIT TRIGGERS — exceptional only:
A single source sentence may be split only when it clearly carries two or more
visual ideas and a safe complete-unit boundary exists. Apply only when one of
these triggers fires clearly:
- time stamp + distinct following action;
- trigger + payoff with camera shift;
- two physical locations;
- two physical actions by different subjects;
- speaker emotion description + actual dialogue;
- dialogue + listener reaction;
- attack/action + aftermath with time ellipsis;
- map/plan + field execution;
- wide establishing + close object detail.

If none of these triggers fires clearly, keep the sentence as one scene even if
it contains commas, dashes, or modifiers.

WITHIN-SENTENCE COHESION — when NOT to split:
Keep one sentence as one scene when it has:
1. Participial/adverbial chain ending in one main verb.
2. Parallel descriptors sharing one camera setup.
3. List with final verb.
4. Appositive or embedded clarification inside one visual idea.
5. Same subject doing connected micro-actions in one frozen moment.
6. Introductory clause + main statement on the same subject and frame.

Do not split on internal commas. Most internal commas support one complete
Hindi thought rather than scene boundaries.


================================================================================
PART 14 — DIALOGUE RULE
================================================================================

One dialogue scene should contain:
- one speaker’s one decisive line;
- brief attribution if already attached;
- immediate translation/gloss if it restates the quote.

Split:
- speaker emotion from actual dialogue;
- speaker A line from speaker B reply;
- dialogue from listener reaction;
- dialogue from resulting decision/action.

Echo/translation/gloss must merge with the line it explains.


================================================================================
PART 15 — ABSTRACT AND METAPHOR HANDLING
================================================================================

Abstract lines must be grounded in a physical visual anchor.

Bad:
Main location:
dark corridor

Main subject:
concept of power

Good:
Main location:
closed strategy room with campaign files and state maps

Main subject:
silent political calculation represented through booth maps, files, and restrained posture

For metaphors:
- do not create impossible split-world scenes;
- do not combine court corridor + stock market desk as one physical location;
- keep the real story-world location;
- explain the metaphor in Current story context or Scene function.

Bad:
Main location:
court corridor and market metaphor desk

Good:
Main location:
2010 Gujarat court corridor under media pressure

Current story context:
The market metaphor is applied to the political fall, showing the central
figure reading panic as temporary rather than final.


================================================================================
PART 16 — LOCATION SPECIFICITY RULE
================================================================================

Never use generic locations when the story supports specificity.

Weak:
office
room
court
street
map
stage
strategy room
media room

Strong:
2010 Gujarat court exterior under media pressure
1990s Gujarat grassroots party office
Gujarati business-family home interior
local campaign lane with poster wall
Uttar Pradesh election command room during 2014 campaign
booth-level campaign workspace with voter lists
national organisational war room
Home Ministry institutional corridor after 2019 mandate
Parliament chamber during major policy proposal
Kashmir security street under restrictions
closed national strategy table with state maps and files
neutral documentary outro desk with research files

Main location should carry:
- era or year if important;
- geography if important;
- institutional type if important;
- mood if important;
- story phase if useful.


================================================================================
PART 17 — SUPPORTING VISUAL ELEMENTS RULE
================================================================================

Every scene must include:

Supporting visual elements:
{2–5 concrete visual elements}

These should help Stage C produce a clear frame.

Examples:
- media cameras
- court doorway
- legal folder
- security barricade
- muted crowd
- stacked policy files
- district map
- booth voter lists
- handwritten notes
- tea glasses
- wall clock
- silent aides
- rally photograph
- empty microphone
- closed wooden door
- map pins without readable labels
- archive documents without readable text
- television screens with unreadable graphics
- police barricades
- dim corridor lighting

Avoid:
- readable text;
- logos;
- party symbols;
- nameplates;
- exact slogans;
- unnecessary clutter;
- split-screen objects from different locations.

Use NONE only when truly unnecessary.


================================================================================
PART 18 — VISUAL BEAT TYPE VOCABULARY
================================================================================

Choose exactly one:

Establishing atmosphere
Operational detail
Character reaction
Dialogue turning point
Investigation analysis
Digital evidence
Domestic reaction
Street tension
Closed-room decision
Field movement
Raid preparation
Device seizure
Forensic review
Network mapping
Consequence beat
Emotional punch
Climax beat
Aftermath beat
Abstract commentary visualized physically

Use carefully:
- Reporters speaking outside court = Consequence beat or Establishing atmosphere.
- Historical documents/policy archive = Investigation analysis or Abstract commentary.
- Voter maps/booth lists = Network mapping.
- Personal facial restraint = Character reaction.
- Major decision room = Closed-room decision.
- Final reflective metaphor = Abstract commentary visualized physically.
- CTA = Aftermath beat.


================================================================================
PART 19 — CAMERA SCALE VOCABULARY
================================================================================

Choose exactly one:

Wide establishing
Medium-wide environmental
Medium character beat
Tight object detail
Over-shoulder analysis
Doorway interior view
Elevated room view
Elevated street view
Close reaction frame
Evidence-table view

Do not use the same scale repeatedly without need.
Do not choose close reaction frame for scenes that require spatial context.
Do not choose wide establishing for scenes that are about a file, phone, map,
face, or hand.


================================================================================
PART 20 — SCENE FUNCTION VOCABULARY
================================================================================

Choose one concise function:

setup
reveal
escalation
reaction
decision
consequence
transition
investigation
threat build-up
climax
aftermath
CTA

Use:
- setup for opening context.
- reveal for identity/status reversal.
- escalation for pressure increasing.
- reaction for emotional/public response.
- decision for official or strategic choice.
- consequence for result/impact.
- transition for time/arc shift.
- investigation for analysis or evidence.
- threat build-up for hostile actor escalation.
- climax for payoff.
- aftermath for closing consequences.
- CTA for audience prompts.


================================================================================
PART 20A — MID-STORY CTA PLACEMENT RULE
================================================================================

A mid-story CTA is a brief opinion-prompt scene inserted at a natural pause
in the narrative — typically at a revelation, decision moment, controversy, or
moral question — where the viewer naturally has a reaction to share.

BUDGET RULE:
- A 12-minute story (≈ 144 scenes at 5 seconds each) must have AT MOST 3 CTA
  scenes in total, INCLUDING the final outro CTA.
- Ideal placement: one CTA roughly every 5 minutes of narration.
  Approximate scene landmarks:
    · CTA 1 — around scene 55–65   (≈ 5-minute mark)
    · CTA 2 — around scene 110–125 (≈ 10-minute mark)
    · CTA 3 — final scene(s) of the story (end outro CTA)
- For shorter stories scale proportionally; never exceed 3 CTAs regardless
  of length.

PLACEMENT TRIGGER:
Place a mid-story CTA ONLY when ALL of the following are true:
1. The story has just revealed a key fact, decision, twist, or moral dilemma.
2. A natural brief pause in the narrative exists at that point.
3. The Hindi line genuinely invites viewer reaction (a question to the audience
   or a direct comment prompt — e.g. "आप इस बारे में क्या सोचते हैं?
   Comment में जरूर बताइए।").
4. The placement falls inside the ≈ 5-minute window for that CTA slot.

Do NOT insert a mid-story CTA:
- In the middle of an action sequence, chase, or climax.
- Immediately before or after another CTA (minimum gap ≈ 4 minutes / 48 scenes).
- Just to fill the 5-minute slot if no genuine opinion moment exists at that
  point — shift the CTA to the nearest natural pause within ±10 scenes.

FORMAT FOR MID-STORY CTA SCENE:
- Merge all opinion-prompt fragments into ONE scene (same merge rule as outro).
- Scene function:   CTA
- Visual beat type: Aftermath beat
- Camera scale:     Medium character beat  (or Wide establishing for group)
- Main location:    documentary neutral space, or the current story location
                    with a slight compositional pause cue
- Hindi line:       must end with a question or direct comment invite.
- Breakdown note:   "Mid-story CTA at ≈ {N}-minute mark; opinion moment after
                    {brief description of preceding revelation}."

EXAMPLE:
Hindi line:
अब आप बताइए — क्या यह फैसला सही था? Comment में अपनी राय जरूर दीजिए।

Scene function: CTA
Visual beat type: Aftermath beat
Breakdown note: Mid-story CTA at ≈ 5-minute mark; opinion moment after the
                cabinet decision reveal.


================================================================================
PART 21 — SCENE COUNT BUDGET
================================================================================

Estimate narration duration:

W = approximate word count of FULL_STORY.
D = W / 180.

Ideal scene count:
D × 12.

Hard cap:
D × 14.

If emitted scenes exceed hard cap:
- merge mandatory merge candidates;
- merge CTA fragments;
- merge abstract clarification pairs;
- merge repeated contrast pairs;
- merge paraphrases;
- merge short atmosphere chains;
- merge role-ladder fragments when they are one montage idea.

Do not solve count by fusing two locations/actions into one scene.

Average words per scene should usually be around 12–16.
If average is below 11, you are over-segmenting.


SCENE COUNT SAFETY WITH AUDIO FIT:
The scene count budget must never be solved by creating long overloaded scenes.
When count is high, first merge only true same-beat candidates:
- date + place;
- time + atmosphere;
- statement + paraphrase;
- abstract line + clarification;
- CTA fragments;
- repeated contrast pairs;
- same-frame atmosphere chains;
- same-issue public reaction pairs;
- role-ladder fragments that form one montage.

Do NOT reduce count by merging different locations, different actions, speaker
+ listener reaction, wide establishing + close object detail, or mood + active
operation.

If average words per scene are below 11, over-segmentation is likely. Recheck
short scenes against mandatory merge patterns and standalone punch discipline.
If many scenes exceed 18 words, under-segmentation is likely. Recheck long
scenes against safe complete-unit split ladder and multi-sentence hard split
review.


================================================================================
PART 22 — FINAL PASS CHECKS
================================================================================

Before output, run these checks:

1. Terminator check:
Every Hindi line ends with । ? ! or close quote.

2. No comma-stub check:
No Hindi line ends with comma or trailing dash.

3. One-visual-beat check:
Every scene can be shown in one 5-second shot.

4. Context check:
Every scene has strong Current story context and Surrounding environment.

5. Generic metadata check:
No generic “office”, “room”, “court”, “map”, “street” if story supports specificity.

6. Supporting elements check:
Every scene has useful concrete visual elements.

7. Library lock check:
Any locked recurring figure appearing by name, alias, role, title, pronoun,
younger/older version, photograph, silhouette, screen image, reflection, hand,
face, back view, memory image, archive image, symbolic representation, or
supporting/background presence gets the correct Library lock.
Library lock: NONE is forbidden when the scene maps to any supplied
CHARACTER_LIBRARY ID.
If the character is not in CHARACTER_LIBRARY but is named or clearly aliased
in the Hindi line or story context, write UNREGISTERED: {alias} — never NONE.

8. Public figure name check:
No real public figure name outside Hindi line except Library lock.

9. CTA merge check:
Outro fragments are merged into fewer scenes unless they have distinct visual beats.
Mid-story CTA scenes must also be fully merged — no split opinion-prompt fragments.
Total CTA scenes (mid-story + outro) must NOT exceed 3 for a 12-minute story.
Each mid-story CTA must be placed at a genuine opinion moment (revelation,
decision, moral question) within ≈ 5-minute spacing windows (see PART 20A).
Mid-story CTAs inside action sequences, climaxes, or within 48 scenes of
another CTA are invalid and must be removed or repositioned.

10. Metaphor check:
Metaphors are grounded in real scene-world, not impossible split-location composites.

11. Scene count check:
Emitted count must be within D × 14 hard cap.


12. Safe audio-fit check:
Every Hindi line should ideally be 8–14 spoken words. 15–18 is allowed only
when smooth and indivisible. 19+ must have a split review. 22+ needs a rare
exception note.

13. 95-character warning check:
Any Hindi line above 95 visible characters must be reviewed for safe split.

14. Multi-sentence check:
Any Hindi line with 2+ `।` marks must be reviewed. Keep together only when all
sentences share the same frozen visual beat and still fit 5 seconds.

15. Pipe separator check:
Any source `|` marker must be reviewed as a preferred split point unless both
sides are one visual beat.

16. Broken-fragment check:
No scene may end mid-thought, mid-quote, mid-participial chain, or mid-comma
chain.

17. Establishing/detail check:
Atmosphere/setup scenes must not be fused with screens, files, phones, maps,
officers, documents, weapons, vehicles, or active operational details.

18. Echo/gloss check:
Translation, paraphrase, repeated statement, or gloss lines must not become
standalone scenes unless they introduce a genuinely new visual beat.

19. Standalone punch check:
Very short scenes must be true reveal/command/hook/climax/rhetorical punch
beats. Otherwise merge if a clean same-beat neighbour exists.

20. Continuation/overlap check:
If FULL_STORY contains CONTEXT OVERLAP or recap text from a previous chunk,
treat it as already-filmed context and do not emit duplicate scenes from it.
Continue only from the authoritative new body.

21. Output-cleanliness check:
Do not insert extra headings, excerpt titles, separators, “END OF” ribbons, or
commentary between scene blocks. The pipeline may merge multiple output slices.

22. On-screen text overlay check:
Every scene must include both On-screen location and On-screen name fields.
On-screen location must be a real named place (not an archetype phrase) or NONE.
On-screen name must be the real person/operation/event name (not an archetype
phrase) or NONE. Do not repeat the same name in consecutive scenes — write NONE
after the first introduction. These fields must never contain image-prompt
archetype phrases like “senior home-ministerial figure”.


================================================================================
PART 22A — ON-SCREEN TEXT OVERLAY FIELDS
================================================================================

Two fields — On-screen location and On-screen name — are for the video editor,
not for image generation. They identify real named entities the editor can
display as text overlays (lower-thirds, title cards, location stamps) to help
the viewer orient themselves.

ON-SCREEN LOCATION:
- Write the REAL named location exactly as a viewer would recognise it.
  Examples: "Chandni Chowk, Delhi" · "Kandahar Airport, Afghanistan" ·
  "Parliament Street, New Delhi" · "Srinagar, Kashmir" · "ISI Headquarters, Islamabad"
- Use the form: {Place Name}, {City/Region/Country} — keep it short (≤ 5 words).
- Write NONE when:
  · No specific named real-world location is mentioned in the Hindi line or
    immediately inferable from current story context.
  · The scene is abstract, metaphorical, or has no identifiable geography.
  · The location is already established in the previous scene and has not changed.

ON-SCREEN NAME:
- Write the real name that a viewer would need to see on screen to understand
  who or what is being referred to. This may be:
  · A real person's name:    "Ajit Doval" · "Masood Azhar" · "Atal Bihari Vajpayee"
  · An operation name:       "Operation Safal" · "Operation Blue Star"
  · An event/incident name:  "IC-814 Hijack" · "Parliament Attack 2001"
  · An organisation name:    "RAW" · "ISI" · "NIA"
- Write NONE when no named person, operation, event, or organisation is
  introduced or first referenced in this scene.
- Only write a name when the Hindi line itself first introduces or emphasises
  that name. Do NOT repeat it in every subsequent scene — write NONE once the
  name has already been displayed.

IMPORTANT — these fields do NOT override the public-figure name rule for image
generation. On-screen name may contain real names because it is a video-editor
metadata field, not an image prompt field. Stage C must still follow SHARED §4
and never use these names in IMAGE PROMPT bodies.


================================================================================
PART 23 — OUTPUT FORMAT
================================================================================

For every scene, use exactly this format:

--- Scene {X} / ~{TOTAL_ESTIMATED_SCENES} ---
Hindi line:
{exact Hindi segmented scene unit}

Scene context label:
{3–8 word file-name-friendly label, no public figure names}

Current story arc:
{larger story arc name}

Current story context:
{one concise sentence explaining what is happening at this exact moment in the story}

Visual continuity anchor:
{one concise phrase linking this scene to the continuing location, character state, political phase, investigation thread, campaign arc, legal arc, media arc, metaphor, or emotional arc}

Surrounding environment:
{concrete visible setting around the subject, including era/geography/mood/props/background figures where useful}

Visual beat type:
{one option from PART 18}

Main location:
{specific location with era/mood/context, not generic}

Main subject:
{main visible subject or group with role/archetype and action/state, no public figure names outside Hindi line}

Supporting visual elements:
{2–5 concrete visual elements; no readable text/logos/symbols/nameplates}

Camera scale suggestion:
{one option from PART 19}

Scene function:
{one option from PART 20}

Library lock:
{CHARACTER_IDs or NONE}

On-screen location:
{real named location as it should appear as a video text overlay — e.g. "Chandni Chowk, Delhi" or "Kandahar Airport, Afghanistan" or NONE}

On-screen name:
{real person name, operation name, or event name to show as a video text overlay — e.g. "Ajit Doval" or "Operation Safal" or "IC-814 Hijack" or NONE}

Breakdown note:
{one short line explaining split/merge logic and why this is one visual beat}


================================================================================
PART 24 — EXAMPLES
================================================================================

Weak output:
Main location:
court corridor

Main subject:
senior strategist figure

Better output:
Main location:
2010 Gujarat court corridor under media pressure

Main subject:
senior national political strategist figure standing with restrained posture under legal and media scrutiny

Current story context:
The story opens at the central figure’s public low point, before the comeback arc begins.

Visual continuity anchor:
Opening downfall arc at the court.

Surrounding environment:
Institutional court corridor with waiting reporters outside, security barricades,
camera flashes, legal folders, and tense public attention.

Supporting visual elements:
court doorway, media cameras, legal folder, security barricade, muted crowd


Weak output:
Main location:
strategy room

Main subject:
map

Better output:
Main location:
2014 Uttar Pradesh election command room

Main subject:
senior national political strategist figure studying booth-level voter patterns on a state map

Current story context:
The campaign shifts from public rally noise to booth-level calculation.

Visual continuity anchor:
Uttar Pradesh comeback and booth machinery arc.

Surrounding environment:
Crowded campaign backroom with district maps, voter lists, handwritten social-equation notes, tea glasses, and workers waiting for instructions.

Supporting visual elements:
UP district map, booth voter lists, handwritten notes, tea glasses, wall board with unreadable marks


Weak output:
Main location:
court corridor and market metaphor desk

Better output:
Main location:
2010 Gujarat court corridor under media pressure

Current story context:
The market metaphor is applied to the political fall, showing the central figure treating public panic as temporary rather than final.

Visual continuity anchor:
Court downfall connected to business-market thinking arc.

Surrounding environment:
Court corridor with camera pressure outside, legal files nearby, and a restrained figure standing still as others assume his career is finished.

Supporting visual elements:
media cameras, court doorway, legal file bundle, distant reporters, muted institutional lighting


Weak outro:
Scene 1:
Comment में अपनी राय जरूर बताइए।

Scene 2:
अगर आपको यह कहानी पसंद आई हो...

Better outro:
One scene:
Comment में अपनी राय जरूर बताइए। अगर आपको यह कहानी पसंद आई हो, तो video को like जरूर करिए, और Sach Uncovered को subscribe करना मत भूलिएगा।

Scene function:
CTA


================================================================================
PART 3 — INPUT SLOTS (fill these before sending)
================================================================================

STORY_CONFIG_BLOCK:
{Paste the STORY CONFIG BLOCK output from Stage A here.}

FULL_STORY:
{Paste the full Hindi / Hinglish / English story here — same as used in Stage A.}

CHARACTER_LIBRARY:
{Paste the same locked character library text used in Stage A for THIS story.
The character folder/library may change per story; Stage B must detect the
available neutral character IDs from the supplied library and propagate those exact IDs into
"Library lock:" whenever the matching character appears, is referenced, is
implied, or appears as a younger/older/photo/silhouette/screen/reflection/memory
version. Leave blank or write NONE if no library is supplied — Stage B will then
emit no library locks and Stage C will fall back to inference per SHARED §3 and §5.}


================================================================================
PART 4 — TASK
================================================================================

Read the STORY_CONFIG_BLOCK, FULL_STORY, and CHARACTER_LIBRARY above.

Execute Stage B only per every rule and output schema defined earlier in this document
(for example PART 23 — OUTPUT FORMAT and all segmentation / metadata rules).

Preserve Hindi lines exactly. Make every scene context-aware enough for Stage C image generation.

Output ONLY the LOCKED SCENE BREAKDOWN.

Do not output commentary, explanation, summary, image prompts, motion prompts,
or anything outside the locked scene breakdown.

================================================================================
END OF STAGE B FILE
================================================================================
 
