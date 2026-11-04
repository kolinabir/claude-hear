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

## Still possible

- pyin: drop the 4-process pool (each worker pays librosa import + numba JIT); measure 1 vs 2 workers.
- sherpa-onnx CED audio tagger (45 MB, fixed 527 AudioSet labels) as a CLAP alternative; untested.
- CPU-only Windows/Linux: not measured here; the same torch removal applies.

## Claude Code docs check (same day)

- `allowed-tools: Bash(uv run --script ${CLAUDE_SKILL_DIR}/hear.py *)` in SKILL.md pre-approves the run for the
  turn that invokes the skill (added, untested against a live permission prompt).
- A `.claude-plugin/plugin.json` beside SKILL.md would make `claude plugin install` work from the GitHub repo; not
  added, the symlink install works today.
- Neither Claude Code nor the API accepts audio input natively (docs index lists only vision and PDF), so the skill
  is still the way in.
