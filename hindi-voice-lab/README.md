# Hindi Voice Lab

Standalone local app for zero-shot Hindi speech from a short clip of your own voice. It is not part of the CMS, it does not call ElevenLabs, and a saved voice profile is only a reference recording. It is not a fine-tuned model.

This does not promise ElevenLabs-level quality or a perfect identity match. Chatterbox Multilingual can resemble a reference speaker, and it can also drift, mispronounce, or change pacing.

## This machine

Checked while building the lab:

| Item | Value |
| --- | --- |
| OS | macOS 26.4.1 (build 25E253), arm64 |
| Chip | Apple M1 Pro, 10 CPU cores, 16 GB unified memory, Metal supported |
| CUDA | Not available |
| MPS | Available in the installed PyTorch build. `auto` selects MPS. No speech was generated on MPS, so acceleration is unverified |
| System Python | `/usr/bin/python3` is 3.9.6, which is too old |
| Lab Python | CPython 3.11.17 from the python-build-standalone release `20261009`, stored in `.python/` and used by `.venv/` |
| FFmpeg | Not installed on the system. The lab venv includes imageio-ffmpeg 0.6.0, which ships an FFmpeg 7.1 binary for MP3 and M4A |

## Model

Pinned package: **chatterbox-tts 0.1.7** from PyPI (wheel sha256 `83782500e3ad4e7c919132e9d7eb8755f29f57c5bde5ec48c655ca23a4eb113c`).

That release's `ChatterboxMultilingualTTS.from_pretrained(device)` has no `t3_model` argument. `from_local()` loads this file by name:

- Repository: [ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox)
- Checkpoint: `t3_mtl23ls_v2.safetensors`
- Expected sha256: `b1237586127ce98e7800a68e49938eb5092846862aabcb6e17b2fda7889a6c75`
- Also required: `s3gen.pt`, `ve.pt`, `grapheme_mtl_merged_expanded_v1.json`, `conds.pt`, `Cangjie5_TC.json`
- Language passed to `generate()`: `hi`

GitHub master later added an optional `t3_model="v3"` switch (commit `5de7a54aa4e5e2baadb0182dde554908b48b85c2`, 2026-07-21). The published 0.1.7 package cannot select that file, and its own default remains the v2 checkpoint above. This lab does not install a moving Git branch and does not load the English-only Turbo or Nano models.

The installed `generate()` arguments, confirmed from the package in `.venv`, are `text`, `language_id`, `audio_prompt_path`, `exaggeration=0.5`, `cfg_weight=0.5`, `temperature=0.8`, `repetition_penalty=2.0`, `min_p=0.05`, and `top_p=1.0`. There is no seed argument. If you enter a seed, the app calls `torch.manual_seed` before each segment. That is best-effort and is not guaranteed to match across MPS and CPU.

Reference audio used by this package:

- First **6 seconds** at 16 kHz for speaker conditioning (`ENC_COND_LEN`)
- First **10 seconds** at 24 kHz for the decoder (`DEC_COND_LEN`)
- Output sample rate: **24000 Hz**
- Each `generate()` call stops at `max_new_tokens=1000`, which is **40 seconds** at 25 speech tokens per second

Longer reference audio is ignored by the model, not learned. The app refuses a selection longer than 30 seconds so a full recording is never sent.

Other tested package versions are in `requirements.lock`, including `torch==2.6.0`, `torchaudio==2.6.0`, `transformers==5.2.0`, `gradio==6.8.0`, `resemble-perth==1.0.1`, `librosa==0.11.0`, and `s3tokenizer==0.3.0`.

## Setup

From any directory:

```bash
/Users/alokkumarverma/project/cms-code/hindi-voice-lab/scripts/setup.sh
```

The script resolves its own folder, creates `.venv` only inside this folder, and installs `requirements.txt` there. It does not change shell startup files or the system Python. If `python3.11` is already on `PATH`, it uses that. Otherwise it downloads the pinned CPython 3.11.17 build into `.python/`.

Download the checkpoint once, while online:

```bash
/Users/alokkumarverma/project/cms-code/hindi-voice-lab/scripts/download_models.py
```

Weights land in `hindi-voice-lab/cache/huggingface`. The script checks the sha256 of `t3_mtl23ls_v2.safetensors` and stops if Hugging Face `main` no longer has the file this package loads.

Check the environment:

```bash
/Users/alokkumarverma/project/cms-code/hindi-voice-lab/scripts/doctor.py
```

