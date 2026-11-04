"""Shared helpers for hear stages. Each stage is its own process so its memory is freed when it exits."""
import json
import resource
import time
import urllib.request
import wave
from pathlib import Path

import numpy as np

SR = 16000
CACHE = Path.home() / ".cache" / "hear"


def load(out: Path, voice=True):
    """16 kHz mono float32. Uses the separated voice when it exists."""
    p = out / "voice.wav" if voice and (out / "voice.wav").exists() else out / "audio.wav"
    with wave.open(str(p)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def read(out: Path, name):
    p = out / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def save(out: Path, name, data, t0, gpu_bytes=0):
    (out / f"{name}.json").write_text(json.dumps(data))
    (out / "stats").mkdir(exist_ok=True)
    (out / "stats" / f"{name}.json").write_text(json.dumps({
        "seconds": round(time.time() - t0, 1),
        # macOS reports bytes; children = worker processes (largest one)
        "ram_gb": round(max(resource.getrusage(r).ru_maxrss
                            for r in (resource.RUSAGE_SELF, resource.RUSAGE_CHILDREN)) / 1e9, 2),
        "gpu_gb": round(gpu_bytes / 1e9, 2),
    }))


def fetch(url, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    if not p.exists():
        tmp = p.with_suffix(".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(p)
    return p


def words(asr):
    return [w for s in asr["segments"] for w in s["words"]]
