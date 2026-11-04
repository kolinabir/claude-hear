# /// script
# requires-python = ">=3.11,<3.13"
# dependencies = ["transformers>=4.45", "torch", "numpy"]
# ///
"""Name non-speech sounds per second with CLAP zero-shot (laion/clap-htsat-unfused). Reads the original file at 48 kHz."""
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

from common import save

SR48 = 48000
WIN, HOP = 2.0, 1.0  # 2 s windows every 1 s
LABELS = [
    "speech", "silence", "music", "singing", "laughter", "applause", "cheering crowd", "crowd talking",
    "whoosh sound effect", "riser sound effect", "beep", "ding notification", "camera shutter", "typing on a keyboard",
    "footsteps", "door", "car traffic", "wind noise", "dog barking", "phone ringing", "explosion",
    "breathing", "coughing", "crying", "screaming",
]
MUSIC = {"music", "singing"}

src, out = sys.argv[1], Path(sys.argv[2])
t0 = time.time()
import torch  # noqa: E402
from transformers import ClapModel, ClapProcessor  # noqa: E402

raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR48), "-f", "f32le", "-"],
                     capture_output=True, check=True).stdout
y = np.frombuffer(raw, np.float32)
starts = np.arange(0, max(len(y) / SR48 - WIN, 0) + 1e-6, HOP)
clips = [y[int(s * SR48):int((s + WIN) * SR48)] for s in starts]

model = ClapModel.from_pretrained("laion/clap-htsat-unfused").eval()
proc = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
def unit(x):
    x = x if torch.is_tensor(x) else x.pooler_output  # transformers 5 returns an output object
    return x / x.norm(dim=-1, keepdim=True)


with torch.inference_mode():
    t = unit(model.get_text_features(**proc(text=[f"This is a sound of {l}." for l in LABELS], return_tensors="pt", padding=True)))
    probs = []
    for i in range(0, len(clips), 16):
        a = unit(model.get_audio_features(**proc(audio=clips[i:i + 16], sampling_rate=SR48, return_tensors="pt")))
        probs.append((model.logit_scale_a.exp() * a @ t.T).softmax(-1).numpy())
probs = np.concatenate(probs)

windows = []
for s, p in zip(starts, probs):
    top = np.argsort(p)[::-1][:3]
    windows.append({"t": float(s), "top": [[LABELS[k], round(float(p[k]), 2)] for k in top],
                    "music": round(float(sum(p[LABELS.index(m)] for m in MUSIC)), 2)})
save(out, "sounds", {"windows": windows, "win": WIN}, t0)
