# hear: let Claude listen

A [Claude Code](https://code.claude.com) skill that gives Claude ears. Claude can't take audio input,
so `hear` turns any audio or video file into a report Claude can read (who spoke, what they said,
and *how* they said it) plus a spectrogram Claude can look at.

Everything runs **locally on macOS, Windows and Linux**. Free, private, no API keys.

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
| **Words** | Full transcript with a time for every word (Whisper large-v3 turbo: [MLX](https://huggingface.co/mlx-community/whisper-large-v3-turbo) on Apple Silicon, [faster-whisper](https://github.com/SYSTRAN/faster-whisper) elsewhere) |
| **Speakers** | `S1`, `S2`… per line, from a voice fingerprint ([WeSpeaker ResNet34](https://github.com/k2-fsa/sherpa-onnx)) |
| **Delivery** | `**louder**`, `(quieter)`, pitch `↑ ↓`, rising/falling line ends `↗ ↘`, pauses `‖0.8s‖`, pace in wpm |
| **Unclear words** | `[?]` where Whisper wasn't sure, so Claude treats it as a guess |
| **Emotion** | `{sounds happy 0.9}` when confident ([emotion2vec+](https://huggingface.co/Voldorn/emotion2vec-plus-large-onnx)) |
| **Sounds** | background music share ([CLAP](https://huggingface.co/laion/clap-htsat-unfused), zero-shot) and events like beeps, laughter, applause, noise ([CED](https://github.com/RicherMans/CED) via sherpa-onnx, 527 AudioSet labels) |
| **Spectrogram** | an image of the sound for anything the labels miss |

## Install

You need [Claude Code](https://code.claude.com) and one of:

| System | Whisper runs on | Speed (40 s clip) |
|---|---|---|
| **macOS, Apple Silicon** (M1–M4, macOS 14+) | the GPU via MLX | fastest: ~15–20 s for everything |
| **Windows 10/11** | an NVIDIA GPU if CUDA 12 + cuDNN 9 are installed, else the CPU | fast with a GPU; on the CPU, Whisper alone took 34 s on a fast 10-core CPU (more on laptops) |
| **Linux** | same as Windows | same as Windows |
| **macOS, Intel** | the CPU | like a CPU-only PC |

The installer adds `ffmpeg`, `git` and [`uv`](https://docs.astral.sh/uv/) if they are missing
(Homebrew / apt / dnf / pacman on macOS and Linux, winget on Windows).

**macOS / Linux**

```bash
git clone https://github.com/kolinabir/claude-hear.git ~/.claude-hear
~/.claude-hear/install.sh --warm
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/kolinabir/claude-hear.git $HOME\.claude-hear
powershell -ExecutionPolicy Bypass -File $HOME\.claude-hear\install.ps1 -Warm
```

`--warm` / `-Warm` downloads the models now (~2.5 GB, a few minutes). Without it, the first listen does it.

**With the [skills](https://github.com/vercel-labs/skills) CLI** (copies the skill into `~/.claude/skills/hear`; you still need `ffmpeg` and `uv` on your PATH, and the first listen downloads the models):

```bash
npx skills add kolinabir/claude-hear --skill hear -a claude-code -g
```

If the repo is public, the same in one line:

```bash
curl -fsSL https://raw.githubusercontent.com/kolinabir/claude-hear/main/install.sh | bash -s -- --warm
```

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/kolinabir/claude-hear/main/install.ps1))) -Warm
```

The skill goes into `~/.claude/skills/hear` (`%USERPROFILE%\.claude\skills\hear` on Windows), so every
Claude Code session on that computer can use it. On macOS and Linux it is linked to the clone; on Windows
it is copied, because Windows links need admin rights.

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
| *(none)* | everything | ~15–20 s |
| `--fast` | words + delivery only (no speakers, sounds, emotion) | ~10–15 s |
| `--separate` | removes music before transcribing, for loud music over speech | +3–4 min |
| `--language bn` | forces the language. The report says when Whisper is unsure; Bengali often comes out in Gujarati script until you force `bn` | n/a |

\* Apple M4, models already downloaded. On Windows the command is the same, with `$HOME\.claude\skills\hear\hear.py`.

Output in the `--out` folder:

- `hearing.md`: the report Claude reads (speakers, sounds, timeline, run stats)
- `spectrogram.png`: picture of the sound (time →, frequency ↑, brightness = loudness)
- `words.json`: per-word numbers (start, end, confidence, dB, Hz, speaker)

## Commands

| Task | macOS / Linux | Windows (PowerShell) |
|---|---|---|
| Install | `./install.sh` | `.\install.ps1` |
| Install + download models | `./install.sh --warm` | `.\install.ps1 -Warm` |
| Update | `git -C ~/.claude-hear pull` | `git -C $HOME\.claude-hear pull` then `.\install.ps1` |
| Uninstall | `./uninstall.sh` | `.\uninstall.ps1` |
| Uninstall + delete models | `./uninstall.sh --purge` | `.\uninstall.ps1 -Purge` |

If PowerShell blocks the script, run it as `powershell -ExecutionPolicy Bypass -File .\install.ps1`.

## How it works

```text
your file ─ ffmpeg ─▶ 16 kHz audio
                       │
  1. asr       Whisper (MLX / faster-whisper) → words + timings + confidence
  then, together:
  2. prosody   loudness + pyin pitch    → **loud** (quiet) ↑ ↓ ↗ ↘
  3. speakers  voice fingerprint/line   → S1 / S2
  4. emotion   emotion2vec+ per line    → {sounds happy 0.9}
  5. sounds    CLAP (ONNX) + CED, 2 s windows → music share / events
                       │
             hearing.md + spectrogram.png + words.json
```

Each stage is a separate [`uv` script](https://docs.astral.sh/uv/guides/scripts/) with its own dependencies.
Whisper runs first on its own; the four light stages then run **together** in their own processes. Their memory adds up to less than Whisper's, so the peak stays at Whisper.

## Resources

| | |
|---|---|
| Peak RAM | **~2.4 GB** (Whisper, on every system; every other stage is lower) |
| Models | ~2.5 GB (+0.9 GB only if you use `--separate`) |
| Python packages | ~2–3 GB in uv's cache (MLX or faster-whisper, onnxruntime, librosa…); torch only if you use `--separate` |
| Speed | ~1.2× the clip length on an M4; Whisper alone took 34 s for a 40 s clip on the M4's CPU (faster-whisper int8, all cores) |

## Limits

- **Fastest on Apple Silicon or with an NVIDIA GPU.** On a CPU-only PC, transcription takes about the
  clip's length or more. On Windows, the GPU needs CUDA 12 and cuDNN 9 installed separately; without them
  it falls back to the CPU automatically.
- **Windows and Linux support is new**: the Windows/Linux transcription engine was tested on a Mac's CPU,
  but the PowerShell installer has not been run on a real Windows PC yet.
- The marks are cues, not facts: "louder and higher" isn't proof of anger.
- Emotion leans neutral and was trained mostly on acted speech.
- Speaker labels are least reliable on very short lines and over loud music; a doubtful minor speaker is folded
  back into the main voice, and one marked *brief* may still be the main voice misheard.
- Whisper lines with no speech under them (its "Thank you." over music) or at impossible speed (token loops) are
  dropped and counted in the header.
- Sound labels are guesses: CED lists AudioSet labels with their probability (often low, 0.1–0.5), and CLAP's music share confuses speech-over-music with singing.
- Pitch is only given for words with clear voicing (about half).

## Repo layout

```text
skills/hear/SKILL.md      instructions Claude reads
skills/hear/hear.py       runs the stages and writes the report
skills/hear/stages/*.py   one script per stage (plus clap_labels.npz and ced_groups.json, the label tables)
install.sh  install.ps1  uninstall.sh  uninstall.ps1
docs/                 home page (GitHub Pages)
research/             how the models were chosen
results/              test runs
```
