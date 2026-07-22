================================================================================
STORY SCENE BREAKDOWN PROMPT — 5-SECOND CLIPS / 110-CHARACTER MAXIMUM
================================================================================

PURPOSE

Break the supplied story into clean 5-second narration scenes.

The supplied story is the only required input.

Return only the final scene breakdown. Do not return configuration, analysis,
metadata, image prompts, motion prompts, character libraries, visual prompts,
overlays, explanations, summaries, headings outside the scene blocks, or any
commentary before or after the result.


================================================================================
1. CORE TASK
================================================================================

Convert the complete story into chronological 5-second scene units.

Each scene must contain:
- one complete narration unit;
- one clear visual beat;
- no more than 110 visible characters;
- the original story wording;
- no broken or dangling sentence fragment.

Process the entire story from beginning to end.

Every source word must appear exactly once and in the same chronological order.
Do not omit, duplicate, paraphrase, summarize, translate, correct, or add
narration.


================================================================================
2. NON-NEGOTIABLE CHARACTER LIMIT
================================================================================

CHARACTER COUNT IS AUTHORITATIVE.

A Hindi line must never exceed 110 visible characters.

Count every visible character exactly as emitted, including:
- Devanagari letters;
- matras;
- spaces;
- punctuation;
- quotation marks;
- numerals;
- English words;
- hyphens and dashes.

Do not count the scene number, field labels, or character-count field.

Rules:
- 75–110 characters is the preferred range when the content forms one complete
  narration and visual beat.
- 60–74 characters is acceptable when a natural complete scene cannot be
  merged safely.
- Below 60 characters is allowed only for a genuine punch, reveal, command,
  question, dialogue response, climax, transition, or unavoidable complete
  visual beat.
- 111 or more visible characters is always invalid and must be split.
- Not a single visible character may appear after character 110.

Word count is advisory only.
Never split a line merely because it contains a certain number of words.


================================================================================
3. COMPLETE-SENTENCE PRIORITY
================================================================================

A complete source sentence of 110 characters or fewer should normally remain
intact.

Split a sentence below 111 characters only when it clearly contains more than
one visual beat, such as:
- a location change;
- a time-period change;
- a main-subject change;
- a separate physical action requiring another shot;
- setup followed by payoff;
- cause followed by a visually separate consequence;
- dialogue followed by another person's reaction;
- an establishing view followed by a close object or action detail;
- public action followed by private action;
- planning followed by field execution;
- attack followed by aftermath.

Do not split merely because the sentence contains commas, multiple clauses, or
more words than usual when it can be shown as one continuous 5-second shot and
remains within 110 characters.


================================================================================
4. ONE-VISUAL-BEAT TEST
================================================================================

For every proposed scene, silently ask:

“Can this narration be represented clearly through one continuous 5-second
shot with one primary visual idea?”

If yes, keep it together when it remains within 110 characters.

If no, split it at the strongest natural boundary.

Multiple small actions by the same subject in the same location may remain one
scene when they form one continuous action and require no camera reset.

Do not create separate scenes for every noun, verb, clause, or sentence.
The segmentation unit is one complete visual beat, not one sentence by default.


================================================================================
5. MANDATORY MERGE RULES
================================================================================

Merge adjacent narration units when all of the following are true:
- they share the same location;
- they share the same primary subject or visual anchor;
- they share the same camera setup;
- they share the same emotional or narrative purpose;
- no new major action begins;
- no new person becomes the primary subject;
- no new important object requires a close-up;
- the combined line remains at or below 110 visible characters;
- the combined line sounds complete and natural.

Strong merge candidates include:
- date + location;
- time + atmosphere;
- identity setup + identity reveal;
- statement + direct clarification;
- two short atmosphere sentences describing the same frame;
- a short sentence + its dependent explanation;
- a person introduction + the person's role;
- dialogue setup + short dialogue;
- negation + immediate affirmation;
- two short rhetorical questions about the same visual moment;
- short CTA fragments belonging to the same audience prompt.

