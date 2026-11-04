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
