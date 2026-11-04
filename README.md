# hear: let Claude listen

A [Claude Code](https://code.claude.com) skill that gives Claude ears. Claude can't take audio input,
so `hear` turns any audio or video file into a report Claude can read (who spoke, what they said,
and *how* they said it) plus a spectrogram Claude can look at.

Everything runs **locally on your Mac**. Free, private, no API keys.

```text
S1 [00:00.0–00:03.2] (209 wpm) So↑ I started lifting when I was about 12 years old.↓ ↘
S1 [00:03.3–00:04.9] (231 wpm) My mum↑ bought me a magazine. ↘
S2 [00:05.2–00:07.1] (191 wpm) Oh my god, that's so cute. ↘ {sounds surprised 1.0}
S1 [00:07.4–00:12.0] (206 wpm) Yeah, and then she gave me soup cans to curl in the kitchen, which was hilarious.
S2 [00:12.6–00:13.1] That's sweet.
```

## What Claude gets

| | |
|---|---|
| **Words** | Full transcript with a time for every word ([Whisper large-v3 turbo](https://huggingface.co/mlx-community/whisper-large-v3-turbo) on MLX) |
| **Speakers** | `S1`, `S2`… per line, from a voice fingerprint ([WeSpeaker ResNet34](https://github.com/k2-fsa/sherpa-onnx)) |
| **Delivery** | `**louder**`, `(quieter)`, pitch `↑ ↓`, rising/falling line ends `↗ ↘`, pauses `‖0.8s‖`, pace in wpm |
| **Unclear words** | `[?]` where Whisper wasn't sure, so Claude treats it as a guess |
| **Emotion** | `{sounds happy 0.9}` when confident ([emotion2vec+](https://huggingface.co/Voldorn/emotion2vec-plus-large-onnx)) |
| **Sounds** | background music, laughter, applause, whooshes… ([CLAP](https://huggingface.co/laion/clap-htsat-unfused), zero-shot) |
| **Spectrogram** | an image of the sound for anything the labels miss |

## Install

You need an **Apple Silicon Mac** (M1–M4) on **macOS 14+** with [Claude Code](https://code.claude.com).
The installer adds `ffmpeg` (via Homebrew) and [`uv`](https://docs.astral.sh/uv/) if they are missing.

```bash
git clone https://github.com/kolinabir/claude-hear.git ~/.claude-hear
~/.claude-hear/install.sh --warm
```

`--warm` downloads the models now (~3 GB, a few minutes). Without it, the first listen does it.

If the repo is public, the same in one line:

```bash
curl -fsSL https://raw.githubusercontent.com/kolinabir/claude-hear/main/install.sh | bash -s -- --warm
```

The installer links the skill into `~/.claude/skills/hear`, so every Claude Code session on your Mac can use it.

## Use it

Just ask Claude Code:

> listen to ~/Downloads/interview.mp4 and tell me where the speaker sounds unsure

> transcribe this voice note and tell me who talks more

> /hear ~/Desktop/podcast.m4a

Or run it yourself:

```bash
uv run --script ~/.claude/skills/hear/hear.py clip.mp4 --out ./clip-hearing
```

| Option | What it does | Time for a 40 s clip* |
|---|---|---|
| *(none)* | everything | ~45–50 s |
| `--fast` | words + delivery only (no speakers, sounds, emotion) | ~30 s |
| `--separate` | removes music before transcribing, for loud music over speech | +3–4 min |
| `--language en` | forces the language when it's detected wrong | n/a |

\* M4, models already downloaded.

Output in the `--out` folder:

- `hearing.md`: the report Claude reads (speakers, sounds, timeline, run stats)
- `spectrogram.png`: picture of the sound (time →, frequency ↑, brightness = loudness)
- `words.json`: per-word numbers (start, end, confidence, dB, Hz, speaker)

## Commands

| Task | Command |
|---|---|
| Install | `./install.sh` |
| Install + download models | `./install.sh --warm` |
| Update | `git -C ~/.claude-hear pull` (the skill is linked, so that's all) |
| Uninstall | `./uninstall.sh` |
| Uninstall + delete models | `./uninstall.sh --purge` |

## How it works

```text
your file ─ ffmpeg ─▶ 16 kHz audio
                       │
  1. sounds    CLAP, 2 s windows        → music / laughter / effects
  2. asr       Whisper (MLX)            → words + timings + confidence
  3. prosody   loudness + pyin pitch    → **loud** (quiet) ↑ ↓ ↗ ↘
  4. speakers  voice fingerprint/line   → S1 / S2
  5. emotion   emotion2vec+ per line    → {sounds happy 0.9}
                       │
             hearing.md + spectrogram.png + words.json
```

Each stage is a separate [`uv` script](https://docs.astral.sh/uv/guides/scripts/) with its own dependencies.
Stages run **one at a time** and exit when done, so their memory is freed before the next starts.

## Resources

| | |
|---|---|
| Peak RAM | **~2.4 GB** (Whisper; every other stage is lower) |
| Models | ~3.5 GB (+0.9 GB only if you use `--separate`) |
| Python packages | ~3–4 GB in uv's cache (torch, MLX, librosa…) |
| Speed | ~1.2× the clip length on an M4 |

## Limits

- **Apple Silicon only** (Whisper runs on MLX).
- The marks are cues, not facts: "louder and higher" isn't proof of anger.
- Emotion leans neutral and was trained mostly on acted speech.
- Speaker labels are least reliable on very short lines and over loud music; a speaker marked
  *brief* may be the main voice misheard.
- Sound labels are guesses: CLAP confuses neighbours like laughing vs coughing, or speech-over-music vs singing.
- Pitch is only given for words with clear voicing (about half).

## Repo layout

```text
skill/SKILL.md        instructions Claude reads
skill/hear.py         runs the stages and writes the report
skill/stages/*.py     one script per stage
install.sh            uninstall.sh
docs/                 home page (GitHub Pages)
research/             how the models were chosen
results/              test runs
```
