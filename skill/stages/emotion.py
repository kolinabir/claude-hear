# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["onnxruntime>=1.18", "huggingface_hub", "numpy"]
# ///
"""Emotion per transcript line (emotion2vec+ large, ONNX export: no torch/FunASR needed)."""
import sys
import time
from pathlib import Path

import numpy as np

from common import SR, load, read, save

MIN_S, MAX_S = 1.5, 30.0  # shorter lines are too little to judge; the model was checked up to 30 s

out = Path(sys.argv[1])
t0 = time.time()
import onnxruntime as ort  # noqa: E402
from huggingface_hub import hf_hub_download  # noqa: E402

sess = ort.InferenceSession(hf_hub_download("Voldorn/emotion2vec-plus-large-onnx", "emotion2vec_plus_large.onnx"),
                            providers=["CPUExecutionProvider"])
labels = sess.get_modelmeta().custom_metadata_map["labels"]
labels = [l.strip(" '\"[]") for l in labels.split(",")]

y = load(out)
res = []
for s in read(out, "asr")["segments"]:
    a, b = s["words"][0]["start"], s["words"][-1]["end"]
    if b - a < MIN_S:
        res.append(None)
        continue
    p = sess.run(None, {"audio": y[int(a * SR):int(min(b, a + MAX_S) * SR)][None]})[0][0]
    top = np.argsort(p)[::-1][:2]
    res.append([[labels[k], round(float(p[k]), 2)] for k in top])
save(out, "emotion", res, t0)