Start the app:

```bash
/Users/alokkumarverma/project/cms-code/hindi-voice-lab/scripts/run.sh
```

Open [http://127.0.0.1:7865/](http://127.0.0.1:7865/). The host is fixed to `127.0.0.1`. Public Gradio sharing is off. To use another port, copy `.env.example` to `.env` and set `HINDI_VOICE_PORT`. If that port is taken, the app exits and leaves the other process alone.

Stop the app with Ctrl+C in the terminal that launched it.

## Hindi Voice Studio

The page has three screens: **My Voices**, **Text to Speech**, and **Generation History**.

**Add a voice.** On My Voices, choose **+ Add voice**. Upload a recording (it stays in this folder), pick a short clean Hindi sample, name the voice, and save it. **Use this voice now** selects that voice and opens the editor. The saved item is a cloning reference, not a fine-tuned model. A longer source file is kept and is not used as training. The model still only conditions on about 6–10 seconds of the sample you select.

**Consistent delivery.** This is on by default for each voice. Generate reuses that voice’s saved reference, settings, and seed. A matching text and settings can reuse an existing file and will say so. **New take** keeps the previous file and writes another job. A fixed seed reduces variation. It does not make every device, text, or runtime version identical.

**Pauses and presets.** Sentence pauses start at 450 ms and paragraph pauses at 800 ms. `[pause=300ms]`, `[pause=700ms]`, and `[pause=1s]` are applied locally and are not spoken. Neutral, Warm storyteller, Serious documentary, and Dramatic only change supported Chatterbox settings. They are experimental and are not emotion controls. **Narration preview** shows the spoken text, boundaries, pauses, and the settings that will be used. The script is not rewritten.

**History.** Every generation is a job under `data/jobs/<job-id>/` with the WAV in `data/outputs/<job-id>.wav` when it succeeds. MP3 is written beside it when FFmpeg is available. History and the compact History tab read those files. Playback and download do not run the model again. Successful files are not expired or overwritten. After a restart, a job that was still generating is marked interrupted and its finished pieces are kept.

**Backup.** Copy these folders together:

- `data/profiles/` — voice names and reference clips
- `data/references/` — original uploads
- `data/outputs/` — finished WAV and MP3 files
- `data/jobs/` — metadata, including text, settings, and status
- `data/preferences.json` — selected voice, per-voice settings, seed, and the text draft

## Prepare a reference from a long recording

1. Upload WAV, MP3, or M4A. Decoding uses FFmpeg from `PATH` when it exists, otherwise the FFmpeg binary bundled in this lab's virtualenv. Restart the app after `scripts/setup.sh` so a newly installed decoder is picked up.
2. The original file is copied under `data/references/` and is not modified.
3. Set start and end in seconds. For a 30 minute recording, pick one clean phrase. A useful length is about 10 seconds, because the model keeps only the first 10 seconds of whatever you select (6 seconds for the speaker embedding).
4. Preview the segment. The page shows duration, sample rate, and channel count, and warns about clipping, near-silence, a very short clip, or a clip longer than the model will actually use.
5. Name the profile and save it.

The prepared clip is mono 16-bit PCM WAV. Stereo is averaged. There is no denoiser. Restarting the app keeps the profile, because it is stored in `data/profiles/`.

Keep the rest of the 30 minutes. It is not used here. A later training experiment would need a separate design; this version does not fine-tune.

## Generate Hindi

Type Devanagari, or use **Insert Hindi sample**. Roman Hindi is sent through unchanged, and the page says Devanagari is recommended. Nothing is translated or transliterated.

Short text is one model call. Longer text is split on `।`, `॥`, `?`, `!`, and `.` (not inside numbers such as `1.5`, and not inside `...`). A blank line is a paragraph break. Pieces longer than 180 characters are split again on commas or spaces without dropping or repeating text. Commas stay in the spoken text; they do not each become a separate model call. A length split does not get a sentence pause.

Pauses are separate from the model. `[pause=300ms]`, `[pause=700ms]`, and `[pause=1s]` are parsed locally and never spoken. A sentence pause (default 450 ms) and a paragraph pause (default 800 ms) are inserted only at those boundaries. An explicit pause replaces the automatic pause at the same point instead of stacking on it. Silence already at the edge of a generated clip shortens the added gap. The clip itself is not trimmed, so a quiet syllable is kept. There is no crossfade.

Delivery presets (Neutral, Warm storyteller, Serious documentary, Dramatic) fill in the installed model's real `generate()` arguments. They are experimental combinations of exaggeration and CFG weight, with temperature left at 0.8. They are not emotion prompts. You can edit the numbers after choosing a preset. Preview the plan before generating: it shows the spoken text, segment boundaries, pause lengths, and the settings that will be used. The script is not rewritten.

Segments are generated one at a time with the same reference and settings. Progress is reported as `Generating segment 3 of 8`, not as a fake percentage inside the model call. Jobs record pipeline version 2, the parsed plan, pause settings, preset values, reference hash, and model identity. Older flat jobs stay on disk and are not reused for a new plan.

The result plays in the browser. WAV is always written. MP3 is written only when FFmpeg is available.

If a long job fails after some segments, the completed WAV pieces stay in `data/jobs/<job-id>/`. Starting the same text, profile, model, pause plan, and settings again reuses those pieces. Changing the text, pauses, preset, reference, checkpoint, or generation settings starts over. A saved profile is still only a reference clip. A clean expressive Hindi clip can influence delivery, and the model may not copy its emotion.

## Offline mode

The first download needs the network. After `scripts/download_models.py` finishes, check **Offline mode** or set `HINDI_VOICE_OFFLINE=1`. The app then sets Hugging Face offline mode and fails with a clear message if a checkpoint file is missing. It does not send text or audio to a hosted API.

## Speed and failures

On this 16 GB M1 Pro, `auto` chooses MPS. A 500M multilingual model plus the speech decoder is large for unified memory, and one short sentence can still take a noticeable amount of time. CPU is slower and is the fallback when MPS cannot run an operation.

If MPS raises an unsupported-operation error, the status text includes that error and the app retries on CPU. It does not describe that result as accelerated. If memory runs out, the message tells you to close other apps, shorten the text, or choose CPU. An out-of-memory error does not silently switch devices.

CUDA is only used when you select it and PyTorch can see a CUDA device. This Mac cannot.

## Licenses and watermark

- Code: MIT, [github.com/resemble-ai/chatterbox](https://github.com/resemble-ai/chatterbox/blob/master/LICENSE)
- Weights: MIT, [huggingface.co/ResembleAI/chatterbox](https://huggingface.co/ResembleAI/chatterbox)
- Watermark library: MIT, [github.com/resemble-ai/perth](https://github.com/resemble-ai/perth)

Every file returned by `generate()` is passed through `perth.PerthImplicitWatermarker`. The watermark is meant to be inaudible and to survive MP3 compression. An MP3 export is a re-encode of that already watermarked WAV.

## What was tested

- Unit tests: 19 tests, all passing, with no model download. They cover Hindi chunking and exact text preservation, invalid segment bounds, profile save/load, resume matching and invalidation, pause insertion, and path confinement.
- `python -m compileall` on the lab sources.
- Import of `chatterbox-tts` 0.1.7 and inspection of `from_pretrained` and `generate` against the signatures above.
- `scripts/doctor.py`: Python 3.11.17, torch 2.6.0, MPS available, CUDA unavailable, FFmpeg absent, auto device `mps`.
- Checkpoint download: all 6 files, and `t3_mtl23ls_v2.safetensors` sha256 matched `b1237586127ce98e7800a68e49938eb5092846862aabcb6e17b2fda7889a6c75`. Hugging Face snapshot `5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18`.
- The Gradio UI at `http://127.0.0.1:7865/`: the page loads, the Hindi sample fills the text box, and previewing before an upload reports that a recording is required. The server was then stopped.

Not tested:

- Real speech generation. No reference recording was available, so voice similarity was not checked. The downloaded weights were not run through `generate()`.
- MPS or CPU inference speed and memory use under a real `generate()` call.
- The v3 checkpoint. It is not what 0.1.7 loads.
- MP3 decoding with the bundled FFmpeg: `cms-generate-stories/general/168-karwa-chauth-story/audio/god.mp3` reads as about 9 minutes 33 seconds, 44.1 kHz, mono. The model still only uses the first 10 seconds of the segment you select.

## Remove the prototype

Stop the app, then delete only this folder:

```bash
rm -rf /Users/alokkumarverma/project/cms-code/hindi-voice-lab
```

That removes the virtualenv, the local Python build, cached weights, profiles, and generated audio. Nothing else in the CMS tree is required by this app.
