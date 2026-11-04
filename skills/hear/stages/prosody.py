# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["librosa>=0.10", "numpy"]
# ///
"""Per-word loudness (dB) and pitch (Hz).

Pitch is pyin (probabilistic yin with voicing), run only on speech lines, in this process.
Tested: a 4-worker pool was no faster (2.0 s either way on 44 s of speech) and its extra processes
slowed the stages that now run alongside. penn (FCNF0++) gave the same median pitch but needed torch and 1.8 GB.
SwiftF0 was 30x faster but no more accurate against Praat on real speech, and it moved the ↑/↓ marks.
"""
import sys
import time
from pathlib import Path

import librosa
import numpy as np

from common import SR, load, read, save

HOP = 160  # 10 ms


def pitch(chunk):
    if chunk.size < 2048:
        return np.full(chunk.size // HOP + 1, np.nan)
    # keep the default resolution: coarser ones break voicing (0.25 st found pitch on 15 of 163 words, 0.1 on 79)
    f0, voiced, _ = librosa.pyin(chunk, fmin=60, fmax=500, sr=SR, frame_length=1024, hop_length=HOP)
    return np.where(voiced, f0, np.nan)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    t0 = time.time()
    y = load(out)
    segs = read(out, "asr")["segments"]
    spans = [(int(s["words"][0]["start"] * SR), int(s["words"][-1]["end"] * SR) + HOP) for s in segs]
    f0s = [pitch(y[a:b]) for a, b in spans]

    frames = np.lib.stride_tricks.sliding_window_view(np.pad(y, (200, 200)), 400)[::HOP]
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-9)

    feats = []
    for s, (a, _), f0 in zip(segs, spans, f0s):
        for w in s["words"]:
            i0 = int(w["start"] * 100)
            i1 = max(i0 + 1, int(w["end"] * 100))
            j0, j1 = i0 - a // HOP, i1 - a // HOP
            v = f0[max(0, j0):max(0, j1)]
            v = v[~np.isnan(v)]
            feats.append({"db": float(db[i0:i1].max()) if i0 < len(db) else None,
                          "hz": float(np.median(v)) if v.size else None})
    save(out, "prosody", feats, t0)
