---
name: hear
description: Listen to an audio or video file (mp3, wav, m4a, aac, mp4, mov, webm...). Transcribes speech with word timings and reports who spoke, how it was said (loudness, pitch, pauses, pace, unclear words, emotion guesses), and non-speech sounds (music, laughter, effects), plus a spectrogram image. Use when the user asks to listen to, hear, transcribe, or judge the tone, delivery, speakers or audio of a file.
---

# Hear

Claude has no audio input. This skill turns sound into text Claude can read and an image Claude can see.
Everything runs locally and free on macOS, Windows and Linux. Whisper uses the GPU on Apple Silicon (MLX)
or an NVIDIA GPU when CUDA works; otherwise it runs on the CPU.

## Run

```bash
uv run --script <this skill's base directory>/hear.py "<file>" --out "<scratchpad>/hear-<name>"
```

| Option | Use when | Cost (40 s clip, warm, Apple M4) |
|---|---|---|
| (default, full) | almost always | ~45–50 s |
| `--fast` | only the words and delivery matter (no speakers, sounds, emotion) | ~30 s |
| `--separate` | loud music drowns the speech and the report shows many `[?]` | +3–4 min |
| `--language en` | the language is detected wrong | — |

- On a PC without an NVIDIA GPU, transcription runs on the CPU and takes roughly the clip's length or more; run long files in the background.
- Stages run one at a time in separate processes, so peak memory is ~2.4 GB (Whisper) however many stages run.
- First run downloads models (~3.5 GB in total) and Python packages; it takes several minutes. Later runs are fast.
- Files over ~5 minutes (or ~2 minutes on a CPU-only PC): run it in the background.

## Read the output

1. Read `hearing.md`:
   - **Speakers**: how many voices, share of talking time, typical pitch. A speaker marked "brief" may be a false split caused by music or noise; say so rather than asserting a second person.
   - **Sounds**: background music likelihood, where music is prominent, and "possibly X" events (laughter, applause, whoosh, crowd...). These are CLAP guesses; it confuses neighbours like laughter vs coughing/crying and speech-over-music vs singing.
   - **Timeline**, one line per phrase, prefixed `S1`/`S2` when there are several speakers:
     - `**word**` clearly louder (emphasis), `(word)` clearly quieter (trailing off, aside)
     - `↑` / `↓` pitch well above / below *that speaker's* normal
     - `[?]` Whisper was unsure: treat the word as a guess
     - `‖0.8s‖` pause inside a line, `— no speech —` gaps over 1 s
     - `↗` / `↘` line ends rising (question, uncertainty) / falling (statement)
     - `(N wpm)` pace; edited reels run fast (200–300) because pauses are cut
     - `{sounds happy 0.9}` emotion guess, only shown when confident and not neutral
2. View `spectrogram.png` when the question is about sound itself: time left→right, frequency bottom→top (log scale), brightness = energy. Speech = wavy stacked bands in bursts; music = steady horizontal lines and beats; hum/hiss = a flat line or haze across the width; silence = dark columns; sharp full-height lines = hard cuts or clicks.
3. `words.json` has per-word numbers (start, end, probability, db, hz, speaker).

## Be honest about limits

- Marks are cues, not certainty. Say "louder and higher here, which sounds emphatic", not "they were angry".
- Emotion comes from a model trained mostly on acted speech; it leans neutral and can misread casual tone.
- Speaker grouping uses a voice fingerprint per line; very short lines and lines over loud music are least reliable.
- Pitch is skipped on words pyin can't call voiced (about half the words); music under speech can still mislead it.