Before keeping any scene below 60 characters, check whether it can merge with
the immediately previous or next narration unit without crossing 110 characters
or creating a second visual beat.

A short complete scene is acceptable when merging would combine different
locations, subjects, actions, times, camera setups, or narrative beats.


================================================================================
6. DEPENDENT-FRAGMENT PROTECTION
================================================================================

Never create an isolated scene that depends grammatically on the previous line.

Do not begin a new scene with connector words such as:
- जो
- जिसकी
- जिसने
- जिन्हें
- जिसका
- और
- लेकिन
- मगर
- क्योंकि
- जहाँ
- वहां / वहाँ
- इसलिए
- जबकि
- फिर भी
- ताकि
- जिससे
- जिन्हें
- कि

unless the source itself uses that text as a genuinely complete standalone
sentence and it cannot safely merge with an adjacent line.

Examples of invalid over-splitting:

Scene A:
यहीं उनकी मुलाकात अनातोली सोबचक से हुई।

Scene B:
जो उनके कानून के शिक्षक रह चुके थे।

Scene C:
और बाद में सेंट पीटर्सबर्ग के मेयर बने।

Correct approach:
Merge the dependent role information with the person's introduction whenever
the complete line stays within 110 characters. If the full combination exceeds
110, keep each resulting scene grammatically complete rather than starting with
“जो” or “और”.

Never leave behind:
- a relative clause without its noun;
- a conjunction without its preceding idea;
- a dangling modifier;
- an unfinished comparison;
- an incomplete quote;
- a participial chain without its main verb;
- a cause without the statement it explains.


================================================================================
7. SAFE SPLIT ORDER
================================================================================

When a proposed scene exceeds 110 characters or contains multiple genuine
visual beats, split it using this order:

1. FULL SENTENCE BOUNDARY
   Split at `।`, `.`, `?`, `!`, or a closed quotation mark when the resulting
   units are complete.

2. DIALOGUE / REACTION BOUNDARY
   Separate spoken dialogue from another person's reaction or resulting action
   when they need different shots.

3. STRONG DASH BOUNDARY
   Split at `—` only when both sides are complete narration units.

4. COMPLETE CLAUSE BOUNDARY
   Split at a natural clause boundary only when both resulting lines remain
   independently understandable and grammatically complete.

5. COMMA BOUNDARY — LAST RESORT
   Use a comma only when the line would otherwise exceed 110 characters and no
   safer boundary exists. Choose the strongest comma where neither side becomes
   a fragment.

When a mandatory within-sentence split requires it, make only the smallest
punctuation adjustment needed to give both scene lines a valid ending. Do not
change, remove, reorder, or add narration words.

Never split:
- inside a person's full name;
- inside a date or number expression;
- inside a short quoted phrase;
- between a noun and its essential relative clause;
- inside `करके`, `कर`, `ते हुए`, `ती हुई`, `होते हुए`, or similar chains when
  they modify the same main action;
- inside a list whose items belong to one visual frame;
- merely to make two lines visually equal in length.


================================================================================
8. VALID LINE ENDINGS
================================================================================

Every Hindi line must end with one of the following:
- `।`
- `?`
- `!`
- a closed quotation mark after a complete sentence.

A scene line must never end with:
- a comma;
- a colon;
- a semicolon;
- an open quotation mark;
- a trailing dash;
- a connector word;
- an unfinished thought.

Do not mechanically cut the line at character 110.
Find a natural earlier split boundary.


================================================================================
9. MULTI-SENTENCE SCENES
================================================================================

Two or more short complete sentences may remain in one scene when:
- they describe the same frozen or continuous visual moment;
- they have the same subject;
- they use the same location and camera setup;
- the second sentence does not introduce a new action, person, object, clue,
  timeline, or consequence;
- their combined length does not exceed 110 characters.

Review any proposed scene containing two or more `।` marks.
Do not split it automatically.
Split only when the next sentence creates a new visual beat.

Three complete sentences should rarely remain together. Keep them together only
when all three are extremely short descriptions of the same exact visual frame
and their combined length is at most 110 characters.


