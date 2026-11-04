# Making `hear` faster without changing its output (2026-11-04)

Measured on an M-series Mac. Test set: four clips (6.8 s, 13.5 s, 17 s, and a 44 s synthetic scene with two
voices, shouting, a near-whisper, a 3 s gap, a beep, a noise burst, a third voice and a music bed under the
second half). Every change was accepted only if all five JSON outputs and `hearing.md` stayed byte-identical.

## Where the time went (before)

| stage | 17 s clip | 44 s clip | why |
|---|---|---|---|
| asr (Whisper turbo, MLX) | 10–14 s | 22–29 s | model load + the fixed 30 s encoder windows |
| sounds (CLAP) | 8 s | 10–19 s | `import torch` alone is 5–12 s; the audio analysis is 0.5 s |
| prosody (pyin) | 4–6 s | 6–23 s | 4 worker processes each import librosa and JIT-compile pyin |
| emotion | 2 s | 3–5 s | 650 MB ONNX model load |
| speakers | 1 s | 1 s | |

Stages ran one after another, so the clip time was the sum.

## What changed

1. **sounds: CLAP audio encoder on ONNX** (`Xenova/clap-htsat-unfused`, 117 MB), the log-mel computed in numpy
   (matches transformers' `ClapFeatureExtractor` to 8e-6 dB), and the 25 label embeddings shipped as
   `clap_labels.npz` (54 KB, computed once from the text model). No torch, no transformers, no 1.1 GB laion download.
   Result: embeddings equal torch's (cosine 1.000); stage RAM 1.7 GB → 0.3 GB; the torch-based environment
   (727 MB) → 191 MB.
2. **Whisper first, then the other four stages together.** They need only asr.json; combined they use ~1.9 GB,
   under Whisper's 2.4 GB peak. Measured whole-tree peak: 1.9–2.0 GB before and after.
3. The `.npz` is checked against `LABELS` at run time, so editing the label list without regenerating it fails loudly.

## Results

| clip | before (warm) | after (warm) | peak RAM (process tree) | outputs |
|---|---|---|---|---|
| ears 17 s | 26–31 s | 12–18 s | 1.9 → 2.0 GB | identical |
| mixed 44 s | 45 s | 29 s | 1.9 → 2.0 GB | identical |
| two-voices 13.5 s | 26 s | 20 s | same | identical |
| test 6.8 s | 28 s | 17 s | same | identical |

The four parallel stages now contend for the CPU (each reports ~8 s instead of 1–4 s alone); the wall time is
still lower. Cutting pyin's 4-process pool would help more, see below.

## Tried and rejected

- **4-bit Whisper** (`whisper-large-v3-turbo-q4`): same words, same 9.5–10 s, same 2.1 GB GPU peak. No gain.
- **SwiftF0 instead of pyin** for pitch: 30× faster (0.04 s vs 1.2 s per clip) and the public benchmark rates it
  higher, but on real speech it is a wash: against Praat as a third opinion over 111 words, pyin was 0.16 st
  off and SwiftF0 0.14 st; on the 3 words where they disagree Praat sided with pyin twice. Both were within
  0.05 st of the truth on synthetic voices. Because the ↑/↓ marks sit on a 4-semitone threshold, the swap
  changed marks on ~6 words per clip with no evidence it was more right. Not worth changing the output.
- **emotion2vec+ base** (373 MB): would save ~0.5 GB RAM; no published accuracy against the large model.
- **Batching CLAP windows**: no faster on CPU, more RAM. Per-window stays.

## Round 2 (same day)

- **pyin pool dropped.** With a warm numba cache, in-process, Pool(2) and Pool(4) all take 2.0 s on 44 s of
  speech (1.8 s on 17 s); the pool only added four processes to the ones already sharing the CPU. Results are
  identical (allclose). Full runs after this, on a quieter machine: 44 s clip 13.7 s, 17 s clip 9.2 s, all four
  reports still byte-identical to the baseline. (Some of that gain is the quieter machine, not the change.)
- **sherpa-onnx CED-mini audio tagger tried** (10 MB int8 ONNX, 527 AudioSet labels, 49 MB download): 43 windows
  in 0.18 s, 0.11 GB. Side by side with CLAP on the 44 s scene it caught what CLAP missed: the beep ("Beep,
  bleep" / "Sine wave" at 27–28 s), the noise burst ("White noise" at 33–35 s), the gap ("Silence"), and it
  labelled every voice "Speech synthesizer", which they are (macOS `say`). CLAP called a woman speaking
  "singing 0.6" at 24 s. CED did not flag the synthetic sine "music bed" as Music (it said Sine wave /
  Synthesizer), so its music detection on real music is untested here. Not applied: it changes the Sounds
  section, so it needs a decision and a look at real-music clips first.

- **CED added next to CLAP** (same day, after a decision): the sounds stage now also runs CED-mini on each 2 s
  window at 16 kHz and stores its top 3 labels as `events`; the report lists CED labels ≥ 0.1 outside a skip set
  (speech, silence, music, room ambience) and keeps CLAP for the music share. On the 44 s scene this adds the
  beep, the noise burst and a "sound effect" around the gap; one false "radio (0.22)". The three speech-only
  clips gained no events. Cost: +0.2 s, 10 MB model, 49 MB download, sounds stage still ~0.3 GB.

## Round 3: eight real videos from Downloads (reels, phone recordings, WhatsApp, a music-only piece)

What the reports got wrong, and the fix for each:

| problem seen | clip | fix |
|---|---|---|
| 20–40 "possibly X" lines per clip: mantra, radio, vehicle, heart murmur, quack... at 0.1–0.2 | every clip with a music bed | CED events listed from 0.25 (laughter from 0.15); music-family labels (150, from the AudioSet ontology, shipped as `ced_groups.json`) go to one "music style guess" line instead; room/channel labels (echo, radio, static...) never listed |
| "Thank you." twice on a music-only clip, with an emotion guess | Minimal Tech Pulse | lines dropped when CLAP saw no speech in any overlapping window; the header counts them; a speech-free clip still gets its Sounds section |
| a 25-word token loop in 0.1 s (56,400 wpm), which also created a phantom second speaker | Facebook explainer | lines over 12 words/s dropped |
| "music or singing prominent at:" listing 50 timestamps | music clip | collapsed to ranges |
| emotion stage at 2.25 GB on a 30 s line, whole run peaking at 2.7 GB | Facebook explainer | emotion input capped at 15 s per line: 1.5 GB, run peak back to 2.05 GB |

After: the music clip reads "no speech found (2 Whisper lines dropped) · ambient music (0.77), new-age, trance";
the Minecraft reel keeps "snicker (0.56), chuckle (0.36)"; the speech-only test clips' timelines are unchanged.
Not fixed: a 4 % "S2" on one reel and a 60/40 split on a single-voice WhatsApp video (130 vs 134 Hz) are
probably the same person over music; the faint test beep (0.12) now falls under the event threshold.

## Round 4: speaker split, Bengali, long lines

- **Speaker fold.** The speakers stage now saves each line's similarity to every speaker; the report folds a
  speaker with under 10 % of the talk back into the main voice when every one of its lines is doubtful (under
  loud music, CLAP music ≥ 0.8, or shorter than 1.5 s) and still resembles the main voice (cosine ≥ 0.55), or
  when it has under a second of speech in total. Fixes the reel whose intro line over the music was "S2" (the
  line's similarity to S1 was 0.74 against a 0.75 bar) and the phantom speaker born from a hallucinated line.
  The 60/40 split on the WhatsApp video turned out to be real: centroid cosine 0.48, and the second voice speaks
  with no music at the end (someone talking over a screen recording). Correct two- and three-speaker clips
  (noah, ears, two-voices, mixed) are unchanged; noah's real second speaker sits at centroid cosine 0.83, which is
  why a plain similarity threshold could never separate these cases.
- **Bengali.** Two Bengali clips: Whisper detects Gujarati at 0.42–0.54 (Bengali 0.06–0.10) on every 30 s window
  and writes Bengali sounds in Gujarati script. Decoding in each candidate language and comparing avg_logprob
  does not help either (gu −0.10 vs bn −0.16). With `--language bn` the transcript is readable Bengali. So:
  the asr stage records the detection probability, the header says "Whisper only 45 % sure: re-run with
  --language" under 0.7, and SKILL.md tells Claude to force `bn` when the script is wrong. English clips detect
  at 1.00.
- **Long lines.** Whisper returned 20–30 s segments (Bengali, fast narration). The asr stage now cuts any segment
  over 10 s at its widest word gap, repeatedly. Facebook's longest line went 27.7 → 8.7 s. What remains long is
  Whisper's own doing: in Bengali it sometimes stretches one word over 12 s, and a one-word line can't be cut.
  Whisper's temperature fallback also makes the garbage tail of the WhatsApp video differ run to run (2 vs 12
  dropped lines, 14 vs 30 unsure words), so counts on hallucinated audio are not stable.
- The sounds stage stores CLAP's speech probability per window so the hallucination check no longer depends on
  "speech" making the top 3.

## Still possible

- CPU-only Windows/Linux: not measured here; the same torch removal applies.
- CED on real music: untested (the test bed is synthetic sines, which it calls "sine wave" / "synthesizer").

## Claude Code docs check (same day)

- `allowed-tools: Bash(uv run --script ${CLAUDE_SKILL_DIR}/hear.py *)` in SKILL.md pre-approves the run for the
  turn that invokes the skill (added, untested against a live permission prompt).
- A `.claude-plugin/plugin.json` beside SKILL.md would make `claude plugin install` work from the GitHub repo; not
  added, the symlink install works today.
- Neither Claude Code nor the API accepts audio input natively (docs index lists only vision and PDF), so the skill
  is still the way in.
