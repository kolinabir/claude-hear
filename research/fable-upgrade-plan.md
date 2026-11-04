# Upgrade plan for `hear` (Fable research, 2026-11-04)

Desk research only: nothing was installed or timed on this Mac. Speeds marked "unmeasured" are inferred.

## Top 5, ranked

| # | Upgrade | Package / model | Fixes | Install cost | Main risk |
|---|---------|-----------------|-------|--------------|-----------|
| 1 | Speaker diarization | **senko** (git main; CoreML on macOS 14+, no torch) | "who said what", speaking time per speaker | ~50 MB | Alpha project; music hurts it; model download/token needs undocumented |
| 2 | Sound-event tagging | **CLAP** `laion/clap-htsat-unfused` via `transformers` zero-shot pipeline | names laughter, applause, music, whoosh/SFX with labels you choose | torch + ~600 MB | Scores are relative to the label set: always include "speech" and "silence" |
| 3 | Better pitch | **penn** (FCNF0++) with viterbi decoding + periodicity | octave errors, fake ↑/↓ marks | torch + ~10 MB | Still fooled by music → do #4 first |
| 4 | Vocal separation | **audio-separator** (MelBand RoFormer), or `mlx-audio-separator` (2.5× faster) | music under speech hurting ASR, pitch, diarization | torch + ~1 GB | Heaviest; run only when music is detected. Demucs is archived, skip it |
| 5 | Emotion | **emotion2vec+ large ONNX** (`Voldorn/emotion2vec-plus-large-onnx`) | tone beyond loud/pitch | onnxruntime + ~1.2 GB | Bias toward "neutral"; report as "sounds X (0.7)" |

Speed notes: senko ~7.7 s per hour of audio on M3 (sub-second for 1 min). penn ~6× faster than torchcrepe on CPU. CLAP on 1-min clip: a few seconds (unmeasured).

Cheap alternative to #2 + #5 in one: **SenseVoiceSmall via sherpa-onnx** emits inline `<|Laughter|>`, `<|Applause|>`, `<|BGM|>` and emotion tags with only onnxruntime, but event detection is weaker and only zh/yue/en/ja/ko.

## Also worth knowing
- **ASR:** parakeet-mlx ≈ whisper-turbo accuracy at ~84× realtime (English only) → `--fast` mode. For mishearings like "Two/Do steroids", Whisper large-v3 (not turbo) on the vocal stem helps most. `whispermlx` adds wav2vec2 forced alignment → tighter word times, more honest wpm.
- **Audio-describing LLM:** `mlx-community/Qwen2-Audio-7B-Instruct-4bit` via mlx-audio can write a free-text caption including emotion (~4–6.5 GB, ~4.7 tok/s): optional `--describe`.
- **Paid:** Gemini API audio understanding (non-speech sounds, speakers, emotion, timestamps by prompt).
- **Diarization alternative:** pyannote community-1 is more accurate (11.2% vs 13.5% DER) but gated (HF token) and much slower on MPS.

## Proposed output format
- `## Speakers`: count, speaking-time share, median pitch per speaker
- Timeline lines prefixed `S1:` / `S2:`
- `## Sounds`: spans like `[0:00–0:04] music (upbeat)`, `[0:12] laughter`
- Per-line emotion tag only when prob > 0.5
- Keep the spectrogram as a fallback

## Sources
- senko: https://github.com/narcotic-sh/senko · https://pypi.org/project/senko/
- pyannote community-1: https://huggingface.co/pyannote/speaker-diarization-community-1 · benchmarks https://docs.rs/crate/speakrs/0.4.0/source/README.md
- mlx-audio: https://github.com/Blaizzy/mlx-audio
- CLAP: https://huggingface.co/laion/clap-htsat-unfused · https://github.com/LAION-AI/CLAP
- SenseVoice: https://github.com/FunAudioLLM/SenseVoice · https://k2-fsa.github.io/sherpa/onnx/sense-voice/index.html
- penn: https://pypi.org/project/penn/ · pitch benchmark https://gh.r-mj.com/lars76/pitch-benchmark
- audio-separator: https://pypi.org/project/audio-separator/ · https://pypi.org/project/mlx-audio-separator/0.1.20/ · demucs (archived) https://github.com/facebookresearch/demucs
- emotion2vec ONNX: https://huggingface.co/Voldorn/emotion2vec-plus-large-onnx · audeering (non-commercial) https://huggingface.co/audeering/wav2vec2-large-robust-12-ft-emotion-msp-dim
- ASR: https://pypi.org/project/silicon-asr/ · https://pypi.org/project/whispermlx/
- Qwen2-Audio MLX: https://huggingface.co/mlx-community/Qwen2-Audio-7B-Instruct-4bit · Audio Flamingo 3: https://huggingface.co/nvidia/audio-flamingo-3-hf
- Gemini audio: https://aistudio.google.com/docs/audio
- transcript-critic: https://github.com/jftuga/transcript-critic