================================================================================
10. DIALOGUE RULE
================================================================================

Keep a short speaker setup and its dialogue together when:
- the same person remains the primary subject;
- the same shot can show both;
- the complete line is at most 110 characters.

Split dialogue when:
- the listener's reaction needs a separate shot;
- the quote changes the location or visual focus;
- the combined line exceeds 110 characters;
- the quote itself contains separate visual beats.

Never split inside an open quotation.
Every quote must close correctly.


================================================================================
11. ABSTRACT OR METAPHORICAL LINES
================================================================================

Keep an abstract statement with its immediate explanation when both communicate
the same visual idea and the combined line is at most 110 characters.

Do not create a tiny standalone scene from a metaphor, repeated explanation, or
paraphrase when it depends on the adjacent line.

Split only when the explanation introduces a genuinely new visual subject,
time, location, action, or consequence.


================================================================================
12. PIPE OR MANUAL BREAK MARKERS
================================================================================

When the source contains `|`, treat it as a preferred review point, not an
automatic scene break.

Split at `|` when the two sides contain different actions, subjects, locations,
times, or visual beats.

Merge the two sides when they form one continuous visual beat and the combined
line remains at most 110 characters.

Remove the `|` from the final Hindi line. Do not create broken fragments around
it.


================================================================================
13. SCENE DENSITY CONTROL
================================================================================

Do not over-segment the story.

After preparing the first breakdown, perform a merge pass:
- review every scene below 60 characters;
- merge dependent fragments;
- merge same-frame short sentences;
- merge date/place combinations;
- merge identity/role combinations;
- merge statement/clarification pairs;
- merge repeated or paraphrased thoughts;
- merge short CTA fragments;
- keep every merged result at or below 110 characters.

Do not reduce the number of scenes by combining different visual beats.

A healthy breakdown should use the available 110-character capacity where
natural, rather than producing many 20–50-character fragments.


================================================================================
14. SOURCE-PRESERVATION AUDIT
================================================================================

Before output, verify:

1. Every story word is included.
2. No story word appears twice.
3. The original chronological order is preserved.
4. No narration has been paraphrased.
5. No grammar or vocabulary has been rewritten.
6. No new narration, CTA, fact, transition, or explanation has been added.
7. Only minimal punctuation adjustment was used where a mandatory internal
   split required a complete ending.


================================================================================
15. FINAL SCENE AUDIT
================================================================================

Before returning the answer, verify every scene:

1. Contains no more than 110 visible characters.
2. Has the exact correct character count.
3. Represents one clear 5-second visual beat.
4. Is a complete narration unit.
5. Does not begin as a dependent connector fragment.
6. Does not end with a comma, dash, colon, or unfinished thought.
7. Has not been kept unnecessarily short when a safe same-beat merge exists.
8. Has not merged different locations, times, subjects, actions, or camera
   setups merely to reduce scene count.
9. Preserves the original story words and order.
10. Contains no metadata or explanation outside the required output fields.

If any scene fails, correct it before output.


================================================================================
16. REQUIRED OUTPUT FORMAT
================================================================================

Return only consecutive scene blocks in exactly this format:

--- Scene 1 ---
Hindi line:
{exact narration for this scene}

Character count:
{exact visible-character count of the Hindi line}

--- Scene 2 ---
Hindi line:
{exact narration for this scene}

Character count:
{exact visible-character count of the Hindi line}

Continue until the complete story has been processed.

Do not output:
- an introduction;
- a title for the breakdown;
- estimated total scenes;
- timestamps or duration estimates;
- word counts;
- reasoning;
- split or merge notes;
- scene descriptions;
- locations as separate fields;
- character details;
- image or motion prompts;
- configuration blocks;
- summaries;
- concluding commentary.


================================================================================
17. INPUT
================================================================================

FULL STORY:
{Paste the complete story below this line.}


================================================================================
18. EXECUTION COMMAND
================================================================================

Break the FULL STORY into scenes using every rule above.

Output only the scene blocks in the required format.
Do not output anything else.

================================================================================
END OF PROMPT
================================================================================
