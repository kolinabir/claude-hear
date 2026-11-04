# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["sherpa-onnx>=1.10", "numpy"]
# ///
"""Who said each transcript line: a voice embedding per line, then greedy cosine clustering.

Per-line (not per-window) on purpose: short reactions like "Oh, God" are their own lines,
and window-based diarizers (tested: senko) merge them into the main speaker.
"""
import sys
import time
from pathlib import Path

import numpy as np

from common import SR, fetch, load, read, save

SAME = 0.75  # cosine similarity above this = same speaker (tested: same voice 0.90+, different voice ~0.5)
SHORT, SAME_SHORT = 1.5, 0.55  # lines under 1.5 s embed poorly: join the nearest voice more readily
MODEL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
         "wespeaker_en_voxceleb_resnet34_LM.onnx")

out = Path(sys.argv[1])
t0 = time.time()
import sherpa_onnx  # noqa: E402

ex = sherpa_onnx.SpeakerEmbeddingExtractor(sherpa_onnx.SpeakerEmbeddingExtractorConfig(
    model=str(fetch(MODEL, "wespeaker_resnet34.onnx")), num_threads=4))
y = load(out)
segs = read(out, "asr")["segments"]

embs = []
for s in segs:
    a, b = s["words"][0]["start"], s["words"][-1]["end"]
    if b - a < 0.6:  # too short to embed reliably: pad around it
        a, b = max(0, (a + b) / 2 - 0.3), (a + b) / 2 + 0.3
    st = ex.create_stream()
    st.accept_waveform(SR, y[int(a * SR):int(b * SR)])
    st.input_finished()
    e = np.array(ex.compute(st))
    embs.append(e / np.linalg.norm(e))

# longest lines first, so the clusters start from the most reliable voices
order = sorted(range(len(segs)), key=lambda i: segs[i]["words"][0]["start"] - segs[i]["words"][-1]["end"])
centroids, labels, sims = [], [None] * len(segs), [0.0] * len(segs)
for i in order:
    s = [float(c @ embs[i] / np.linalg.norm(c)) for c in centroids]
    k = int(np.argmax(s)) if s else -1
    short = segs[i]["words"][-1]["end"] - segs[i]["words"][0]["start"] < SHORT
    if k >= 0 and s[k] >= (SAME_SHORT if short else SAME):
        centroids[k] = centroids[k] + embs[i]
    else:
        centroids.append(embs[i].copy())
        k = len(centroids) - 1
    labels[i], sims[i] = k, (s[k] if k < len(s) else 1.0)

# name speakers S1, S2... by total speaking time
time_by = {}
for i, s in enumerate(segs):
    time_by[labels[i]] = time_by.get(labels[i], 0) + s["words"][-1]["end"] - s["words"][0]["start"]
rank = {k: f"S{n + 1}" for n, k in enumerate(sorted(time_by, key=time_by.get, reverse=True))}
save(out, "speakers", [{"speaker": rank[labels[i]], "similarity": round(sims[i], 2)} for i in range(len(segs))], t0)
