#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Turn an audio/video file into text Claude can "hear".

Runs each analysis stage as its own process: Whisper first, then the four light stages together.
Their memory adds up to less than Whisper's, so peak RAM stays ~2.4 GB.
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
# CED (AudioSet) label groups from the AudioSet ontology: music-family labels become a "music style" line, speech,
# silence and room/channel labels are never events, laughter counts at a lower bar because it matters most.
CED = json.loads((STAGES / "ced_groups.json").read_text())
CED_SKIP = set(CED["speech"]) | {"Silence", "Echo", "Reverberation", "Radio", "Television", "Static", "Sidetone",
                                 "Mains hum", "Hum", "Harmonic", "Inside, small room", "Inside, large room or hall",
                                 "Inside, public space", "Outside, urban or manmade", "Outside, rural or natural",
                                 "Field recording", "Environmental noise", "Sound effect", "Pulse", "Throbbing"}
CED_MUSIC, CED_LAUGH = set(CED["music"]), set(CED["laughter"])
NOT_STYLE = {"Music", "Mantra", "Chant"}  # "Mantra" fires on any voice over a music bed; bare "Music" says nothing
HALLUCINATION_WPS = 12  # real speech tops out around 8 words/s; Whisper's repeated-token loops run far above


def start(stage, *args):
    return stage, time.time(), subprocess.Popen(["uv", "run", "--quiet", "--script", str(STAGES / f"{stage}.py"), *map(str, args)],
                                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")


def wait(started, required=False):
    """Wait for stages started with start(); a failed optional stage only prints its error."""
    for stage, t, p in started:
        err = p.communicate()[1]
        if p.returncode:
            msg = f"stage {stage} failed:\n" + "\n".join(err.strip().splitlines()[-8:])
            if required:
                sys.exit(msg)
            print(msg, file=sys.stderr)
        else:
            print(f"  {stage}: {time.time() - t:.0f}s", file=sys.stderr)


def run(stage, *args, required=False):
    wait([start(stage, *args)], required)


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
    """Collapse per-second windows into spans of possible non-speech events (CED labels; CLAP for older runs).

    Returns (event spans, windows with prominent music, {music-style label: max prob})."""
    spans, open_, styles = [], {}, {}   # open_: the latest span per label, so a label that alternates with another still joins up
    for w in sounds["windows"]:
        ced = "events" in w
        for label, p in (w["events"] if ced else w["top"]):
            if ced:
                if label in CED_MUSIC:
                    if label not in NOT_STYLE:
                        styles[label] = max(styles.get(label, 0), p)
                    continue
                if label in CED_SKIP or p < (0.15 if label in CED_LAUGH else 0.25):
                    continue
            elif label in NOT_EVENTS or p < 0.2:
                continue
            last = open_.get(label)
            if last and w["t"] <= last["end"]:
                last["end"], last["p"] = w["t"] + sounds["win"], max(last["p"], p)
            else:
                open_[label] = {"label": label, "start": w["t"], "end": w["t"] + sounds["win"], "p": p}
                spans.append(open_[label])
    loud_music = [w for w in sounds["windows"] if w["music"] >= 0.5]
    return sorted(spans, key=lambda s: s["start"]), loud_music, styles


def speech_evidence(sounds, a, b):
    """True unless CLAP saw no speech in any window overlapping [a, b] (used to drop Whisper's music hallucinations)."""
    if not sounds:
        return True
    hits = [w for w in sounds["windows"] if w["t"] < b and w["t"] + sounds["win"] > a]
    speech = lambda w: w["speech"] if "speech" in w else dict(w["top"]).get("speech", 0)
    return not hits or any(speech(w) >= 0.15 for w in hits)


def ranges(times, win):
    """[0, 1, 2, 7] with a 2 s window -> ['00:00.0–00:04.0', '00:07.0–00:09.0']."""
    out = []
    for t in times:
        if out and t <= out[-1][1]:
            out[-1][1] = t + win
        else:
            out.append([t, t + win])
    return [f"{ts(a)}–{ts(b)}" for a, b in out]


def sound_lines(sounds):
    spans, loud, styles = sound_spans(sounds)
    bed = sum(w["music"] >= 0.2 for w in sounds["windows"]) / max(1, len(sounds["windows"]))
    L = ["## Sounds (model guesses, not certain)",
         f"- background music: {'likely' if bed >= 0.3 else 'possible' if bed >= 0.1 else 'not detected'} ({bed:.0%} of the clip)"]
    style = [f"{k.lower()} ({p:.2f})" for k, p in sorted(styles.items(), key=lambda kv: -kv[1])[:3] if p >= 0.2]
    if bed >= 0.1 and style:
        L.append("- music style guess: " + ", ".join(style))
    if loud:
        L.append("- music or singing prominent at: " + ", ".join(ranges([w["t"] for w in loud], sounds["win"])))
    for s in spans:
        L.append(f"- [{ts(s['start'])}–{ts(s['end'])}] possibly {s['label'].lower()} ({s['p']:.2f})")
    return L + [""]


def fold_doubtful_speakers(segs, speakers, sounds):
    """A voice fingerprint taken under loud music or from a very short line is unreliable. A speaker with under 10 %
    of the talk whose every line is like that, and whose lines still resemble the main speaker, is almost always the
    main speaker again (seen on reels: one intro line over the music became "S2"). Fold it back and renumber."""
    if not speakers or "sims" not in speakers[0]:
        return
    dur = lambda s: s["words"][-1]["end"] - s["words"][0]["start"]
    time_by = {}
    for s, k in zip(segs, speakers):
        time_by[k["speaker"]] = time_by.get(k["speaker"], 0) + dur(s)
    if len(time_by) < 2:
        return
    main, total = max(time_by, key=time_by.get), sum(time_by.values()) or 1

    def music(s):
        a, b = s["words"][0]["start"], s["words"][-1]["end"]
        return max([w["music"] for w in sounds["windows"] if w["t"] < b and w["t"] + sounds["win"] > a] or [0]) if sounds else 0

    for spk, t in time_by.items():
        if spk == main or t / total >= 0.1:
            continue
        lines = [(s, k) for s, k in zip(segs, speakers) if k["speaker"] == spk]
        # under a second of speech in total can't establish a voice at all; otherwise every line must be doubtful
        if t < 1.0 or all((music(s) >= 0.8 or dur(s) < 1.5) and k["sims"].get(main, 0) >= 0.55 for s, k in lines):
            for _, k in lines:
                k["speaker"] = main
    left = sorted({k["speaker"] for k in speakers}, key=lambda n: -time_by[n])
    rename = {old: f"S{i + 1}" for i, old in enumerate(left)}
    for k in speakers:
        k["speaker"] = rename[k["speaker"]]


def render(out, info):
    asr = load(out, "asr")
    segs = asr["segments"]
    words = [w for s in segs for w in s["words"]]
    for w, f in zip(words, load(out, "prosody") or [{}] * len(words)):
        w.update(f)
    speakers = load(out, "speakers") or [{"speaker": "S1"}] * len(segs)
    emotions = load(out, "emotion") or [None] * len(segs)
    sounds = load(out, "sounds")

    # Whisper hallucinates on music and silence: token loops at absurd speed, or "Thank you." where nobody speaks
    def real(s):
        a, b = s["words"][0]["start"], s["words"][-1]["end"]
        return len(s["words"]) / max(b - a, 0.05) <= HALLUCINATION_WPS and speech_evidence(sounds, a, b)
    keep = [real(s) for s in segs]
    dropped = keep.count(False)
    segs, speakers, emotions = ([x for x, k in zip(xs, keep) if k] for xs in (segs, speakers, emotions))
    words = [w for s in segs for w in s["words"]]
    fold_doubtful_speakers(segs, speakers, sounds)
    if not words:
        L = [f"# Hearing report: {info['file']}", "", f"- duration: {info['duration']:.1f} s · no speech found"
             + (f" ({dropped} Whisper line{'s' if dropped > 1 else ''} dropped as likely hallucination)" if dropped else ""), ""]
        (out / "hearing.md").write_text("\n".join(L + (sound_lines(sounds) if sounds else [])))
        (out / "words.json").write_text("[]")
        return

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
         f"- duration: {info['duration']:.1f} s · language: {asr.get('language')}"
         + (f" (Whisper only {asr['language_prob']:.0%} sure: if the script looks wrong, re-run with --language)"
            if asr.get("language_prob") is not None and asr["language_prob"] < 0.7 else "")
         + f" · words: {len(words)}"
         f" · average pace: {round(len(words) / span * 60) if span else 0} wpm",
         f"- unsure words [?]: {sum(w['probability'] < 0.5 for w in words)}"
         + (f" · {dropped} Whisper line{'s' if dropped > 1 else ''} dropped as likely hallucination" if dropped else "")
         + (" · transcribed from the voice with music removed" if info["separated"] else ""), ""]

    if load(out, "speakers"):
        L.append(f"## Speakers ({len(by_spk)})")
        for spk in sorted(by_spk):
            hz = f"{ref_hz[spk]:.0f} Hz typical pitch" if ref_hz[spk] else "pitch unknown"
            brief = " (brief: may be the main speaker heard over music or noise)" if multi and share[spk] < 0.1 else ""
            L.append(f"- {spk}: {share[spk]:.0%} of the talking, {hz}{brief}")
        L.append("")

    if sounds:
        L += sound_lines(sounds)

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
    run("asr", out, a.language, a.model, required=True)
    # the rest only need asr.json; together they use less RAM than Whisper did, so run them at once
    rest = [start("prosody", out)]
    if not a.fast:
        rest += [start("speakers", out), start("emotion", out), start("sounds", src, out)]
    wait(rest)

    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-lavfi",
                    "showspectrumpic=s=1600x512:legend=1:scale=log:fscale=log", str(out / "spectrogram.png")])
    render(out, {"file": src.name, "duration": duration, "separated": (out / "voice.wav").exists()})
    (out / "audio.wav").unlink(missing_ok=True)
    (out / "voice.wav").unlink(missing_ok=True)
    print(out / "hearing.md")


if __name__ == "__main__":
    main()
