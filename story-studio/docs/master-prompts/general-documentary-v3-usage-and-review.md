# General documentary prompt: review and use

Created 14 October 2026. The new reusable profile is `general-documentary-independent-v3.md`. Existing prompts are preserved. This review examined repository code and prompt documents; it did not test the running UI or generate a sample documentary.

## What the five older files contribute

| File | Useful material | What the new profile changes |
| --- | --- | --- |
| master-story-prompt-v3-nitish-flow-universal | Multi-transcript extraction, contextual roots, mechanisms, source-independent expression | Removes creator imitation, mandatory historical roots, timed reveals, seven-word clearance assumptions, and automatic causal links |
| taxonomy-backup-general-masterprompt-3rdaug | Concrete detail, spoken Hindi, visual awareness | Despite the general filename, the content strongly favours military/intelligence stories; removes compulsory villain peaks, dialogue quotas, patriotic endings, and production bundles |
| updated-story-master-prompt-v2-nitish-rajpoot | Evidence-led investigation and concern for human consequences | Despite its filename, the body is a crime template with victim/perpetrator rules and a shock montage; these become topic-dependent rather than universal |
| v1-claude-latest-8thjune | Procedural clarity, concrete anchors, complete narrative ending | Removes rigid retention cycles, forced emotional ordering, conflicting duration formulas, and mandatory dialogue |
| v1-claude-latest-19june-with-charaacters | Same core narrative strengths plus animation continuity | Separates narration from character/image production; no mandatory ten-character list or appearance invention |

Some old requirements conflict: the first five retention blocks must all differ, while the first three must use only question or reveal types. Timing also conflicts between 300–350 characters per 30 seconds, 1,000 characters per minute, and validators using 900. These should not control a new script.

## Story Studio findings

- `src/lib/prompts/index.ts` separates claim extraction, source fingerprinting, planning, and writing. The final writer is intended to receive neutral facts rather than source prose.
- `src/lib/prompts/profile.ts` makes profile rules an editable delivery layer; the app retains factual and originality boundaries. Project length overrides profile length.
- `src/lib/external-writer-brief.ts` combines the selected profile, saved settings, and enabled fact bullets for external writing. It removes exact duplicate bullets and uses a reproducible order independent of source order. Shuffling does not verify facts or prove originality.
- `src/app/settings/prompts/page.tsx` supports creating, viewing, editing, and duplicating profiles. Saving a Markdown file does not automatically create a profile in the app database.
- `docs/master-prompts/general-documentary.md` already contains a useful Revision 2 profile. It is the closest existing match to this request and is preserved.
- `src/lib/narration/count.ts` counts Unicode code points with ±5% tolerance; its app fallback is 6,000 characters. The new prompt's 12,000-character standalone fallback never overrides the app's project target.
- The app is source-only: fact extraction and originality QA do not constitute independent fact-checking. Review important claims before writing and publishing.

## Use in Story Studio

1. Open Prompt Profiles at `/settings/prompts`.
2. Create a profile named **Original Hindi Documentary — V3**, with genre **General Documentary**.
3. Paste the complete contents of `general-documentary-independent-v3.md` into Writing rules / Style instructions and save.
4. Select that profile in the project's story settings. Set the character target, tone, opening preference, narrative approach, and CTA mode there.
5. Paste source transcripts. Generate fact bullets, then review and edit the Fact Bank, especially conflicting numbers, allegations, and causal claims.
6. Use **Copy master prompt** for an external writer, or generate the story inside Studio. The exported brief already supplies project settings and reference bullets; do not add the standalone template a second time.

Suggested starting settings: general audience, thoughtful conversational tone, Auto opening and narrative approach, an explicitly chosen character target, and one mid-story plus closing CTA if desired. A specific project can choose a different treatment.

## Use directly with transcripts

Paste the complete reusable prompt into your writing model, then append the input template below. Label each source separately. One transcript is sufficient, but one source does not establish independent corroboration.

```text
TOPIC / WORKING TITLE:
[Your subject or central question]

AUDIENCE:
General Hindi-speaking viewers; no specialist knowledge assumed.

LANGUAGE:
Natural spoken Hindi in Devanagari.

TARGET CHARACTERS:
[For example: 12000 Unicode code points, ±5%]

TONE:
Thoughtful, clear, conversational; tension only where supported.

NARRATIVE APPROACH / OPENING:
Auto — choose from the evidence.

MUST COVER:
[Optional questions or relevant points; these are not assumed true]

CTA MODE:
[No CTAs / closing only / one mid and closing / two mid and closing]

CHANNEL NAME / CLOSING PREFERENCE:
[Optional]

EXTERNAL RESEARCH:
No — use supplied material only.

OUTPUT:
Finished narration only, in natural paragraphs.

REFERENCE MATERIAL — SOURCE 1:
[Source title, URL/date if known, then transcript or notes]

REFERENCE MATERIAL — SOURCE 2:
[Optional; label each additional source separately]

KNOWN CONFLICTS / UNCERTAINTIES:
[Optional]

Write the complete documentary using the master prompt above.
```

## YouTube concern

YouTube's published monetization policy discusses reused content without substantial original value and mass-produced or repetitive content. It does not specify a ban on a 30-second curiosity/reveal pattern. Avoiding that formula is an editorial choice; the stronger improvement is substantive original explanation and a subject-specific narrative. A prompt or an app QA PASS cannot guarantee platform approval or copyright clearance.

Official reference: https://support.google.com/youtube/answer/1311392?hl=en

## Editorial update — Version 3.1

The reusable prompt now incorporates the Nauru script review: a subject-specific opening without a second introduction, brief claim-level attribution instead of research-process commentary, one full explanation per mechanism, more space for concrete central developments, natural transitions after CTAs, and a concise single ending. Length repair should deepen supported material rather than restore repetition.

The existing `general-documentary-independent-v3.md` filename remains the canonical file; its contents are now Version 3.1. Access to the running app was declined during this update, so the saved database profile was not changed. Edit the existing General Documentary profile and replace its Writing rules with this file once, then save. Future Copy master prompt exports using that profile will include these rules automatically. Previously copied prompts will not change.
