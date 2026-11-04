#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Turn an audio/video file into text Claude can "hear".

Runs each analysis stage as its own process, one at a time, so peak RAM is the biggest stage
(~2.2 GB, Whisper) instead of the sum of all models.
"""
import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

STAGES = Path(__file__).resolve().parent / "stages"
QUIET_LABELS = {"neutral", "other", "unknown"}
NOT_EVENTS = {"speech", "silence", "music", "singing"}


def run(stage, *args, required=False):
    t = time.time()
    p = subprocess.run(["uv", "run", "--quiet", "--script", str(STAGES / f"{stage}.py"), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode:
        msg = f"stage {stage} failed:\n" + "\n".join(p.stderr.strip().splitlines()[-8:])
        if required:
            sys.exit(msg)
        print(msg, file=sys.stderr)
    else:
        print(f"  {stage}: {time.time() - t:.0f}s", file=sys.stderr)


def load(out, name):
    p = out / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def ts(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def semitones(hz, ref):
    import math
    return 12 * math.log2(hz / ref) if hz and ref else None


def mark(w, ref_db, ref_hz):
    text = w["word"].strip()
    d = w["db"] - ref_db if w.get("db") is not None else 0
    st = semitones(w.get("hz"), ref_hz)
    if d > 6:
        text = f"**{text}**"
    elif d < -8:
        text = f"({text})"
    if st is not None and st > 4:
        text += "↑"
    elif st is not None and st < -4:
        text += "↓"
    if w["probability"] < 0.5:
        text += "[?]"
    return text


def sound_spans(sounds):
    """Collapse per-second CLAP windows into spans of possible non-speech events."""
    spans = []
    for w in sounds["windows"]:
        for label, p in w["top"]:
            if label in NOT_EVENTS or p < 0.2:
                continue
            last = spans[-1] if spans else None
            if last and last["label"] == label and w["t"] <= last["end"]:
                last["end"], last["p"] = w["t"] + sounds["win"], max(last["p"], p)
            else:
                spans.append({"label": label, "start": w["t"], "end": w["t"] + sounds["win"], "p": p})
    loud_music = [w for w in sounds["windows"] if w["music"] >= 0.5]
    return sorted(spans, key=lambda s: s["start"]), loud_music


def render(out, info):
    asr = load(out, "asr")
    segs = asr["segments"]
    words = [w for s in segs for w in s["words"]]
    for w, f in zip(words, load(out, "prosody") or [{}] * len(words)):
        w.update(f)
    speakers = load(out, "speakers") or [{"speaker": "S1"}] * len(segs)
    emotions = load(out, "emotion") or [None] * len(segs)
    sounds = load(out, "sounds")

    # per-speaker reference pitch, so ↑/↓ mean "unusual for this person"
    by_spk = {}
    for s, k in zip(segs, speakers):
        by_spk.setdefault(k["speaker"], []).append(s)
    ref_hz, share = {}, {}
    talk = sum(s["words"][-1]["end"] - s["words"][0]["start"] for s in segs) or 1
    for spk, ss in by_spk.items():
        hz = [w["hz"] for s in ss for w in s["words"] if w.get("hz")]
        ref_hz[spk] = statistics.median(hz) if hz else None
        share[spk] = sum(s["words"][-1]["end"] - s["words"][0]["start"] for s in ss) / talk
    dbs = [w["db"] for w in words if w.get("db") is not None]
    ref_db = statistics.median(dbs) if dbs else 0
    multi = len(by_spk) > 1

    span = words[-1]["end"] - words[0]["start"] if len(words) > 1 else 0
    L = [f"# Hearing report: {info['file']}", "",
         f"- duration: {info['duration']:.1f} s · language: {asr.get('language')} · words: {len(words)}"
         f" · average pace: {round(len(words) / span * 60) if span else 0} wpm",
         f"- unsure words [?]: {sum(w['probability'] < 0.5 for w in words)}"
         + (" · transcribed from the voice with music removed" if info["separated"] else ""), ""]

    if load(out, "speakers"):
        L.append(f"## Speakers ({len(by_spk)})")
        for spk in sorted(by_spk):
            hz = f"{ref_hz[spk]:.0f} Hz typical pitch" if ref_hz[spk] else "pitch unknown"
            brief = " (brief: may be the main speaker heard over music or noise)" if multi and share[spk] < 0.1 else ""
            L.append(f"- {spk}: {share[spk]:.0%} of the talking, {hz}{brief}")
        L.append("")

    if sounds:
        spans, loud = sound_spans(sounds)
        bed = sum(w["music"] >= 0.2 for w in sounds["windows"]) / max(1, len(sounds["windows"]))
        L.append("## Sounds (CLAP guesses, not certain)")
        L.append(f"- background music: {'likely' if bed >= 0.3 else 'possible' if bed >= 0.1 else 'not detected'}"
                 f" ({bed:.0%} of the clip)")
        if loud:
            L.append("- music or singing prominent at: " + ", ".join(ts(w["t"]) for w in loud))
        for s in spans:
            L.append(f"- [{ts(s['start'])}–{ts(s['end'])}] possibly {s['label']} ({s['p']:.2f})")
        L.append("")

    L += ["## Timeline", "",
          "Legend: **word** louder · (word) quieter · ↑/↓ pitch well above/below that speaker's normal · "
          "[?] Whisper unsure · ‖0.8s‖ pause · ↗/↘ line ends rising/falling · {sounds sad 0.8} emotion guess", ""]
    prev = 0.0
    for s, k, emo in zip(segs, speakers, emotions):
        ws, spk = s["words"], k["speaker"]
        if ws[0]["start"] - prev > 1.0:
            L.append(f"[{ts(prev)}–{ts(ws[0]['start'])}] — no speech —")
        parts = []
        for i, w in enumerate(ws):
            if i and w["start"] - ws[i - 1]["end"] > 0.4:
                parts.append(f"‖{w['start'] - ws[i - 1]['end']:.1f}s‖")
            parts.append(mark(w, ref_db, ref_hz.get(spk)))
        dur = ws[-1]["end"] - ws[0]["start"]
        pace = f"({round(len(ws) / dur * 60)} wpm) " if len(ws) >= 5 and dur > 0 else ""
        pitched = [semitones(w.get("hz"), ref_hz.get(spk)) for w in ws if w.get("hz")]
        end = ""
        if len(pitched) >= 3 and ws[-1].get("hz"):
            delta = semitones(ws[-1]["hz"], ref_hz.get(spk)) - statistics.median(pitched)
            end = " ↗" if delta > 2 else " ↘" if delta < -2 else ""
        tag = ""
        if emo and emo[0][0] not in QUIET_LABELS and emo[0][1] >= 0.6:
            tag = f" {{sounds {emo[0][0]} {emo[0][1]:.1f}}}"
        who = f"{spk} " if multi else ""
        L.append(f"{who}[{ts(ws[0]['start'])}–{ts(ws[-1]['end'])}] {pace}{' '.join(parts)}{end}{tag}")
        prev = ws[-1]["end"]
    if info["duration"] - prev > 1.0:
        L.append(f"[{ts(prev)}–{ts(info['duration'])}] — no speech —")

    stats = {p.stem: json.loads(p.read_text()) for p in sorted((out / "stats").glob("*.json"))}
    L += ["", "## Run", "", "| stage | seconds | process RAM GB | MLX GPU GB |", "|---|---|---|---|"]
    L += [f"| {k} | {v['seconds']} | {v['ram_gb']} | {v['gpu_gb']} |" for k, v in stats.items()]
    (out / "hearing.md").write_text("\n".join(L) + "\n", encoding="utf-8")  # Windows defaults to cp1252: ↑↗ would fail

    for w in words:
        w["speaker"] = None
    i = 0
    for s, k in zip(segs, speakers):
        for _ in s["words"]:
            words[i]["speaker"] = k["speaker"]
            i += 1
    (out / "words.json").write_text(json.dumps(words, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file")
    ap.add_argument("--out", required=True, help="folder for hearing.md, words.json, spectrogram.png")
    ap.add_argument("--fast", action="store_true", help="transcript + loudness/pitch only (no speakers, sounds, emotion)")
    ap.add_argument("--separate", action="store_true",
                    help="remove music before transcribing (slow: ~3-4 min per 40 s; only for loud music over speech)")
    ap.add_argument("--language", default="", help="force a language code, e.g. en, bn")
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    a = ap.parse_args()

    src, out = Path(a.file).resolve(), Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    for old in ["asr", "prosody", "speakers", "emotion", "sounds", "separate"]:
        (out / f"{old}.json").unlink(missing_ok=True)
        (out / "stats" / f"{old}.json").unlink(missing_ok=True)
    (out / "voice.wav").unlink(missing_ok=True)

    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(out / "audio.wav")], check=True)
    duration = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                     str(out / "audio.wav")], capture_output=True, text=True).stdout or 0)
    if duration < 0.1:
        sys.exit("No audio stream found (or under 0.1 s).")

    if a.separate:
        run("separate", src, out)
    if not a.fast:
        run("sounds", src, out)
    run("asr", out, a.language, a.model, required=True)
    run("prosody", out)
    if not a.fast:
        run("speakers", out)
        run("emotion", out)

    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-lavfi",
                    "showspectrumpic=s=1600x512:legend=1:scale=log:fscale=log", str(out / "spectrogram.png")])
    render(out, {"file": src.name, "duration": duration, "separated": (out / "voice.wav").exists()})
    (out / "audio.wav").unlink(missing_ok=True)
    (out / "voice.wav").unlink(missing_ok=True)
    print(out / "hearing.md")


if __name__ == "__main__":
    main()
